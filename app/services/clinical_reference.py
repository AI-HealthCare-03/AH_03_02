"""
임상 참조 데이터 · 상태/방향 계산 함수
출처: Combined_model1&2/CKD_통합_최종.ipynb (모델1 리포트 셀 + 모델2 local_shap_report 셀)
검증용 초안, 임의 변형 금지 — 의료 참조 데이터는 노트북 값을 정확히 이식한 것입니다.
gender 규약: 1 = 남성(M), 0 = 여성(F)
"""

# ──────────────────────────────────────────────────────────────────────────────
# 모델1 참조 데이터
# ──────────────────────────────────────────────────────────────────────────────

M1_LABEL = {
    "sbp": "수축기혈압",
    "dbp": "이완기혈압",
    "pulse_pressure": "맥압",
    "fasting_glucose": "공복혈당(FBS)",
    "total_cholesterol": "총콜레스테롤",
    "ldl_cholesterol": "저밀도 지단백(LDL)",
    "hdl_cholesterol": "고밀도 지단백(HDL)",
    "triglycerides": "중성지방",
    "creatinine": "크레아티닌",
    "ast": "간 효소(AST)",
    "alt": "간 효소(ALT)",
    "hemoglobin": "헤모글로빈",
    "urine_protein_qual": "요단백",
    "urine_glucose": "요당",
    "waist_cm": "허리둘레",
    "bmi": "체질량지수(BMI, kg/m²)",
    "waist_height_ratio": "허리-키 비율",
    "smoking_current": "흡연 여부",
}

M1_DESC = {
    "sbp": "심장이 수축할 때 혈관 압력",
    "dbp": "심장이 이완할 때 혈관 압력",
    "pulse_pressure": "수축기·이완기 혈압의 차이",
    "fasting_glucose": "공복 상태에서 잰 혈당",
    "total_cholesterol": "혈액 속 전체 콜레스테롤",
    "ldl_cholesterol": "혈관에 쌓이는 나쁜 콜레스테롤",
    "hdl_cholesterol": "혈관을 청소하는 좋은 콜레스테롤",
    "triglycerides": "혈액 속 지방 성분",
    "creatinine": "신장의 여과 기능을 나타내는 노폐물 수치",
    "ast": "간·근육 손상 시 오르는 효소",
    "alt": "간 손상 시 오르는 효소",
    "hemoglobin": "산소를 운반하는 적혈구 색소",
    "urine_protein_qual": "소변으로 단백질이 새는지 검사",
    "urine_glucose": "소변으로 당이 새는지 검사",
    "waist_cm": "복부(내장) 비만 지표",
    "bmi": "키 대비 체중 지표(kg/m²)",
    "waist_height_ratio": "키 대비 허리둘레 비율",
    "smoking_current": "0=비흡연  1=과거 흡연  2=현재 흡연",
}

M1_DISEASE = {
    "sbp": ("저혈압·탈수·부신기능저하·쇼크(중증) 등 원인 점검", "고혈압·뇌졸중·심혈관질환·심부전·고혈압성 신증"),
    "dbp": ("저혈압·탈수 등 원인 점검", "고혈압·뇌졸중·심혈관질환·심부전·고혈압성 신증"),
    "pulse_pressure": ("심박출량 감소·심부전·대동맥판막협착", "동맥경화(혈관 경직)·대동맥판막역류·갑상선기능항진"),
    "fasting_glucose": (
        "기아·간질환·인슐린종 등 저혈당 원인 점검",
        "당뇨병·내당능장애·공복혈당장애·당뇨병성 신증·심혈관질환",
    ),
    "total_cholesterol": ("영양결핍·간질환·갑상선기능항진·흡수장애", "이상지질혈증·동맥경화·심혈관질환"),
    "ldl_cholesterol": ("(대개 문제 적음) 영양결핍·간질환·갑상선항진", "동맥경화·관상동맥질환·심혈관질환"),
    "hdl_cholesterol": (
        "낮은 것 자체가 위험 → 심혈관질환·동맥경화 위험↑",
        "대체로 보호적(높을수록 유리), 극히 높으면 드문 유전적 요인",
    ),
    "triglycerides": (
        "영양결핍·갑상선기능항진·흡수장애(드묾)",
        "고중성지방혈증·대사증후군·심혈관질환·췌장염(매우 높을 때)",
    ),
    "waist_cm": ("저체중·영양결핍", "복부비만·인슐린저항성·대사증후군·당뇨·심혈관질환"),
    "bmi": ("영양결핍·근감소·면역저하·골다공증", "당뇨·고혈압·이상지질혈증·대사증후군·비만 관련 신증"),
    "waist_height_ratio": ("—", "내장지방·대사증후군 위험"),
    "creatinine": ("—", "신장 기능 저하 → 정밀검사(CKD·신부전)"),
    "ast": ("—", "간세포 손상(간염·지방간·간경화)·근육 손상·심근경색·알코올"),
    "alt": ("—", "간세포 손상(간염·지방간·약물성 간손상) — 간 특이도 높음"),
    "hemoglobin": (
        "철·비타민 결핍·만성질환(신장성 빈혈 등)·재생불량성·용혈성 빈혈 등 원인 점검",
        "적혈구증가증·탈수·만성 저산소(폐질환·흡연)",
    ),
    "urine_protein_qual": (
        "—",
        "신장 손상(사구체신염·당뇨병성·고혈압성 신증·CKD)·일시적(발열·운동·기립성)",
    ),
    "urine_glucose": (
        "—",
        "당뇨·고혈당 / 혈당 정상 시 신성 당뇨(세뇨관 재흡수 문제)·임신성 당뇨병",
    ),
    "smoking_current": ("—", "심혈관질환·폐질환·암·COPD·신장 기능 저하 가속"),
}

