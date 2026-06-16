from enum import StrEnum

from tortoise import fields, models


class CkdStage(StrEnum):
    G1 = "G1"  # eGFR >= 90  (정상 or 고위험 경계)
    G2 = "G2"  # eGFR 60~89  (경증 감소)
    G3A = "G3A"  # eGFR 45~59  (경~중등도)
    G3B = "G3B"  # eGFR 30~44  (중~중증도)
    G4 = "G4"  # eGFR 15~29  (중증)
    G5 = "G5"  # eGFR < 15   (신부전)


class AppGroup(StrEnum):
    """ML 모델(Model 1) 출력 그룹 — KDIGO 단계와 별개 (REQ-ML-003)."""

    G1 = "G1"  # eGFR < 60 → Track A (케어)
    G2 = "G2"  # eGFR >= 60 + 임상 마커 → Track A (케어)
    G3 = "G3"  # 위험점수 >= 임계값 → Track B (일반)
    G4 = "G4"  # 정상 → Track B (일반)
    CKD = "CKD"  # CKD 진단 + 투석 안함 → 비투석(보존기) 트랙
    DIALYSIS = "DIALYSIS"  # CKD 진단 + 혈액투석/복막투석/이식 → 투석·이식 트랙


class DialysisType(StrEnum):
    """투석 종류 (RAG 트랙 필터용). null=미진단."""

    NONE = "none"  # 진단받았으나 투석 안 함(비투석)
    HEMODIALYSIS = "hemodialysis"  # 혈액투석
    PERITONEAL = "peritoneal"  # 복막투석
    TRANSPLANT = "transplant"  # 이식


class UrineResult(StrEnum):
    """요검사 정성 결과 (요단백·요당)."""

    POSITIVE = "POSITIVE"  # 양성(의심)
    NEGATIVE = "NEGATIVE"  # 음성(정상)


class HealthCheck(models.Model):
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="health_checks")
    checked_date = fields.DateField(description="검진일")

    # 혈압 (mmHg)
    systolic_bp = fields.IntField(description="수축기혈압")
    diastolic_bp = fields.IntField(description="이완기혈압")

    # 혈액 검사
    fasting_glucose = fields.FloatField(description="공복혈당 mg/dL")
    creatinine = fields.FloatField(null=True, description="혈청 크레아티닌 mg/dL")
    total_cholesterol = fields.FloatField(null=True, description="총 콜레스테롤 mg/dL")
    hdl_cholesterol = fields.FloatField(null=True, description="HDL 콜레스테롤 mg/dL")
    triglycerides = fields.FloatField(null=True, description="중성지방 mg/dL")
    ldl_cholesterol = fields.FloatField(
        null=True, description="LDL 콜레스테롤 mg/dL (입력값; 미입력 시 Friedewald 계산)"
    )
    hemoglobin = fields.FloatField(null=True, description="헤모글로빈 g/dL")
    ast = fields.FloatField(null=True, description="AST U/L")
    alt = fields.FloatField(null=True, description="ALT U/L")
    urine_protein = fields.CharEnumField(enum_type=UrineResult, null=True, description="요단백")
    urine_glucose = fields.CharEnumField(enum_type=UrineResult, null=True, description="요당")

    # 신체 측정
    weight = fields.FloatField(description="체중 kg")
    height = fields.FloatField(description="신장 cm")
    bmi = fields.FloatField(description="체질량지수 (서비스에서 자동 계산)")
    waist_circumference = fields.FloatField(null=True, description="허리둘레 cm")

    # AI / CKD-EPI 예측 결과 — ai_worker 또는 서비스가 비동기로 채움
    egfr_estimated = fields.FloatField(null=True, description="추정 eGFR mL/min/1.73m²")
    ckd_risk_score = fields.FloatField(null=True, description="ML 모델 CKD 위험도 0.0~1.0")
    ckd_stage = fields.CharEnumField(enum_type=CkdStage, null=True)
    app_group = fields.CharEnumField(enum_type=AppGroup, null=True, description="ML 모델 배정 그룹 (REQ-ML-003)")

    # SHAP 리포트 (ai_worker 예측 job이 비동기로 채움)
    shap_model1 = fields.JSONField(null=True, description="모델1 위험변수 SHAP Top-N")
    shap_model2 = fields.JSONField(null=True, description="모델2 생활습관 SHAP + 또래비교")
    # AI 행동 가이드 (ai_worker가 예측 직후 비동기 선생성·저장 — 리포트는 읽기만)
    ai_guide = fields.TextField(null=True, description="RAG 기반 AI 행동 가이드(선생성 캐시)")
    # 투석 종류 — RAG 챗봇 트랙 필터용(투석/비투석 식이 권고 분기). null=미진단.
    dialysis_type = fields.CharEnumField(enum_type=DialysisType, null=True, description="투석 종류 (null=미진단)")

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "health_checks"
        ordering = ["-checked_date"]
