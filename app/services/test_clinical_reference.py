"""
clinical_reference.py 단위 테스트
- 순수 모듈 테스트 (DB·외부 의존 없음)
- app/tests/conftest.py 범위 밖에 위치 → 운영DB drop 위험 없음
"""

from app.services.clinical_reference import (
    build_domain_summary_text,
    m1_direction,
    m1_format,
    m1_group_message,
    m1_group_title,
    m1_normal_range,
    m1_status,
    m1_unit,
    m2_domain,
    m2_improve_action,
    m2_in_normal,
    m2_label,
    m2_maintain_msg,
    m2_normal_range,
    m2_status,
)

# ──────────────────────────────────────────────────────────────────────────────
# 모델1 — m1_status
# ──────────────────────────────────────────────────────────────────────────────


class TestM1Status:
    def test_sbp_normal(self):
        label, level = m1_status("sbp", 110, gender=1)
        assert label == "정상"
        assert level == "good"

    def test_sbp_caution(self):
        label, level = m1_status("sbp", 135, gender=1)
        assert label == "주의"
        assert level == "caution"

    def test_sbp_danger(self):
        label, level = m1_status("sbp", 145, gender=1)
        assert label == "위험"
        assert level == "danger"

    def test_hdl_caution_boundary(self):
        # 48 mg/dL → 40~60 구간 → '주의'
        label, level = m1_status("hdl_cholesterol", 48, gender=0)
        assert label == "주의"
        assert level == "caution"

    def test_hdl_low_is_danger(self):
        # 38 mg/dL → 0~40 구간 → '낮음'. HDL 낮음=좋은 콜레스테롤 부족→심혈관 위험.
        # (항목,라벨) 예외 M1_STATUS_LEVEL_OVERRIDE로 danger 처리 (주니 결정 2026-06-09).
        # 크레아티닌·맥압 '낮음'은 caution 유지(아래 별도 테스트).
        label, level = m1_status("hdl_cholesterol", 38, gender=1)
        assert label == "낮음"
        assert level == "danger"

    def test_creatinine_high_is_danger(self):
        # 1.42 mg/dL → 1.4~99 → '높음'
        label, level = m1_status("creatinine", 1.42, gender=1)
        assert label == "높음"
        assert level == "danger"

    def test_creatinine_normal(self):
        label, level = m1_status("creatinine", 0.9, gender=1)
        assert label == "정상"
        assert level == "good"

    def test_waist_cm_obese_female(self):
        # 여성 85cm 기준 → 88 cm → '복부비만'
        label, level = m1_status("waist_cm", 88, gender=0)
        assert label == "복부비만"
        assert level == "danger"

    def test_waist_cm_normal_male(self):
        # 남성 90cm 기준 → 88 cm → '정상'
        label, level = m1_status("waist_cm", 88, gender=1)
        assert label == "정상"
        assert level == "good"

    def test_waist_cm_obese_male(self):
        label, level = m1_status("waist_cm", 92, gender=1)
        assert label == "복부비만"
        assert level == "danger"

    def test_bmi_underweight(self):
        label, level = m1_status("bmi", 17.2, gender=1)
        assert label == "저체중"
        assert level == "info"

    def test_bmi_mild_obese(self):
        label, level = m1_status("bmi", 26, gender=1)
        assert label == "경도 비만"
        assert level == "warnLight"

    def test_smoking_nonsmoker(self):
        label, level = m1_status("smoking_current", 0, gender=1)
        assert label == "비흡연"
        assert level == "good"

    def test_smoking_current(self):
        label, level = m1_status("smoking_current", 2, gender=1)
        assert label == "현재 흡연"
        assert level == "danger"

    def test_triglycerides_high(self):
        label, level = m1_status("triglycerides", 218, gender=1)
        assert label == "높음"
        assert level == "danger"

    def test_ldl_very_high(self):
        label, level = m1_status("ldl_cholesterol", 200, gender=1)
        assert label == "매우 높음"
        assert level == "danger"

    def test_pulse_pressure_low(self):
        # 35 mmHg → 0~40 → '낮음' → #fef9e7 → caution
        label, level = m1_status("pulse_pressure", 35, gender=1)
        assert label == "낮음"
        assert level == "caution"

    def test_pulse_pressure_normal(self):
        label, level = m1_status("pulse_pressure", 50, gender=1)
        assert label == "정상"
        assert level == "good"


# ──────────────────────────────────────────────────────────────────────────────
# 모델1 — m1_direction
# ──────────────────────────────────────────────────────────────────────────────