# 형식: {feature: (unit, target_str, stages_or_dict)}
# stages = [(lo, hi, label), …]  /  gender-split = {'M': […], 'F': […]}
M1_STAGES = {
    "sbp": ("mmHg", "<120", [(0, 120, "정상"), (120, 140, "주의"), (140, 9999, "위험")]),
    "dbp": ("mmHg", "<80", [(0, 80, "정상"), (80, 90, "주의"), (90, 9999, "위험")]),
    "fasting_glucose": ("mg/dL", "<100", [(0, 100, "정상"), (100, 126, "주의"), (126, 9999, "위험")]),
    "total_cholesterol": ("mg/dL", "<200", [(0, 200, "적정"), (200, 240, "경계"), (240, 9999, "높음")]),
    "ldl_cholesterol": (
        "mg/dL",
        "<100",
        [(0, 100, "적정"), (100, 130, "거의 적정"), (130, 160, "경계"), (160, 190, "높음"), (190, 9999, "매우 높음")],
    ),
    "hdl_cholesterol": (
        "mg/dL",
        "60~80",
        [(0, 40, "낮음"), (40, 60, "주의"), (60, 80, "적정"), (80, 9999, "높음(모니터링)")],
    ),
    "triglycerides": (
        "mg/dL",
        "<150",
        [(0, 150, "적정"), (150, 200, "경계"), (200, 500, "높음"), (500, 99999, "매우 높음")],
    ),
    "pulse_pressure": ("mmHg", "40 내외", [(0, 40, "낮음"), (40, 60, "정상"), (60, 999, "높음")]),
    "waist_cm": (
        "cm",
        {"M": "<90", "F": "<85"},
        {"M": [(0, 90, "정상"), (90, 999, "복부비만")], "F": [(0, 85, "정상"), (85, 999, "복부비만")]},
    ),
    "bmi": (
        "kg/m²",
        "18.5–22.9",
        [
            (0, 18.5, "저체중"),
            (18.5, 23, "정상"),
            (23, 25, "과체중"),
            (25, 30, "경도 비만"),
            (30, 35, "중등도 비만"),
            (35, 99, "고도 비만"),
        ],
    ),
    "waist_height_ratio": ("", "<0.5", [(0, 0.5, "정상"), (0.5, 9, "높음")]),
    "creatinine": ("mg/dL", "0.50~1.4", [(0, 0.5, "낮음"), (0.5, 1.4, "정상"), (1.4, 99, "높음")]),
    "ast": ("U/L", "≤40", [(0, 41, "정상"), (41, 9999, "위험")]),
    "alt": ("U/L", "≤40", [(0, 41, "정상"), (41, 9999, "위험")]),
    "hemoglobin": (
        "g/dL",
        {"M": "13~16.5", "F": "12~16"},
        {
            "M": [(0, 13, "빈혈"), (13, 16.5, "정상"), (16.5, 99, "높음")],
            "F": [(0, 12, "빈혈"), (12, 16, "정상"), (16, 99, "높음")],
        },
    ),
    "urine_protein_qual": ("", "음성", [(0, 1, "음성"), (1, 99, "양성")]),
    "urine_glucose": ("", "음성", [(0, 1, "음성"), (1, 99, "양성")]),
    "smoking_current": ("", "비흡연", [(0, 1, "비흡연"), (1, 2, "과거 흡연"), (2, 99, "현재 흡연")]),
}

