from datetime import date

from app.models.health_check import AppGroup, CkdStage, DialysisType, HealthCheck


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
        """사용자의 검진 이력 목록 (최신 검진일 기준 내림차순)."""
        qs = HealthCheck.filter(user_id=user_id)
        total = await qs.count()
        items = await qs.order_by("-checked_date").offset(offset).limit(limit)
        return total, items

    async def get_by_id(self, health_check_id: int, user_id: int) -> HealthCheck | None:
        """단건 조회 — user_id 조건으로 타인 검진 접근 차단."""
        return await HealthCheck.get_or_none(id=health_check_id, user_id=user_id)

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
