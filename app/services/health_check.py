import datetime

from app.core.logger import setup_logger
from app.dtos.health_check import (
    ClinicalItem,
    HealthCheckCreateRequest,
    HealthCheckListResponse,
    HealthCheckResponse,
    LifestyleDomainSummary,
    LifestyleItem,
    ReportMeta,
    ReportResponse,
)
from app.models.health_check import AppGroup, CkdStage, DialysisType, HealthCheck, UrineResult
from app.models.lifestyle_survey import LifestyleSurvey, SmokingStatus
from app.models.safety_event import SafetyEvent, SafetyEventType
from app.models.users import Gender, User
from app.repositories.health_check_repository import HealthCheckRepository
from app.services import ckd_publisher
from app.services.clinical_reference import (
    DOMAIN_LABEL,
    DOMAIN_ORDER,
    M1_CAT_ORDER,
    M1_CATEGORY,
    M1_DESC,
    M1_DISEASE,
    M1_LABEL,
    M2_LABEL,
    build_domain_summary_text,
    classify_shap_items,
    m1_direction,
    m1_format,
    m1_group_message,
    m1_group_title,
    m1_normal_range,
    m1_status,
    m2_domain,
    m2_improve_action,
    m2_in_normal,
    m2_label,
    m2_normal_range,
    m2_status,
)

logger = setup_logger("health_check_service")

# 세이프티 가드 임계값
_BP_CRISIS_SYSTOLIC = 180  # mmHg — 고혈압 위기 기준
_BP_CRISIS_DIASTOLIC = 120  # mmHg
_GLUCOSE_CRISIS = 400  # mg/dL — 즉각 처치 필요 수준
_EGFR_G5_THRESHOLD = 15  # mL/min/1.73m² — 신부전 단계

# 그룹 분류 임계값 (설계서 § 4)
_G1_EGFR_THRESHOLD = 60.0  # eGFR < 60 → G1
_G2_SBP_THRESHOLD = 130  # SBP ≥ 130 → G2
_G2_DBP_THRESHOLD = 80  # DBP ≥ 80  → G2
_G2_GLUCOSE_THRESHOLD = 100.0  # 공복혈당 ≥ 100 → G2