# 상태 라벨 → 색상 hex (노트북 M1_STATUS_COLOR 그대로)
# 주의: '낮음'은 단일 매핑 #fef9e7(caution). HDL '낮음' 특례는 색→level 변환 후 처리 불필요
# (노트북도 동일 dict — 색은 동일하게 #fef9e7)
M1_STATUS_COLOR = {
    "정상": "#d5f5e3",
    "적정": "#d5f5e3",
    "양호": "#d5f5e3",
    "음성": "#d5f5e3",
    "거의 적정": "#d5f5e3",
    "저체중": "#d6eaf8",
    "주의": "#fef9e7",
    "경계": "#fef9e7",
    "과체중": "#fef9e7",
    "높음(모니터링)": "#fef9e7",
    "낮음": "#fef9e7",
    "경도 비만": "#fdebd0",
    "빈혈": "#fadbd8",
    "높음": "#fadbd8",
    "위험": "#fadbd8",
    "복부비만": "#fadbd8",
    "양성": "#fadbd8",
    "매우 높음": "#fadbd8",
    "중등도 비만": "#fadbd8",
    "고도 비만": "#fadbd8",
    "비흡연": "#d5f5e3",
    "과거 흡연": "#fef9e7",
    "현재 흡연": "#fadbd8",
}

# 색상 hex → status_level (카테고리)
_COLOR_TO_LEVEL: dict[str, str] = {
    "#d5f5e3": "good",  # 초록: 정상·적정·양호 등
    "#d6eaf8": "info",  # 파랑: 저체중
    "#fef9e7": "caution",  # 노랑: 주의·경계·낮음 등
    "#fdebd0": "warnLight",  # 주황: 경도 비만
    "#fadbd8": "danger",  # 빨강: 높음·위험·복부비만 등
}

M1_CATEGORY = {
    "sbp": "혈압·혈당",
    "dbp": "혈압·혈당",
    "fasting_glucose": "혈압·혈당",
    "pulse_pressure": "혈압·혈당",
    "total_cholesterol": "지질",
    "hdl_cholesterol": "지질",
    "ldl_cholesterol": "지질",
    "triglycerides": "지질",
    "creatinine": "간·혈액",
    "ast": "간·혈액",
    "alt": "간·혈액",
    "hemoglobin": "간·혈액",
    "urine_protein_qual": "신장(소변)",
    "urine_glucose": "신장(소변)",
    "waist_cm": "신체",
    "bmi": "신체",
    "waist_height_ratio": "신체",
    "smoking_current": "기타",
}

M1_CAT_ORDER = ["혈압·혈당", "지질", "간·혈액", "신장(소변)", "신체", "기타"]

M1_GROUP_TITLE = {
    "A": "신장 집중 관리군",
    "B": "신장 위험 관리군",
    "C": "신장 사전 관리군",
    "D": "건강 습관 형성군",
    "CKD": "비투석 CKD 진단군",
    "DIALYSIS": "투석·이식 진단군",
}

M1_GROUP_MESSAGE = {
    "A": ("이미 신장 기능이 저하된 단계입니다. 신장내과 진료, 검사, 상담 등 정기 모니터링이 필요합니다.\n"),
    "B": (
        "신장 기능은 정상 범위지만 고혈압·당뇨 등 위험인자가 있어 적극 관리가 필요한 단계입니다.\n"
        "위험 요인을 꾸준히 관리하면 신장 손상을 예방하는 데 도움이 됩니다.\n"
    ),
    "C": ("신장 기능은 정상 범위이며, 두드러진 위험인자는 적지만 모델이 위험 신호를 감지한 단계입니다.\n"),
    "D": (
        "현재 신장 건강과 관련된 뚜렷한 위험 신호는 보이지 않습니다.\n"
        "지금의 건강 상태를 유지할 수 있도록 정기적인 건강검진과 균형 잡힌 생활습관을 이어가세요.\n"
    ),
    "CKD": ("만성 콩팥병(CKD)을 진단받으셨습니다. 주치의 지시에 따라 정기 진료와 약물 복용을 꾸준히 유지하세요.\n"),
    "DIALYSIS": (
        "투석 또는 이식 치료를 받고 계십니다. 투석 일정과 수분·식이 관리를 철저히 지키고 의료진과 긴밀히 소통하세요.\n"
    ),
}