class TestM1Direction:
    def test_sbp_high(self):
        assert m1_direction("sbp", 145, gender=1) == "high"

    def test_sbp_normal(self):
        assert m1_direction("sbp", 115, gender=1) == "normal"

    def test_creatinine_low(self):
        # 0.4 < 0.5(정상 하한) → low
        assert m1_direction("creatinine", 0.4, gender=1) == "low"

    def test_creatinine_high(self):
        assert m1_direction("creatinine", 1.5, gender=1) == "high"

    def test_bmi_low(self):
        # 17.2 < 18.5(정상 하한) → low
        assert m1_direction("bmi", 17.2, gender=1) == "low"

    def test_bmi_normal(self):
        assert m1_direction("bmi", 21, gender=1) == "normal"

    def test_bmi_high(self):
        assert m1_direction("bmi", 25, gender=1) == "high"

    def test_smoking_high(self):
        assert m1_direction("smoking_current", 2, gender=1) == "high"

    def test_smoking_normal(self):
        assert m1_direction("smoking_current", 0, gender=1) == "normal"

    def test_fasting_glucose_high(self):
        assert m1_direction("fasting_glucose", 130, gender=1) == "high"

    def test_fasting_glucose_normal(self):
        assert m1_direction("fasting_glucose", 90, gender=1) == "normal"


# ──────────────────────────────────────────────────────────────────────────────
# 모델1 — m1_format
# ──────────────────────────────────────────────────────────────────────────────


class TestM1Format:
    def test_smoking_current_smoker(self):
        assert m1_format("smoking_current", 2) == "현재 흡연"

    def test_smoking_nonsmoker(self):
        assert m1_format("smoking_current", 0) == "비흡연"

    def test_smoking_ex_smoker(self):
        assert m1_format("smoking_current", 1) == "과거 흡연"

    def test_sbp_numeric(self):
        assert m1_format("sbp", 135.0) == "135.0"

    def test_bmi_decimal(self):
        assert m1_format("bmi", 22.35) == "22.4"

    def test_creatinine_decimal(self):
        assert m1_format("creatinine", 1.0) == "1.0"


# ──────────────────────────────────────────────────────────────────────────────
# 모델1 — m1_normal_range
# ──────────────────────────────────────────────────────────────────────────────


class TestM1NormalRange:
    def test_sbp(self):
        result = m1_normal_range("sbp", gender=1)
        assert result == "<120 mmHg"

    def test_dbp(self):
        result = m1_normal_range("dbp", gender=1)
        assert result == "<80 mmHg"

    def test_bmi(self):
        result = m1_normal_range("bmi", gender=1)
        assert result == "18.5–22.9 kg/m²"

    def test_waist_cm_male(self):
        result = m1_normal_range("waist_cm", gender=1)
        assert result == "<90 cm"

    def test_waist_cm_female(self):
        result = m1_normal_range("waist_cm", gender=0)
        assert result == "<85 cm"

    def test_waist_height_ratio_no_unit(self):
        result = m1_normal_range("waist_height_ratio", gender=1)
        assert result == "<0.5"

    def test_creatinine(self):
        result = m1_normal_range("creatinine", gender=1)
        assert result == "0.50~1.4 mg/dL"


# ──────────────────────────────────────────────────────────────────────────────
# 모델1 — m1_unit
# ──────────────────────────────────────────────────────────────────────────────


class TestM1Unit:
    def test_sbp(self):
        assert m1_unit("sbp") == "mmHg"

    def test_bmi(self):
        assert m1_unit("bmi") == "kg/m²"

    def test_smoking_current_no_unit(self):
        assert m1_unit("smoking_current") == ""


# ──────────────────────────────────────────────────────────────────────────────
# 모델1 — 그룹 메시지
# ──────────────────────────────────────────────────────────────────────────────


class TestM1Group:
    def test_group_title_a(self):
        assert m1_group_title("A") == "신장 집중 관리군"

    def test_group_title_d(self):
        assert m1_group_title("D") == "건강 습관 형성군"

    def test_group_message_a_contains(self):
        msg = m1_group_message("A")
        assert "신장내과" in msg

    def test_group_message_d_contains(self):
        msg = m1_group_message("D")
        assert "건강검진" in msg

    def test_group_message_unknown(self):
        assert m1_group_message("Z") == ""


# ──────────────────────────────────────────────────────────────────────────────
# 모델2 — m2_status
# ──────────────────────────────────────────────────────────────────────────────


class TestM2Status:
    def test_triglycerides_high(self):
        label, level = m2_status("triglycerides", 218, gender=1)
        assert label == "높음"
        assert level == "danger"

    def test_triglycerides_normal(self):
        label, level = m2_status("triglycerides", 100, gender=1)
        assert label == "적정"
        assert level == "good"

    def test_bmi_underweight(self):
        label, level = m2_status("bmi", 17.0, gender=1)
        assert label == "저체중"
        assert level == "info"

    def test_bmi_normal(self):
        label, level = m2_status("bmi", 21.0, gender=1)
        assert label == "정상"
        assert level == "good"

    def test_walking_days_good(self):
        label, level = m2_status("walking_days", 6, gender=1)
        assert label == "양호"
        assert level == "good"

    def test_walking_days_very_poor(self):
        label, level = m2_status("walking_days", 1, gender=1)
        assert label == "매우 부족"
        assert level == "danger"

    def test_smoking_nonsmoker(self):
        label, level = m2_status("smoking_current", 0, gender=1)
        assert label == "비흡연"
        assert level == "good"

    def test_smoking_smoker(self):
        label, level = m2_status("smoking_current", 1, gender=1)
        assert label == "흡연"
        assert level == "danger"