class HealthCheckService:
    def __init__(self) -> None:
        self._repo = HealthCheckRepository()

    # ── 순수 계산 유틸 ──────────────────────────────────────────────────────

    @staticmethod
    def _calculate_bmi(weight: float, height: float) -> float:
        """BMI = 체중(kg) / 신장(m)²"""
        height_m = height / 100.0
        return round(weight / (height_m**2), 1)

    @staticmethod
    def _estimate_egfr(creatinine: float, age: int, gender: Gender) -> float:
        """
        CKD-EPI 2021 공식 (race 무관 버전).
        creatinine: mg/dL | age: 세 | 반환: mL/min/1.73m²

        참고: Inker LA, et al. NEJM 2021;385:1737-1749.
        """
        is_female = gender == Gender.FEMALE
        kappa = 0.7 if is_female else 0.9
        alpha = -0.241 if is_female else -0.302
        sex_factor = 1.012 if is_female else 1.0

        cr_ratio = creatinine / kappa
        if cr_ratio < 1.0:
            egfr = 142 * (cr_ratio**alpha) * (0.9938**age) * sex_factor
        else:
            egfr = 142 * (cr_ratio**-1.200) * (0.9938**age) * sex_factor
        return round(egfr, 1)

    @staticmethod
    def _effective_ldl(hc: HealthCheck) -> float | None:
        """LDL: 입력값 우선, 없으면 Friedewald(total - hdl - trig/5, trig<400)."""
        if hc.ldl_cholesterol is not None:
            return hc.ldl_cholesterol
        if (
            hc.total_cholesterol is not None
            and hc.hdl_cholesterol is not None
            and hc.triglycerides is not None
            and hc.triglycerides < 400
        ):
            return round(hc.total_cholesterol - hc.hdl_cholesterol - hc.triglycerides / 5.0, 1)
        return None

    @staticmethod
    def _get_ckd_stage(egfr: float) -> CkdStage:
        """KDIGO 2022 기준 eGFR → G 단계 매핑."""
        if egfr >= 90:
            return CkdStage.G1
        elif egfr >= 60:
            return CkdStage.G2
        elif egfr >= 45:
            return CkdStage.G3A
        elif egfr >= 30:
            return CkdStage.G3B
        elif egfr >= 15:
            return CkdStage.G4
        else:
            return CkdStage.G5

    @staticmethod
    def _assign_app_group(
        egfr: float | None,
        systolic_bp: int,
        diastolic_bp: int,
        fasting_glucose: float,
        ckd_diagnosed: bool = False,
        dialysis_type: DialysisType | None = None,
    ) -> AppGroup:
        """규칙 기반 AppGroup 배정 (설계서 § 4 + CKD 진단자 분기).

        1단계: CKD 진단자 우선 — 투석/이식이면 DIALYSIS, 그 외(비투석)는 CKD.
               스크리닝(2단계)으로 내려가지 않는다.
        2단계: 미진단자 스크리닝 (우선순위 G1→G2→G4). G3는 Model 1 score 필요 —
               AI 워커가 비동기로 배정(연동 전까지 G4 fallback).
        """
        # 1단계: CKD 진단자 우선 처리
        if ckd_diagnosed:
            if dialysis_type in (DialysisType.HEMODIALYSIS, DialysisType.PERITONEAL, DialysisType.TRANSPLANT):
                return AppGroup.DIALYSIS
            return AppGroup.CKD  # none/미입력 → 비투석(보존기)
        # 2단계: 미진단자 스크리닝
        if egfr is not None and egfr < _G1_EGFR_THRESHOLD:
            return AppGroup.G1
        if (
            systolic_bp >= _G2_SBP_THRESHOLD
            or diastolic_bp >= _G2_DBP_THRESHOLD
            or fasting_glucose >= _G2_GLUCOSE_THRESHOLD
        ):
            return AppGroup.G2
        return AppGroup.G4  # G3: Model 1 연동 전 G4로 fallback

    @staticmethod
    async def recompute_app_group(user_id: int) -> AppGroup | None:
        """문진(LifestyleSurvey) 변경 시 최신 검진의 app_group을 동기 재계산한다.

        app_group은 검진(create_health_check) 시점에만 굳는다. 그러나 CKD 진단 여부·
        투석 종류는 문진에서 오므로, 검진 후 문진을 바꾸면 app_group이 옛 값으로 어긋난다
        (예: 진단 입력 후에도 대시보드가 일반 G그룹으로 표시). 여기서 최신 검진+최신 문진으로
        _assign_app_group을 재호출해 정합을 맞춘다. AI 워커 재예측은 app_group이
        CKD/DIALYSIS면 보호하므로(db.update_prediction CASE 가드) 이 동기 갱신을 덮어쓰지 않는다.

        반환: 갱신 후 app_group (검진 없으면 None).
        """
        hc = await HealthCheck.filter(user_id=user_id).order_by("-checked_date", "-id").first()
        if hc is None:
            return None
        lifestyle = await LifestyleSurvey.filter(user_id=user_id).order_by("-surveyed_date", "-id").first()
        ckd_diagnosed = bool(lifestyle.ckd_diagnosed) if lifestyle else False
        dialysis_type = lifestyle.dialysis_type if (lifestyle and ckd_diagnosed) else None
        new_group = HealthCheckService._assign_app_group(
            hc.egfr_estimated,
            hc.systolic_bp,
            hc.diastolic_bp,
            hc.fasting_glucose,
            ckd_diagnosed=ckd_diagnosed,
            dialysis_type=dialysis_type,
        )
        if hc.app_group != new_group:
            hc.app_group = new_group
            await hc.save(update_fields=["app_group"])
        return new_group

    @staticmethod
    def _check_safety_warning(
        systolic_bp: int,
        diastolic_bp: int,
        fasting_glucose: float,
        egfr: float | None,
    ) -> str | None:
        """
        위험 수치 감지 시 즉시 의료기관 안내 문구 반환.
        서비스는 진단·처방을 내리지 않는다 — 안내 메시지만 제공.
        """
        warnings: list[str] = []

        if systolic_bp >= _BP_CRISIS_SYSTOLIC or diastolic_bp >= _BP_CRISIS_DIASTOLIC:
            warnings.append(
                f"혈압이 매우 높습니다 ({systolic_bp}/{diastolic_bp} mmHg). "
                "즉시 가까운 의료기관을 방문하거나 119에 연락하세요."
            )

        if fasting_glucose >= _GLUCOSE_CRISIS:
            warnings.append(
                f"공복혈당이 매우 높습니다 ({fasting_glucose:.0f} mg/dL). "
                "즉시 가까운 의료기관을 방문하거나 119에 연락하세요."
            )

        if egfr is not None and egfr < _EGFR_G5_THRESHOLD:
            warnings.append(
                f"신장 기능이 매우 저하되어 있습니다 (eGFR {egfr} mL/min/1.73m²). 즉시 신장내과 전문의 진료를 받으세요."
            )

        return " | ".join(warnings) if warnings else None

    # ── 퍼블릭 서비스 메서드 ────────────────────────────────────────────────

    async def create_health_check(
        self,
        user_id: int,
        user_age: int,
        user_gender: Gender,
        dto: HealthCheckCreateRequest,
    ) -> HealthCheckResponse:
        bmi = self._calculate_bmi(dto.weight, dto.height)

        # CKD-EPI eGFR 추정 (크레아티닌 입력 시)
        egfr: float | None = None
        ckd_stage: CkdStage | None = None
        if dto.creatinine is not None:
            egfr = self._estimate_egfr(dto.creatinine, user_age, user_gender)
            ckd_stage = self._get_ckd_stage(egfr)

        # CKD 진단 여부 조회(LifestyleSurvey) — 그룹 배정에 반영. 없으면 미진단(False).
        lifestyle = await LifestyleSurvey.filter(user_id=user_id).order_by("-surveyed_date", "-id").first()
        ckd_diagnosed = bool(lifestyle.ckd_diagnosed) if lifestyle else False
        dialysis_type = lifestyle.dialysis_type if (lifestyle and ckd_diagnosed) else None  # 문진 단일 진실 + 미러링
        app_group = self._assign_app_group(
            egfr,
            dto.systolic_bp,
            dto.diastolic_bp,
            dto.fasting_glucose,
            ckd_diagnosed=ckd_diagnosed,
            dialysis_type=dialysis_type,
        )

        hc = await self._repo.create(
            user_id=user_id,
            checked_date=dto.checked_date,
            systolic_bp=dto.systolic_bp,
            diastolic_bp=dto.diastolic_bp,
            fasting_glucose=dto.fasting_glucose,
            creatinine=dto.creatinine,
            total_cholesterol=dto.total_cholesterol,
            hdl_cholesterol=dto.hdl_cholesterol,
            triglycerides=dto.triglycerides,
            ldl_cholesterol=dto.ldl_cholesterol,
            hemoglobin=dto.hemoglobin,
            ast=dto.ast,
            alt=dto.alt,
            urine_protein=dto.urine_protein,
            urine_glucose=dto.urine_glucose,
            weight=dto.weight,
            height=dto.height,
            bmi=bmi,
            waist_circumference=dto.waist_circumference,
            egfr_estimated=egfr,
            ckd_stage=ckd_stage,
            app_group=app_group,
            dialysis_type=dialysis_type,
        )

        safety_warning = self._check_safety_warning(dto.systolic_bp, dto.diastolic_bp, dto.fasting_glucose, egfr)

        # 위험 감지 시 SafetyEvent 영구 기록 (관리자 모니터링용)
        await self._record_safety_events(user_id=user_id, health_check=hc, dto=dto, egfr=egfr)

        # 비동기 CKD 예측 job 발행 — 진단자는 스킵(이미 의료영역, 위험도 예측·리포트 비대상)
        if not ckd_diagnosed:
            try:
                await ckd_publisher.publish_ckd_job(
                    health_check_id=hc.id,
                    user_id=user_id,
                    user_age=user_age,
                    user_gender=user_gender,
                    checked_date=dto.checked_date,
                    bmi=bmi,
                    egfr=egfr,
                    dto=dto,
                )
            except Exception:  # noqa: BLE001 — 예측 발행 실패가 검진 API를 깨지 않도록
                logger.exception("CKD 예측 job 발행 실패 — 검진은 저장됨 hc=%s", hc.id)
        else:
            logger.info("CKD 진단자 — 예측 job 미발행(위험도·리포트 비대상) hc=%s", hc.id)

        response = HealthCheckResponse.model_validate(hc)
        response.safety_warning = safety_warning
        return response

    @staticmethod
    async def _record_safety_events(
        *,
        user_id: int,
        health_check: HealthCheck,
        dto: HealthCheckCreateRequest,
        egfr: float | None,
    ) -> None:
        """위험 수치 발견 시 SafetyEvent 1건씩 영구 기록. 관리자 화면에서 모니터링."""
        if dto.systolic_bp >= _BP_CRISIS_SYSTOLIC or dto.diastolic_bp >= _BP_CRISIS_DIASTOLIC:
            await SafetyEvent.create(
                user_id=user_id,
                health_check_id=health_check.id,
                event_type=SafetyEventType.BP_CRISIS,
                value=float(dto.systolic_bp),
                message=(
                    f"혈압이 매우 높습니다 ({dto.systolic_bp}/{dto.diastolic_bp} mmHg). "
                    "즉시 가까운 의료기관을 방문하거나 119에 연락하세요."
                ),
            )
        if dto.fasting_glucose >= _GLUCOSE_CRISIS:
            await SafetyEvent.create(
                user_id=user_id,
                health_check_id=health_check.id,
                event_type=SafetyEventType.GLUCOSE_CRISIS,
                value=float(dto.fasting_glucose),
                message=(
                    f"공복혈당이 매우 높습니다 ({dto.fasting_glucose:.0f} mg/dL). "
                    "즉시 가까운 의료기관을 방문하거나 119에 연락하세요."
                ),
            )
        if egfr is not None and egfr < _EGFR_G5_THRESHOLD:
            await SafetyEvent.create(
                user_id=user_id,
                health_check_id=health_check.id,
                event_type=SafetyEventType.EGFR_CRISIS,
                value=float(egfr),
                message=(
                    f"신장 기능이 매우 저하되어 있습니다 (eGFR {egfr} mL/min/1.73m²). "
                    "즉시 신장내과 전문의 진료를 받으세요."
                ),
            )

    async def get_health_checks(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> HealthCheckListResponse:
        total, items = await self._repo.get_by_user(user_id, limit, offset)
        return HealthCheckListResponse(
            total=total,
            items=[HealthCheckResponse.model_validate(item) for item in items],
        )

    async def get_health_check(
        self,
        health_check_id: int,
        user_id: int,
    ) -> HealthCheckResponse | None:
        hc = await self._repo.get_by_id(health_check_id, user_id)
        if hc is None:
            return None
        return HealthCheckResponse.model_validate(hc)

    async def delete_health_check(self, health_check_id: int, user_id: int) -> bool:
        """본인 소유 검진 삭제. 없으면 False."""
        return await self._repo.delete_by_id(health_check_id, user_id)

    async def delete_all_health_checks(self, user_id: int) -> int:
        """본인 검진 전부 삭제. 삭제된 건수 반환."""
        return await self._repo.delete_all_by_user(user_id)

    async def update_health_check(
        self,
        health_check_id: int,
        user_id: int,
        user_age: int,
        user_gender: Gender,
        dto: HealthCheckCreateRequest,
    ) -> HealthCheckResponse | None:
        """본인 소유 검진 수정. 없으면 None. eGFR/CKD stage/app_group 재계산.

        ✱ 정책: 최신 검진의 수정 흐름이지만 권한·동작은 단건 PATCH로 통합 — 본인 소유면 어떤 row든 수정 가능.
        프론트(`CheckupHistoryPage`)에서 최신 1건에만 수정 버튼 노출하여 UX 정책 시행.
        """
        bmi = self._calculate_bmi(dto.weight, dto.height)
        egfr: float | None = None
        ckd_stage: CkdStage | None = None
        if dto.creatinine is not None:
            egfr = self._estimate_egfr(dto.creatinine, user_age, user_gender)
            ckd_stage = self._get_ckd_stage(egfr)

        lifestyle = await LifestyleSurvey.filter(user_id=user_id).order_by("-surveyed_date", "-id").first()
        ckd_diagnosed = bool(lifestyle.ckd_diagnosed) if lifestyle else False
        dialysis_type = lifestyle.dialysis_type if (lifestyle and ckd_diagnosed) else None
        app_group = self._assign_app_group(
            egfr,
            dto.systolic_bp,
            dto.diastolic_bp,
            dto.fasting_glucose,
            ckd_diagnosed=ckd_diagnosed,
            dialysis_type=dialysis_type,
        )

        hc = await self._repo.update_by_id(
            health_check_id,
            user_id,
            checked_date=dto.checked_date,
            systolic_bp=dto.systolic_bp,
            diastolic_bp=dto.diastolic_bp,
            fasting_glucose=dto.fasting_glucose,
            creatinine=dto.creatinine,
            total_cholesterol=dto.total_cholesterol,
            hdl_cholesterol=dto.hdl_cholesterol,
            triglycerides=dto.triglycerides,
            ldl_cholesterol=dto.ldl_cholesterol,
            hemoglobin=dto.hemoglobin,
            ast=dto.ast,
            alt=dto.alt,
            urine_protein=dto.urine_protein,
            urine_glucose=dto.urine_glucose,
            weight=dto.weight,
            height=dto.height,
            bmi=bmi,
            waist_circumference=dto.waist_circumference,
            egfr_estimated=egfr,
            ckd_stage=ckd_stage,
            app_group=app_group,
            dialysis_type=dialysis_type,
        )
        if hc is None:
            return None

        safety_warning = self._check_safety_warning(dto.systolic_bp, dto.diastolic_bp, dto.fasting_glucose, egfr)
        response = HealthCheckResponse.model_validate(hc)
        response.safety_warning = safety_warning
        return response

    # ── 모델1 리포트 헬퍼 (순수 함수, app_group 기반) ─────────────────────────

    @staticmethod
    def _recommend_tests(
        app_group: AppGroup | None,
        *,
        sbp: int,
        dbp: int,
        fasting_glucose: float,
        hemoglobin: float | None,
        urine_protein: UrineResult | None,
        gender_int: int,
        htn_dx: bool = False,
        dm_dx: bool = False,
    ) -> list[str]:
        """app_group 코어 + 임상 상태 게이트 조건부 권장 검사 리스트.

        코어: 그룹별 재검 주기·CKD 특이 항목 (eGFR 수치 무관 고정).
        조건부: status != good 또는 진단 플래그 → 그룹 무관 추가.
        톤: 선별 서비스 — "진단"·"환자" 단정 표현 배제.
        """
        if app_group is None:
            return []

        # ── 그룹별 코어 ──────────────────────────────────────────────────
        if app_group == AppGroup.G1:
            core: list[str] = [
                "eGFR·혈청 크레아티닌 재검(3개월 내)",
                "요단백(소변 알부민/크레아티닌비) 검사",
                "신장내과 상담 권고",
            ]
        elif app_group == AppGroup.G2:
            core = [
                "eGFR·혈청 크레아티닌 정기 재검(6개월 내)",
                "요단백(소변) 선별 검사",
            ]
        elif app_group == AppGroup.G3:
            core = [
                "생활습관 개선 후 신장 기능 재평가",
                "연 1~2회 eGFR 정기 검사",
            ]
        else:  # G4
            core = [
                "현 상태 유지",
                "연 1회 정기 건강검진 권장",
            ]

        # ── 조건부 추가 (그룹 무관, 임상 상태 게이트) ────────────────────
        conditional: list[str] = []

        # 혈압: sbp 또는 dbp status_level != good, 또는 고혈압 진단
        _, sbp_level = m1_status("sbp", float(sbp), gender_int)
        _, dbp_level = m1_status("dbp", float(dbp), gender_int)
        if sbp_level != "good" or dbp_level != "good" or htn_dx:
            conditional.append("혈압 정밀 측정·관리 상태 확인")

        # 공복혈당: status_level != good, 또는 당뇨 진단
        _, fbs_level = m1_status("fasting_glucose", fasting_glucose, gender_int)
        if fbs_level != "good" or dm_dx:
            conditional.append("공복혈당·당화혈색소(HbA1c) 검사")

        # 헤모글로빈 빈혈
        if hemoglobin is not None:
            hb_label, _ = m1_status("hemoglobin", hemoglobin, gender_int)
            if hb_label == "빈혈":
                conditional.append("빈혈(헤모글로빈) 확인")

        # 요단백 양성 — 코어 선별 검사와 별도 escalation
        if urine_protein == UrineResult.POSITIVE:
            conditional.append("요단백 양성 — 정밀 추적 및 전문의 소견 권고")

        return core + conditional

    @staticmethod
    def _enrich_shap_status(shap_list: list, gender: int) -> list:
        """각 ShapItem dict에 status(단계 라벨)·status_level을 추가한다.

        DB에 저장된 shap_model1 항목은 feature(한글)·value·shap·note만 가진다.
        classify_shap_items는 status 필드로 임상 분류를 수행하므로 두 필드 모두 필요.
        SHAP 수치 자체는 변경하지 않는다(부호 왜곡 금지).
        """
        _reverse_label: dict[str, str] = {v: k for k, v in M1_LABEL.items()}
        enriched = []
        for item in shap_list:
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            if "status" not in entry or "status_level" not in entry:
                var = _reverse_label.get(entry.get("feature", ""))
                if var:
                    st_label, sl = m1_status(var, float(entry.get("value", 0.0)), gender)
                    entry.setdefault("status", st_label)
                    entry.setdefault("status_level", sl)
            enriched.append(entry)
        return enriched

    @staticmethod
    def _enrich_m1_side(shap_list: list) -> list:
        """classify_shap_items 결과로 각 M1 ShapItem dict에 side 필드를 채운다.

        raise_items → "improve" (위험 높임·빨강)
        lower_items → "maintain" (위험 낮춤·초록)
        양쪽 제외(정상+shap>0) → "exclude" (ShapImpactBars 양쪽에서 자동 제외)

        _enrich_shap_status 이후 호출 전제 — status/status_level이 채워진 상태여야 함.
        """
        if not shap_list:
            return shap_list
        classified = classify_shap_items(shap_list)
        raise_ids = {id(it) for it in classified["raise_items"]}
        lower_ids = {id(it) for it in classified["lower_items"]}
        for it in shap_list:
            if id(it) in raise_ids:
                it["side"] = "improve"
            elif id(it) in lower_ids:
                it["side"] = "maintain"
            else:
                it["side"] = "exclude"
        return shap_list

    @staticmethod
    def _enrich_m2_side(shap2_raw: dict | None, gender_int: int) -> dict | None:
        """shap_model2 raw dict의 items에 side("improve"/"maintain") 필드를 추가한다.

        m2_in_normal 게이트로 분류 — 정상범위 밖이면 "improve", 내이면 "maintain".
        var_key(DB 저장 키)를 우선 사용; 없으면 feature 한글 라벨로 M2_LABEL 역조회.
        """
        if not shap2_raw or not isinstance(shap2_raw, dict):
            return shap2_raw
        items = shap2_raw.get("items", [])
        if not items:
            return shap2_raw
        _rev: dict[str, str] = {v: k for k, v in M2_LABEL.items()}
        enriched_items = []
        for item in items:
            if not isinstance(item, dict):
                enriched_items.append(item)
                continue
            entry = dict(item)
            var = entry.get("var_key") or _rev.get(entry.get("feature", ""))
            val = float(entry.get("value", 0.0))
            in_normal = m2_in_normal(var, val, gender_int) if var else False
            entry["side"] = "maintain" if in_normal else "improve"
            enriched_items.append(entry)
        return {**shap2_raw, "items": enriched_items}

    @staticmethod
    def _model1_summary(
        app_group: AppGroup | None,
        egfr: float | None,
        shap_model1: list,
    ) -> str:
        """app_group·eGFR·상위 위험변수 1~2개 기반 종합 한 줄 요약.

        의료 진단이 아닌 선별(스크리닝) 참고 정보임을 톤에 반영.
        """
        if app_group is None:
            return ""

        top_features: list[str] = []
        if shap_model1:
            classified = classify_shap_items(shap_model1)
            top_features = [
                it.get("feature", "") if isinstance(it, dict) else it.feature for it in classified["raise_items"][:2]
            ]

        # 라벨 한국어 매핑 (노트북 M1_LABEL 기반)
        label_ko = {
            "sbp": "수축기혈압",
            "dbp": "이완기혈압",
            "fasting_glucose": "공복혈당",
            "total_cholesterol": "총콜레스테롤",
            "ldl_cholesterol": "LDL 콜레스테롤",
            "hdl_cholesterol": "HDL 콜레스테롤",
            "triglycerides": "중성지방",
            "ast": "간 효소(AST)",
            "alt": "간 효소(ALT)",
            "hemoglobin": "헤모글로빈",
            "urine_protein_qual": "요단백",
            "urine_glucose": "요당",
            "waist_cm": "허리둘레",
            "bmi": "체질량지수(BMI)",
            "creatinine": "크레아티닌",
            "smoking_current": "흡연",
        }
        top_ko = [label_ko.get(f, f) for f in top_features]
        factor_str = "·".join(top_ko) if top_ko else ""

        egfr_str = f" (eGFR {egfr:.1f} mL/min/1.73m²)" if egfr is not None else ""

        group_title_map = {
            AppGroup.G1: "신장 집중 관리 위험군",
            AppGroup.G2: "신장 위험 관리 위험군",
            AppGroup.G3: "신장 사전 관리 위험군",
            AppGroup.G4: "건강 습관 형성군",
        }
        group_title = group_title_map.get(app_group, str(app_group))

        if app_group == AppGroup.G1:
            base = f"신장 기능 저하{egfr_str}가 감지된 {group_title}에 해당합니다."
        elif app_group == AppGroup.G2:
            base = f"신장 기능은 정상이나 임상 위험인자가 있는 {group_title}에 해당합니다."
        elif app_group == AppGroup.G3:
            base = f"뚜렷한 임상 이상은 없으나 AI 모델이 위험 신호를 감지한 {group_title}에 해당합니다."
        else:
            base = f"현재 신장 관련 위험 신호가 낮은 {group_title}입니다."

        if factor_str:
            base += f" 주요 위험 요인: {factor_str}."

        base += " 본 결과는 의료 진단이 아닌 선별(스크리닝) 참고 정보입니다."
        return base

    # ── A2: 임상·생활습관 상세표 + 리포트 메타 빌더 ──────────────────────────

    @staticmethod
    def _build_clinical_items(hc: HealthCheck, ls: LifestyleSurvey | None, gender: int) -> list[ClinicalItem]:
        """모델1 임상 항목 상세표 구성.

        판단:
        - pulse_pressure = sbp - dbp (sbp·dbp는 항상 존재)
        - ldl_cholesterol: Friedewald 공식 (total - hdl - trig/5). 세 값 모두 존재 AND trig < 400 일 때만 포함.
        - smoking_current: ls 없으면 생략 (검진 데이터에 흡연 컬럼 없음).
        - waist_height_ratio: waist_circumference AND height 모두 있어야 계산.
        - 값이 None인 항목은 모두 생략.
        - 정렬: M1_CAT_ORDER(카테고리) 순, 카테고리 내부는 아래 _M1_FEAT_ORDER 고정 순서.
        """
        # 카테고리 내부 항목 순서
        m1_feat_order: dict[str, int] = {
            "sbp": 0,
            "dbp": 1,
            "fasting_glucose": 2,
            "pulse_pressure": 3,
            "total_cholesterol": 4,
            "ldl_cholesterol": 5,
            "hdl_cholesterol": 6,
            "triglycerides": 7,
            "creatinine": 8,
            "waist_cm": 9,
            "bmi": 10,
            "waist_height_ratio": 11,
            "smoking_current": 12,
            "ast": 13,
            "alt": 14,
            "hemoglobin": 15,
            "urine_protein_qual": 16,
            "urine_glucose": 17,
        }

        # 원시 값 수집
        raw: dict[str, float | None] = {
            "sbp": float(hc.systolic_bp),
            "dbp": float(hc.diastolic_bp),
            "pulse_pressure": float(hc.systolic_bp - hc.diastolic_bp),
            "fasting_glucose": hc.fasting_glucose,
            "total_cholesterol": hc.total_cholesterol,
            "hdl_cholesterol": hc.hdl_cholesterol,
            "triglycerides": hc.triglycerides,
            "creatinine": hc.creatinine,
            "bmi": hc.bmi,
            "waist_cm": hc.waist_circumference,
        }

        # waist_height_ratio: 허리둘레·신장 모두 있을 때만 계산
        if hc.waist_circumference is not None and hc.height and hc.height > 0:
            raw["waist_height_ratio"] = round(hc.waist_circumference / hc.height, 4)
        else:
            raw["waist_height_ratio"] = None

        # LDL: 입력값 우선, 없으면 Friedewald(total - hdl - trig/5, trig<400)
        raw["ldl_cholesterol"] = HealthCheckService._effective_ldl(hc)

        # 흡연: SmokingStatus enum → 0/1/2 (NEVER=0, PAST=1, CURRENT=2)
        if ls is not None:
            smoke_map = {SmokingStatus.NEVER: 0, SmokingStatus.PAST: 1, SmokingStatus.CURRENT: 2}
            raw["smoking_current"] = float(smoke_map.get(ls.smoking_status, 0))
        else:
            raw["smoking_current"] = None

        raw["ast"] = hc.ast
        raw["alt"] = hc.alt
        raw["hemoglobin"] = hc.hemoglobin
        raw["urine_protein_qual"] = (
            1.0
            if hc.urine_protein == UrineResult.POSITIVE
            else 0.0
            if hc.urine_protein == UrineResult.NEGATIVE
            else None
        )
        raw["urine_glucose"] = (
            1.0
            if hc.urine_glucose == UrineResult.POSITIVE
            else 0.0
            if hc.urine_glucose == UrineResult.NEGATIVE
            else None
        )

        items: list[ClinicalItem] = []
        for feature, val in raw.items():
            if val is None:
                continue
            status_label, status_level = m1_status(feature, val, gender)
            dis_low, dis_high = M1_DISEASE.get(feature, ("", ""))
            items.append(
                ClinicalItem(
                    feature=feature,
                    label=M1_LABEL.get(feature, feature),
                    desc=M1_DESC.get(feature, ""),
                    category=M1_CATEGORY.get(feature, "기타"),
                    normal_range=m1_normal_range(feature, gender),
                    value_text=m1_format(feature, val),
                    status=status_label,
                    status_level=status_level,
                    direction=m1_direction(feature, val, gender),
                    disease_low=dis_low,
                    disease_high=dis_high,
                )
            )

        # M1_CAT_ORDER → 카테고리 내부 _M1_FEAT_ORDER 순 정렬
        cat_idx = {cat: i for i, cat in enumerate(M1_CAT_ORDER)}
        items.sort(key=lambda ci: (cat_idx.get(ci.category, 99), m1_feat_order.get(ci.feature, 99)))
        return items

    @staticmethod
    def _build_lifestyle_items(hc: HealthCheck, ls: LifestyleSurvey | None, gender: int) -> list[LifestyleItem]:
        """모델2 생활습관 항목 상세표 구성.

        판단:
        - 혈액/신체 지표(bmi, waist_cm, hdl, ldl, trig)는 HealthCheck에서 가져옴.
        - 활동 지표(sitting_hours, walking_days, moderate_days, vigorous_days, smoking_current)는 ls에서 가져옴.
        - ls 없으면 활동 지표 전체 생략.
        - ldl_cholesterol: Friedewald 조건 동일 (trig < 400).
        - 그룹 분류: m2_in_normal 정상범위 내 → 'maintain', 벗어남 → 'improve'.
          (노트북은 SHAP 부호도 고려하는 엣지 케이스가 있으나, 상세표 목적상 정상범위 기준 단순화 — 의도적 단순화.)
        - value_text: 운동/좌식은 소수점 1자리, 흡연은 텍스트.
        """
        # 모델2 항목별 원시 값 수집
        raw: dict[str, float | None] = {
            "bmi": hc.bmi,
            "waist_cm": hc.waist_circumference,
            "hdl_cholesterol": hc.hdl_cholesterol,
            "triglycerides": hc.triglycerides,
        }

        # LDL: 입력값 우선, 없으면 Friedewald (모델2에서도 동일 조건)
        raw["ldl_cholesterol"] = HealthCheckService._effective_ldl(hc)

        # 생활습관 설문 의존 항목
        if ls is not None:
            raw["sitting_hours"] = ls.sitting_hours_per_day  # float | None
            raw["walking_days"] = float(ls.exercise_days_per_week)  # 걷기 = 일반 운동일수
            raw["moderate_days"] = float(ls.moderate_exercise_days)
            raw["vigorous_days"] = float(ls.vigorous_exercise_days)
            smoke_map = {SmokingStatus.NEVER: 0, SmokingStatus.PAST: 1, SmokingStatus.CURRENT: 2}
            raw["smoking_current"] = float(smoke_map.get(ls.smoking_status, 0))
        # else: 위 항목들은 raw에 없음 → 아래 루프에서 자동 생략

        items: list[LifestyleItem] = []
        # 모델2 항목 순서 유지
        m2_features = [
            "bmi",
            "waist_cm",
            "hdl_cholesterol",
            "ldl_cholesterol",
            "triglycerides",
            "sitting_hours",
            "walking_days",
            "moderate_days",
            "vigorous_days",
            "smoking_current",
        ]
        for feature in m2_features:
            val = raw.get(feature)
            if val is None:
                continue
            status_label, status_level = m2_status(feature, val, gender)
            nr = m2_normal_range(feature, gender)
            # value_text: 흡연은 텍스트, 나머지는 소수점 1자리
            if feature == "smoking_current":
                vtext = {0: "비흡연", 1: "과거 흡연", 2: "현재 흡연"}.get(int(val), str(int(val)))
            else:
                vtext = f"{val:.1f}"
            in_normal = m2_in_normal(feature, val, gender)
            group = "maintain" if in_normal else "improve"
            action = "" if in_normal else m2_improve_action(feature)
            items.append(
                LifestyleItem(
                    feature=feature,
                    label=m2_label(feature),
                    normal_range=nr,
                    value_text=vtext,
                    status=status_label,
                    status_level=status_level,
                    group=group,
                    action=action,
                    domain=m2_domain(feature),
                )
            )
        return items

    @staticmethod
    def _build_lifestyle_domain_summary(
        items: list[LifestyleItem],
    ) -> list[LifestyleDomainSummary]:
        """생활습관 항목을 도메인별로 묶어 핵심요약 생성. 항상 DOMAIN_ORDER 3개.

        improve 그룹 라벨을 모아 한 줄 요약. 개선항목 0건 도메인은 '양호합니다'.
        """
        summaries: list[LifestyleDomainSummary] = []
        for domain in DOMAIN_ORDER:
            improve_labels = [it.label for it in items if it.domain == domain and it.group == "improve"]
            summaries.append(
                LifestyleDomainSummary(
                    domain=domain,
                    domain_label=DOMAIN_LABEL[domain],
                    improve_count=len(improve_labels),
                    summary=build_domain_summary_text(improve_labels),
                )
            )
        return summaries

    @staticmethod
    def _build_report_meta(hc: HealthCheck, user: User, ls: LifestyleSurvey | None) -> ReportMeta:
        """리포트 메타 구성.

        판단:
        - grade: G1→높음, G2→주의, G3→주의, G4→낮음. (G2 내 '더 높은' 서브타입 구분은 진단 로직 필요 — 단순화.)
        - age: User.birthday DateField에서 오늘 날짜로 만 나이 계산.
        - gender: Gender.MALE→"남성", Gender.FEMALE→"여성".
        - conditions: ls.htn_diagnosed / dm_diagnosed / dyslipidemia_diagnosed / ckd_diagnosed.
        - family_history: ls.family_history_diabetes / hypertension / heart_disease.
        - peer_top_pct / peer_relative: hc.shap_model2 dict에서 조회 (None 안전).
        - score: ckd_risk_score * 100, 소수점 1자리.
        """
        group = hc.app_group  # AppGroup enum or None
        group_str = group.value if group is not None else None
        # app AppGroup(G1~G4) ↔ 노트북 참조 그룹(A~D): G1=A·G2=B·G3=C·G4=D
        letter = {"G1": "A", "G2": "B", "G3": "C", "G4": "D", "CKD": "CKD", "DIALYSIS": "DIALYSIS"}.get(
            group_str or "", ""
        )

        grade_map = {"G1": "높음", "G2": "주의", "G3": "주의", "G4": "낮음", "CKD": "CKD 진단", "DIALYSIS": "투석·이식"}
        grade = grade_map.get(group_str or "", "낮음")

        score = round(hc.ckd_risk_score * 100, 1) if hc.ckd_risk_score is not None else None

        # 만 나이 계산 (birthday DateField)
        age: int | None = None
        if user.birthday is not None:
            today = datetime.date.today()
            bd = user.birthday
            age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))

        gender_str = "남성" if user.gender == Gender.MALE else "여성"

        conditions: list[str] = []
        family_hist: list[str] = []
        if ls is not None:
            if ls.htn_diagnosed:
                conditions.append("고혈압")
            if ls.dm_diagnosed:
                conditions.append("당뇨")
            if ls.dyslipidemia_diagnosed:
                conditions.append("이상지질혈증")
            if ls.ckd_diagnosed:
                conditions.append("CKD")
            if ls.family_history_hypertension:
                family_hist.append("고혈압")
            if ls.family_history_diabetes:
                family_hist.append("당뇨")
            if ls.family_history_heart_disease:
                family_hist.append("심장질환")

        # shap_model2에서 또래 비교 정보 추출 (없으면 None)
        shap2 = hc.shap_model2 or {}
        peer_top_pct = shap2.get("peer_top_pct") if isinstance(shap2, dict) else None
        peer_relative = shap2.get("peer_relative") if isinstance(shap2, dict) else None

        return ReportMeta(
            group=group_str,
            group_title=m1_group_title(letter),
            grade=grade,
            score=score,
            group_message=m1_group_message(letter),
            age=age,
            gender=gender_str,
            conditions=conditions,
            family_history=family_hist,
            peer_top_pct=peer_top_pct,
            peer_relative=peer_relative,
            report_available=group_str not in ("CKD", "DIALYSIS"),
        )

    async def get_report(
        self,
        *,
        health_check_id: int,
        user_id: int,
    ) -> ReportResponse | None:
        """SHAP 리포트 조회.

        user_id 소유권 필터로 타인 검진 접근 차단.
        ai_guide는 ai_worker가 예측 시 선생성·저장한 캐시를 읽는다(미생성 시 빈 문자열).
        A2 추가: clinical_items, lifestyle_items, report_meta 빌드 (기존 필드 불변).
        """
        hc = await HealthCheck.filter(id=health_check_id, user_id=user_id).first()
        if hc is None:
            return None

        # 사용자 정보 및 최신 생활습관 설문 로드 (같은 날 재제출 시 최신 보장 — id tiebreaker)
        user = await User.get(id=user_id)
        ls = await LifestyleSurvey.filter(user_id=user_id).order_by("-surveyed_date", "-id").first()

        # gender int 변환: MALE=1, FEMALE=0
        gender_int = 1 if user.gender == Gender.MALE else 0

        shap_list = self._enrich_shap_status(hc.shap_model1 or [], gender_int)
        shap_list = self._enrich_m1_side(shap_list)
        recommended = self._recommend_tests(
            hc.app_group,
            sbp=hc.systolic_bp,
            dbp=hc.diastolic_bp,
            fasting_glucose=hc.fasting_glucose,
            hemoglobin=hc.hemoglobin,
            urine_protein=hc.urine_protein,
            gender_int=gender_int,
            htn_dx=bool(ls.htn_diagnosed) if ls else False,
            dm_dx=bool(ls.dm_diagnosed) if ls else False,
        )
        summary = self._model1_summary(hc.app_group, hc.egfr_estimated, shap_list)

        clinical_items = self._build_clinical_items(hc, ls, gender_int)
        lifestyle_items = self._build_lifestyle_items(hc, ls, gender_int)
        lifestyle_domain_summary = self._build_lifestyle_domain_summary(lifestyle_items)
        report_meta = self._build_report_meta(hc, user, ls)
        shap2_enriched = self._enrich_m2_side(hc.shap_model2, gender_int)
        # 표시용 클램프 — lifestyle_score는 양(+) SHAP 합이라 1.0을 초과할 수 있음
        # 웹·PDF 모두 * 100 후 "/100"으로 표시하므로, raw 값을 여기서 1.0 상한으로 제한.
        # 게이트·SHAP·피어 비교 로직은 ai-worker에서 이미 완료 → 여기서 건드려도 안전.
        if isinstance(shap2_enriched, dict) and "lifestyle_score" in shap2_enriched:
            shap2_enriched["lifestyle_score"] = max(0.0, min(1.0, float(shap2_enriched["lifestyle_score"])))

        return ReportResponse(
            health_check_id=hc.id,
            shap_model1=shap_list,
            shap_model2=shap2_enriched,
            ai_guide=hc.ai_guide or "",  # ai_worker가 선생성·저장 → 읽기만
            recommended_tests=recommended,
            model1_summary=summary,
            clinical_items=clinical_items,
            lifestyle_items=lifestyle_items,
            lifestyle_domain_summary=lifestyle_domain_summary,
            report_meta=report_meta,
        )