# ──────────────────────────────────────────────────────────────────────────────
# 모델2 참조 데이터
# ──────────────────────────────────────────────────────────────────────────────

# PLAIN_LABEL subset (ast·alt 제외)
M2_LABEL = {
    "bmi": "체질량지수(BMI)",
    "waist_cm": "허리둘레",
    "hdl_cholesterol": "고밀도 지단백(HDL)",
    "ldl_cholesterol": "저밀도 지단백(LDL)",
    "triglycerides": "중성지방",
    "sitting_hours": "하루 앉아있는 시간",
    "walking_days": "걷기(주)",
    "moderate_days": "중강도 운동(주)",
    "vigorous_days": "고강도 운동(주)",
    "smoking_current": "흡연 여부",
}

# 모델2 생활습관 도메인 분류 (식이/운동/기타) — Phase B
M2_DOMAIN = {
    # 식이 연관: 체중·지질 지표 (운동도 영향하나 식이 개입이 주된 권고)
    "bmi": "diet",
    "waist_cm": "diet",
    "hdl_cholesterol": "diet",
    "ldl_cholesterol": "diet",
    "triglycerides": "diet",
    "sitting_hours": "exercise",
    "walking_days": "exercise",
    "moderate_days": "exercise",
    "vigorous_days": "exercise",
    "smoking_current": "etc",
}
DOMAIN_LABEL = {"diet": "식이", "exercise": "운동", "etc": "기타"}
DOMAIN_ORDER = ["diet", "exercise", "etc"]

# CLINICAL_STAGES subset (ast·alt 제외)
M2_STAGES = {
    "bmi": {
        "unit": "",
        "target": "18.5–22.9",
        "stages": [
            (0, 18.5, "저체중", "#3498db"),
            (18.5, 23.0, "정상", "#27ae60"),
            (23.0, 25.0, "과체중", "#f39c12"),
            (25.0, 30.0, "경도 비만", "#e67e22"),
            (30.0, 35.0, "중등도 비만", "#e74c3c"),
            (35.0, 999, "고도 비만", "#c0392b"),
        ],
    },
    "waist_cm": {
        "unit": "cm",
        "target": {"M": "90 미만", "F": "85 미만"},
        "stages": {
            "M": [(0, 90, "정상", "#27ae60"), (90, 999, "복부비만", "#e74c3c")],
            "F": [(0, 85, "정상", "#27ae60"), (85, 999, "복부비만", "#e74c3c")],
        },
    },
    "hdl_cholesterol": {
        "unit": "mg/dL",
        "target": "60~90",
        "stages": [
            (0, 40, "낮음", "#e74c3c"),
            (40, 60, "주의", "#f39c12"),
            (60, 90, "적절", "#27ae60"),
            (90, 999, "높음", "#2980b9"),
        ],
    },
    "ldl_cholesterol": {
        "unit": "mg/dL",
        "target": "100 미만",
        "stages": [
            (0, 100, "적절", "#27ae60"),
            (100, 130, "거의 적절", "#2ecc71"),
            (130, 160, "약간 높음", "#f39c12"),
            (160, 190, "높음", "#e67e22"),
            (190, 999, "아주 높음", "#e74c3c"),
        ],
    },
    "triglycerides": {
        "unit": "mg/dL",
        "target": "150 미만",
        "stages": [
            (0, 150, "적정", "#27ae60"),
            (150, 199, "경계", "#f39c12"),
            (200, 499, "높음", "#e67e22"),
            (500, 9999, "매우 높음", "#e74c3c"),
        ],
    },
    "sitting_hours": {
        "unit": "시간",
        "target": "6시간 미만",
        "stages": [
            (0, 6, "적정", "#27ae60"),
            (6, 8, "주의", "#f39c12"),
            (8, 999, "위험", "#e74c3c"),
        ],
    },
    "walking_days": {
        "unit": "일/주",
        "target": "주 5일 이상",
        "stages": [
            (5, 99, "양호", "#27ae60"),
            (3, 5, "부족", "#f39c12"),
            (0, 3, "매우 부족", "#e74c3c"),
        ],
    },
    "moderate_days": {
        "unit": "일/주",
        "target": "주 5일 이상",
        "stages": [
            (5, 99, "양호", "#27ae60"),
            (3, 5, "부족", "#f39c12"),
            (0, 3, "매우 부족", "#e74c3c"),
        ],
    },
    "vigorous_days": {
        "unit": "일/주",
        "target": "주 3일 이상",
        "stages": [
            (3, 99, "양호", "#27ae60"),
            (1, 3, "부족", "#f39c12"),
            (0, 1, "매우 부족", "#e74c3c"),
        ],
    },
    "smoking_current": {
        "unit": "",
        "target": "비흡연",
        "stages": [
            (0, 0.5, "비흡연", "#27ae60"),
            (0.5, 2, "흡연", "#e74c3c"),
        ],
    },
}

