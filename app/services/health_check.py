from app.core.logger import setup_logger
from app.dtos.health_check import (
    HealthCheckCreateRequest,
    HealthCheckListResponse,
    HealthCheckResponse,
    ReportResponse,
)
from app.models.health_check import AppGroup, CkdStage, HealthCheck
from app.models.safety_event import SafetyEvent, SafetyEventType
from app.models.users import Gender
from app.repositories.health_check_repository import HealthCheckRepository
from app.services import ckd_publisher, report_guide

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
    ) -> AppGroup:
        """규칙 기반 AppGroup 배정 (설계서 § 4, 우선순위 G1→G2→G4).

        G3는 Model 1 score 필요 — AI 팀 연동 전까지 G4로 fallback.
        htn_diagnosed / dm_diagnosed 미수집 — 추후 식이설문 연동 시 보완 예정.
        """
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

        app_group = self._assign_app_group(egfr, dto.systolic_bp, dto.diastolic_bp, dto.fasting_glucose)

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
            weight=dto.weight,
            height=dto.height,
            bmi=bmi,
            waist_circumference=dto.waist_circumference,
            egfr_estimated=egfr,
            ckd_stage=ckd_stage,
            app_group=app_group,
        )

        safety_warning = self._check_safety_warning(dto.systolic_bp, dto.diastolic_bp, dto.fasting_glucose, egfr)

        # 위험 감지 시 SafetyEvent 영구 기록 (관리자 모니터링용)
        await self._record_safety_events(user_id=user_id, health_check=hc, dto=dto, egfr=egfr)

        # 비동기 CKD 예측 job 발행 — 실패해도 검진 저장은 유지(graceful)
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

    # ── 모델1 리포트 헬퍼 (순수 함수, app_group 기반) ─────────────────────────

    @staticmethod
    def _recommend_tests(app_group: AppGroup | None, egfr: float | None) -> list[str]:
        """app_group(G1~G4) 기반 권장 검사 리스트.

        노트북 m1_recommended_tests 로직 참고 (셀12·251~268줄).
        서비스에 요단백 컬럼이 없어 app_group + eGFR 기반으로 단순화.
        톤: 선별 서비스 — "진단"·"환자" 단정 표현 배제.
        """
        if app_group is None:
            return []

        if app_group == AppGroup.G1:
            # eGFR < 60 → 신장 기능 저하 의심 → 정밀 추적 필요
            tests = [
                "eGFR·혈청 크레아티닌 재검(3개월 내)",
                "요단백(소변 알부민/크레아티닌비) 검사",
                "신장내과 상담 권고",
            ]
            # eGFR이 매우 낮을 경우 혈압·빈혈 동반 평가 추가
            if egfr is not None and egfr < 45:
                tests.append("혈압 정밀 모니터링 및 빈혈(헤모글로빈) 확인")
            return tests

        if app_group == AppGroup.G2:
            # eGFR ≥ 60 + 임상 마커(혈압·혈당) 이상 → 위험인자 관리 중심
            return [
                "eGFR·혈청 크레아티닌 정기 재검(6개월 내)",
                "혈압 정밀 측정 및 관리 상태 확인",
                "공복혈당·당화혈색소(HbA1c) 검사",
                "요단백(소변) 선별 검사",
            ]

        if app_group == AppGroup.G3:
            # 위험점수 임계 이상 — 뚜렷한 임상 이상은 없으나 모델이 위험 신호 감지
            return [
                "생활습관 개선 후 신장 기능 재평가",
                "연 1~2회 eGFR·공복혈당 정기 검사",
                "혈압 자가 모니터링",
            ]

        # G4: 정상
        return [
            "현 상태 유지",
            "연 1회 정기 건강검진 권장",
        ]

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

        # 상위 위험변수 추출 (shap > 0, feature 기준 상위 2개)
        top_features: list[str] = []
        if shap_model1:
            # shap_model1은 dict list (feature, shap, value, note)
            positive_items = [item for item in shap_model1 if isinstance(item, dict) and item.get("shap", 0) > 0]
            positive_items.sort(key=lambda x: x.get("shap", 0), reverse=True)
            top_features = [item["feature"] for item in positive_items[:2] if "feature" in item]

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

    async def get_report(
        self,
        *,
        health_check_id: int,
        user_id: int,
    ) -> ReportResponse | None:
        """SHAP 리포트 조회 + RAG 기반 AI 행동 가이드 생성.

        user_id 소유권 필터로 타인 검진 접근 차단.
        RAG 가이드 생성 실패·타임아웃 시 ai_guide="" 로 리포트는 정상 반환.
        """
        hc = await HealthCheck.filter(id=health_check_id, user_id=user_id).first()
        if hc is None:
            return None

        # eGFR·체중을 user_context로 전달 → RAG가 영양 권장량 개인화 환산에 활용
        user_ctx: dict = {}
        if hc.egfr_estimated is not None:
            user_ctx["eGFR"] = hc.egfr_estimated
        if hc.weight is not None:
            user_ctx["weight"] = hc.weight

        guide = await report_guide.generate_guide(
            hc.shap_model1 or [],
            hc.shap_model2,
            user_ctx,
        )

        shap_list = hc.shap_model1 or []
        recommended = self._recommend_tests(hc.app_group, hc.egfr_estimated)
        summary = self._model1_summary(hc.app_group, hc.egfr_estimated, shap_list)

        return ReportResponse(
            health_check_id=hc.id,
            shap_model1=shap_list,
            shap_model2=hc.shap_model2,  # dict 또는 None → LifestyleShap 검증
            ai_guide=guide,
            recommended_tests=recommended,
            model1_summary=summary,
        )