# ──────────────────────────────────────────────────────────────────────────────
# 모델2 — m2_in_normal
# ──────────────────────────────────────────────────────────────────────────────


class TestM2InNormal:
    def test_bmi_overweight_false(self):
        # 23.9 > 22.9 → 정상범위 벗어남
        assert m2_in_normal("bmi", 23.9, gender=1) is False

    def test_bmi_normal_true(self):
        assert m2_in_normal("bmi", 21.0, gender=1) is True

    def test_walking_days_enough_true(self):
        assert m2_in_normal("walking_days", 7, gender=1) is True

    def test_walking_days_insufficient_false(self):
        assert m2_in_normal("walking_days", 3, gender=1) is False

    def test_waist_cm_female_normal(self):
        assert m2_in_normal("waist_cm", 80, gender=0) is True

    def test_waist_cm_female_obese(self):
        assert m2_in_normal("waist_cm", 86, gender=0) is False

    def test_waist_cm_male_normal(self):
        assert m2_in_normal("waist_cm", 88, gender=1) is True

    def test_hdl_low_false(self):
        # 38 < 60(정상 하한) → False
        assert m2_in_normal("hdl_cholesterol", 38, gender=1) is False

    def test_hdl_normal_true(self):
        assert m2_in_normal("hdl_cholesterol", 70, gender=1) is True

    def test_triglycerides_high_false(self):
        assert m2_in_normal("triglycerides", 218, gender=1) is False

    def test_smoking_current_false(self):
        # 1.0 > 0.5 → False
        assert m2_in_normal("smoking_current", 1.0, gender=1) is False

    def test_smoking_nonsmoker_true(self):
        assert m2_in_normal("smoking_current", 0, gender=1) is True


# ──────────────────────────────────────────────────────────────────────────────
# 모델2 — 라벨·메시지
# ──────────────────────────────────────────────────────────────────────────────


class TestM2Messages:
    def test_label_bmi(self):
        assert m2_label("bmi") == "체질량지수(BMI)"

    def test_label_walking_days(self):
        assert m2_label("walking_days") == "걷기(주)"

    def test_improve_bmi_contains(self):
        action = m2_improve_action("bmi")
        assert "체중" in action

    def test_improve_smoking_contains(self):
        action = m2_improve_action("smoking_current")
        assert "금연" in action

    def test_maintain_bmi(self):
        assert m2_maintain_msg("bmi") == "건강 체중"

    def test_maintain_smoking(self):
        assert m2_maintain_msg("smoking_current") == "비흡연"

    def test_normal_range_hdl(self):
        result = m2_normal_range("hdl_cholesterol", gender=1)
        assert result == "60~90"

    def test_normal_range_waist_male(self):
        result = m2_normal_range("waist_cm", gender=1)
        assert result == "90 미만"

    def test_normal_range_waist_female(self):
        result = m2_normal_range("waist_cm", gender=0)
        assert result == "85 미만"


# ──────────────────────────────────────────────────────────────────────────────
# 모델2 — m2_domain
# ──────────────────────────────────────────────────────────────────────────────


class TestM2Domain:
    def test_diet_features(self):
        for f in ["bmi", "waist_cm", "hdl_cholesterol", "ldl_cholesterol", "triglycerides"]:
            assert m2_domain(f) == "diet"

    def test_exercise_features(self):
        for f in ["sitting_hours", "walking_days", "moderate_days", "vigorous_days"]:
            assert m2_domain(f) == "exercise"

    def test_etc_feature(self):
        assert m2_domain("smoking_current") == "etc"

    def test_unknown_defaults_etc(self):
        assert m2_domain("unknown_feature") == "etc"


# ──────────────────────────────────────────────────────────────────────────────
# build_domain_summary_text
# ──────────────────────────────────────────────────────────────────────────────


class TestBuildDomainSummaryText:
    def test_empty_is_good(self):
        assert build_domain_summary_text([]) == "양호합니다"

    def test_single_label(self):
        assert build_domain_summary_text(["중성지방"]) == "중성지방 관리가 필요합니다"

    def test_multiple_labels(self):
        assert build_domain_summary_text(["LDL 콜레스테롤", "중성지방"]) == "LDL 콜레스테롤·중성지방 관리가 필요합니다"