# NORMAL_RANGES_MAP subset (ast·alt 제외)
M2_NORMAL_RANGES = {
    "bmi": [18.5, 22.9],
    "waist_cm": {"M": [0, 90], "F": [0, 85]},
    "hdl_cholesterol": [60, 90],
    "ldl_cholesterol": [0, 100],
    "triglycerides": [0, 150],
    "sitting_hours": [0, 5.999],
    "walking_days": [5, 99],
    "moderate_days": [5, 99],
    "vigorous_days": [3, 99],
    "smoking_current": [0, 0.5],
}

# IMPROVE_ACTION subset (ast·alt 제외)
M2_IMPROVE_ACTION = {
    "bmi": "채소 먼저 천천히 먹고 규칙적 운동으로 정상 체중을 목표로 해보세요.",
    "waist_cm": "유산소 운동과 저탄수화물 식단으로 복부 지방을 줄여보세요.",
    "hdl_cholesterol": "유산소 운동을 늘리고 금연하면 좋은 콜레스테롤을 높일 수 있어요.",
    "ldl_cholesterol": "버터·삼겹살 등 포화지방을 줄이고 채소·통곡물 섭취를 늘려보세요.",
    "triglycerides": "흰쌀·설탕·음주를 줄이면 중성지방 개선에 효과적이에요.",
    "sitting_hours": "앉은 시간이 길수록 부담이 쌓여요. 1시간마다 일어나 움직여보세요.",
    "walking_days": "주 5일, 하루 30분 빠르게 걷기를 목표로 해보세요.",
    "moderate_days": "숨이 약간 찰 정도의 운동을 주 5일 해보세요.",
    "vigorous_days": "숨이 많이 찰 정도의 운동을 주 3일 이상 해보세요.",
    "smoking_current": "금연은 신장을 포함한 전반적 건강에 가장 큰 효과가 있어요.",
}

# MAINTAIN_MSG subset (ast·alt 제외)
M2_MAINTAIN_MSG = {
    "bmi": "건강 체중",
    "waist_cm": "복부비만 없음",
    "hdl_cholesterol": "고밀도 지단백 양호",
    "ldl_cholesterol": "저밀도 지단백 양호",
    "triglycerides": "중성지방 정상",
    "sitting_hours": "좌식시간 적정",
    "walking_days": "걷기 양호",
    "moderate_days": "중강도 운동 충분",
    "vigorous_days": "고강도 운동 실천",
    "smoking_current": "비흡연",
}

# STATUS_COLOR (모델2 노트북 그대로)
M2_STATUS_COLOR = {
    "적정": "#d5f5e3",
    "정상": "#d5f5e3",
    "양호": "#d5f5e3",
    "비흡연": "#d5f5e3",
    "거의 적절": "#d5f5e3",
    "적절": "#d5f5e3",
    "저체중": "#d6eaf8",
    "주의": "#fef9e7",
    "경계": "#fef9e7",
    "부족": "#fef9e7",
    "과체중": "#fef9e7",
    "약간 높음": "#fef9e7",
    "경도 비만": "#fdebd0",
    "높음": "#fadbd8",
    "위험": "#fadbd8",
    "복부비만": "#fadbd8",
    "낮음": "#fadbd8",
    "흡연": "#fadbd8",
    "매우 부족": "#fadbd8",
    "매우 높음": "#fadbd8",
    "아주 높음": "#fadbd8",
    "중등도 비만": "#fadbd8",
    "고도 비만": "#fadbd8",
}

