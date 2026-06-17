from datetime import date

from app.models.health_check import AppGroup, CkdStage, DialysisType, HealthCheck, UrineResult


class HealthCheckRepository:
    async def create(
        self,
        user_id: int,
        checked_date: date,
        systolic_bp: int,
        diastolic_bp: int,
        fasting_glucose: float,
        weight: float,
        height: float,
        bmi: float,
        creatinine: float | None = None,
        total_cholesterol: float | None = None,
        hdl_cholesterol: float | None = None,
        triglycerides: float | None = None,
        ldl_cholesterol: float | None = None,
        hemoglobin: float | None = None,
        ast: float | None = None,
        alt: float | None = None,
        urine_protein: UrineResult | None = None,
        urine_glucose: UrineResult | None = None,
        waist_circumference: float | None = None,
        egfr_estimated: float | None = None,
        ckd_stage: CkdStage | None = None,
        app_group: AppGroup | None = None,
        dialysis_type: DialysisType | None = None,
    ) -> HealthCheck:
        return await HealthCheck.create(
            user_id=user_id,
            checked_date=checked_date,
            systolic_bp=systolic_bp,
            diastolic_bp=diastolic_bp,
            fasting_glucose=fasting_glucose,
            creatinine=creatinine,
            total_cholesterol=total_cholesterol,
            hdl_cholesterol=hdl_cholesterol,
            triglycerides=triglycerides,
            ldl_cholesterol=ldl_cholesterol,
            hemoglobin=hemoglobin,
            ast=ast,
            alt=alt,
            urine_protein=urine_protein,
            urine_glucose=urine_glucose,
            weight=weight,
            height=height,
            bmi=bmi,
            waist_circumference=waist_circumference,
            egfr_estimated=egfr_estimated,
            ckd_stage=ckd_stage,
            app_group=app_group,
            dialysis_type=dialysis_type,
        )

    async def get_by_user(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[int, list[HealthCheck]]:
        """사용자의 검진 이력 목록 (최신 검진일 기준 내림차순, 같은 날짜면 최근 생성분 우선)."""
        qs = HealthCheck.filter(user_id=user_id)
        total = await qs.count()
        # 같은 checked_date가 여러 건이면 id 내림차순으로 가장 최근 검진이 먼저 오게 한다
        # (리포트가 '최신 검진'으로 가장 최근 생성분을 집도록 — 같은 날 재검진 대비)
        items = await qs.order_by("-checked_date", "-id").offset(offset).limit(limit)
        return total, items

    async def get_by_id(self, health_check_id: int, user_id: int) -> HealthCheck | None:
        """단건 조회 — user_id 조건으로 타인 검진 접근 차단."""
        return await HealthCheck.get_or_none(id=health_check_id, user_id=user_id)

    async def delete_by_id(self, health_check_id: int, user_id: int) -> bool:
        """단건 삭제 — user_id 조건으로 타인 소유분 보호. 영향 행 수 > 0 이면 True."""
        deleted = await HealthCheck.filter(id=health_check_id, user_id=user_id).delete()
        return deleted > 0

    async def delete_all_by_user(self, user_id: int) -> int:
        """본인 검진 전부 삭제. 삭제된 행 수 반환."""
        return await HealthCheck.filter(user_id=user_id).delete()

    async def update_by_id(
        self,
        health_check_id: int,
        user_id: int,
        **fields,
    ) -> HealthCheck | None:
        """단건 부분 업데이트 — user_id 조건으로 타인 소유분 보호."""
        hc = await HealthCheck.get_or_none(id=health_check_id, user_id=user_id)
        if hc is None:
            return None
        for key, value in fields.items():
            setattr(hc, key, value)
        await hc.save()
        return hc

    async def update_prediction(
        self,
        health_check_id: int,
        egfr_estimated: float | None = None,
        ckd_risk_score: float | None = None,
        ckd_stage: CkdStage | None = None,
    ) -> HealthCheck | None:
        """ai_worker가 ML 예측 완료 후 결과를 채울 때 사용."""
        hc = await HealthCheck.get_or_none(id=health_check_id)
        if hc is None:
            return None
        if egfr_estimated is not None:
            hc.egfr_estimated = egfr_estimated
        if ckd_risk_score is not None:
            hc.ckd_risk_score = ckd_risk_score
        if ckd_stage is not None:
            hc.ckd_stage = ckd_stage
        await hc.save()
        return hc