# ──────────────────────────────────────────────────────────────────────────────
# 모델1 함수
# ──────────────────────────────────────────────────────────────────────────────

# (항목, 라벨)별 status_level 예외 — 라벨 색과 의학적 의미가 다른 경우.
# HDL '낮음' = 좋은 콜레스테롤 부족 → 심혈관 위험(danger). 크레아티닌·맥압 '낮음'은 양성이라 caution 유지.
M1_STATUS_LEVEL_OVERRIDE: dict[tuple[str, str], str] = {
    ("hdl_cholesterol", "낮음"): "danger",
}

# 노트북 m1_local_report 분류 기준: 이 라벨이면 shap 부호와 무관하게 '위험 높임'.
# HDL "낮음"은 여기 없음 — status_level override와 별개이므로 충실 구현 불가 케이스.
_BAD_LABELS: frozenset[str] = frozenset(
    {
        "높음",
        "위험",
        "복부비만",
        "양성",
        "빈혈",
        "매우 높음",
        "중등도 비만",
        "고도 비만",
        "현재 흡연",
        "주의",
        "경계",
        "과체중",
        "경도 비만",
        "높음(모니터링)",
        "저체중",
    }
)


def m1_status(feature: str, value: float, gender: int) -> tuple[str, str]:
    """(status_label, status_level) 반환.
    status_label: M1_STAGES 구간 매칭 결과 라벨
    status_level: 색 hex → 'good'/'info'/'caution'/'warnLight'/'danger'
                  단 (항목,라벨) 예외(M1_STATUS_LEVEL_OVERRIDE)가 있으면 우선 적용
    gender: 1=남성, 0=여성
    """
    label = _m1_stage(feature, value, gender)
    color = M1_STATUS_COLOR.get(label, "#fef9e7")
    level = _COLOR_TO_LEVEL.get(color, "caution")
    return label, M1_STATUS_LEVEL_OVERRIDE.get((feature, label), level)


def _m1_stage(feature: str, value: float, gender: int) -> str:
    """M1_STAGES 구간 매칭 → 라벨 반환 (내부 헬퍼)."""
    if feature not in M1_STAGES:
        return "기타"
    stages = M1_STAGES[feature][2]
    if isinstance(stages, dict):
        stages = stages["M"] if gender == 1 else stages["F"]
    for lo, hi, label in stages:
        if lo <= value < hi:
            return label
    return stages[-1][2]


def m1_unit(feature: str) -> str:
    """단위 문자열 반환."""
    return M1_STAGES.get(feature, ("", ""))[0]


def m1_normal_range(feature: str, gender: int) -> str:
    """정상범위 표기 문자열 + 단위 반환. 예: '<120 mmHg'"""
    if feature not in M1_STAGES:
        return "-"
    unit = M1_STAGES[feature][0]
    target = M1_STAGES[feature][1]
    if isinstance(target, dict):
        target_str = target["M"] if gender == 1 else target["F"]
    else:
        target_str = target
    if unit:
        return f"{target_str} {unit}"
    return target_str


def m1_format(feature: str, raw: float) -> str:
    """표시용 값 문자열 반환 (노트북 m1_fmt 이식)."""
    if feature in {"urine_protein_qual", "urine_glucose"}:
        return "양성" if raw >= 1 else "음성"
    if feature == "smoking_current":
        return {0: "비흡연", 1: "과거 흡연", 2: "현재 흡연"}.get(int(raw), str(int(raw)))
    return f"{raw:.1f}"


def m1_direction(feature: str, value: float, gender: int) -> str:
    """정상 범위 대비 방향: 'low' / 'high' / 'normal'.
    범위 하한 미만 → 'low', 상한 초과 → 'high', 범위 내 → 'normal'.
    smoking_current: 1 이상이면 'high', 0이면 'normal'.
    범위를 정의하기 어려운 항목(waist_height_ratio 등)은 stage 라벨로 판단.
    """
    if feature == "smoking_current":
        return "high" if value >= 1 else "normal"

    # 구간 기반으로 정상 구간 경계 추출
    normal_bounds = _m1_normal_bounds(feature, gender)
    if normal_bounds is None:
        return "normal"

    lo, hi = normal_bounds
    if value < lo:
        return "low"
    if value > hi:
        return "high"
    return "normal"


def _m1_normal_bounds(feature: str, gender: int) -> tuple[float, float] | None:
    """M1_STAGES에서 '정상/적정/비흡연' 라벨 구간의 (lo, hi) 반환 (내부 헬퍼).
    정상 라벨이 여러 구간에 걸치거나 없으면 None.
    """
    _normal_labels = {"정상", "적정", "비흡연", "음성"}

    if feature not in M1_STAGES:
        return None

    stages = M1_STAGES[feature][2]
    if isinstance(stages, dict):
        stages = stages["M"] if gender == 1 else stages["F"]

    # 특수 케이스: 단조 증가 위험 (waist_height_ratio, triglycerides 등 하한=0)
    # 정상 라벨 구간 탐색
    for lo, hi, label in stages:
        if label in _normal_labels:
            return (lo, hi)

    # hdl_cholesterol: '적정'이 60~80 → 그 외는 방향 판정 어려움
    # creatinine: '정상' 0.5~1.4 → 이하는 low, 이상은 high
    return None


def m1_group_title(group: str) -> str:
    """그룹 코드 → 그룹 제목."""
    return M1_GROUP_TITLE.get(group, "")


def m1_group_message(group: str) -> str:
    """그룹 코드 → 그룹 메시지."""
    return M1_GROUP_MESSAGE.get(group, "")


def classify_shap_items(
    items: list,
    *,
    bar_threshold: float = 0.001,
) -> dict:
    """SHAP 항목을 임상 단계 라벨 기반으로 높임/낮춤/제외로 분류.

    노트북 m1_local_report 규칙 이식:
      - 단계 라벨이 _BAD_LABELS ∈ → '위험 높임' (shap 부호 무관)
      - 라벨 정상이고 shap <= 0 → '위험 낮춤'
      - 라벨 정상이고 shap > 0 → 양쪽 제외
      - |shap| / total_abs < bar_threshold → 막대 제외 (raise_bar/lower_bar에서만 제거)

    items: dict 또는 ShapItem 객체 혼용 가능.
    반환 키: raise_items, lower_items, total_abs, raise_bar, lower_bar
    """

    def _get(item, key, default=None):
        return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)

    total_abs = sum(abs(_get(it, "shap", 0.0)) for it in items) or 1.0

    raise_items: list = []
    lower_items: list = []
    for item in items:
        stage = _get(item, "status") or ""
        shap = _get(item, "shap", 0.0)
        level = _get(item, "status_level") or ""
        # M1_STATUS_LEVEL_OVERRIDE 케이스(HDL '낮음' 등) 보정:
        # stage가 _BAD_LABELS 밖이어도 status_level이 danger이면 위험 높임으로 처리.
        if stage in _BAD_LABELS or level == "danger":
            raise_items.append(item)
        elif shap <= 0:
            lower_items.append(item)
        # (라벨 정상 + level 정상) + shap > 0 → 양쪽 제외

    raise_items.sort(key=lambda it: -abs(_get(it, "shap", 0.0)))
    lower_items.sort(key=lambda it: -abs(_get(it, "shap", 0.0)))

    def _bar(lst: list) -> list:
        return [it for it in lst if abs(_get(it, "shap", 0.0)) / total_abs >= bar_threshold]

    return {
        "raise_items": raise_items,
        "lower_items": lower_items,
        "total_abs": total_abs,
        "raise_bar": _bar(raise_items),
        "lower_bar": _bar(lower_items),
    }


def classify_m2_shap_items(items: list, gender: int, *, bar_threshold: float = 0.001) -> dict:
    """M2 SHAP 항목을 m2_in_normal 게이트로 개선/유지 두 패널로 분류.

    item.side == "improve" 또는 not in_normal → 개선이 필요한 항목(raise).
    item.side == "maintain" 또는 in_normal → 잘 관리되고 있는 항목(lower).
    side 필드 우선, 없으면 feature 한글 라벨로 M2_LABEL 역조회 후 m2_in_normal 계산.
    """
    _rev: dict[str, str] = {v: k for k, v in M2_LABEL.items()}

    def _get(item, key, default=None):
        return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)

    total_abs = sum(abs(_get(it, "shap", 0.0)) for it in items) or 1.0
    raise_items: list = []
    lower_items: list = []

    for item in items:
        shap = _get(item, "shap", 0.0)
        value = _get(item, "value", 0.0)
        side = _get(item, "side", None)

        if side is not None:
            in_normal = side == "maintain"
        else:
            feature_label = _get(item, "feature", "")
            var = _rev.get(feature_label)
            in_normal = m2_in_normal(var, float(value), gender) if var else (shap <= 0)

        if not in_normal:
            raise_items.append(item)
        else:
            lower_items.append(item)

    raise_items.sort(key=lambda it: -abs(_get(it, "shap", 0.0)))
    lower_items.sort(key=lambda it: -abs(_get(it, "shap", 0.0)))

    def _bar(lst: list) -> list:
        return [it for it in lst if abs(_get(it, "shap", 0.0)) / total_abs >= bar_threshold]

    return {
        "raise_items": raise_items,
        "lower_items": lower_items,
        "total_abs": total_abs,
        "raise_bar": _bar(raise_items),
        "lower_bar": _bar(lower_items),
    }


# ──────────────────────────────────────────────────────────────────────────────
# 모델2 함수
# ──────────────────────────────────────────────────────────────────────────────


def m2_status(feature: str, value: float, gender: int) -> tuple[str, str]:
    """(status_label, status_level) 반환 (모델2 CLINICAL_STAGES 기반).
    gender: 1=남성, 0=여성
    """
    label, _ = _m2_get_stage(feature, value, gender)
    color = M2_STATUS_COLOR.get(label, "#fef9e7")
    level = _COLOR_TO_LEVEL.get(color, "caution")
    return label, level


def _m2_get_stage(feature: str, value: float, gender: int) -> tuple[str, str]:
    """M2_STAGES 구간 매칭 → (label, color) 반환 (내부 헬퍼)."""
    if feature not in M2_STAGES:
        return "기타", "#888888"
    stages = M2_STAGES[feature]["stages"]
    if isinstance(stages, dict):
        stages = stages["M"] if gender == 1 else stages["F"]
    for lo, hi, label, color in stages:
        if lo <= value < hi:
            return label, color
    return stages[-1][2], stages[-1][3]


def m2_normal_range(feature: str, gender: int) -> str:
    """정상범위 표기 문자열 반환 (모델2 target 기반)."""
    if feature not in M2_STAGES:
        return "-"
    target = M2_STAGES[feature]["target"]
    if isinstance(target, dict):
        return target["M"] if gender == 1 else target["F"]
    return target


# M2_STAGES에서 '정상·양호' 단계로 판정되는 라벨 집합
_M2_NORMAL_STATUS_LABELS: frozenset[str] = frozenset({"정상", "적절", "적정", "양호", "비흡연"})


def m2_in_normal(feature: str, value: float, gender: int) -> bool:
    """M2_STAGES 기반 정상·양호 단계 여부 반환.

    _m2_get_stage 와 동일한 반열린 구간(lo <= v < hi)을 공유하므로
    경계값(waist_cm=90 등)에서 m2_status 와 항상 일치.
    """
    label, _ = _m2_get_stage(feature, value, gender)
    return label in _M2_NORMAL_STATUS_LABELS


def m2_label(feature: str) -> str:
    """M2_LABEL 표시명 반환."""
    return M2_LABEL.get(feature, feature)


def m2_improve_action(feature: str) -> str:
    """개선 행동 메시지 반환."""
    return M2_IMPROVE_ACTION.get(feature, "")


def m2_maintain_msg(feature: str) -> str:
    """유지 메시지 반환."""
    return M2_MAINTAIN_MSG.get(feature, "")


def m2_domain(feature: str) -> str:
    """생활습관 feature의 도메인(diet/exercise/etc) 반환. 미정의는 etc."""
    return M2_DOMAIN.get(feature, "etc")


def build_domain_summary_text(improve_labels: list[str]) -> str:
    """도메인 개선항목 표시명(m2_label 변환 후) → 한 줄 요약.

    빈 리스트는 '양호합니다'. 라벨 순서는 호출자가 보장한다.
    """
    if not improve_labels:
        return "양호합니다"
    return f"{'·'.join(improve_labels)} 관리가 필요합니다"
