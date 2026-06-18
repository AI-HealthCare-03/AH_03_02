"""의료 안전 가드 (ai_worker/rag/safety_guard.py) — REQ-RAG-005.

학습카드 05_medical_guard 명세 전체를 구현한다.
  • pre_retrieval_guard : 검색 전 즉시 차단 (응급 119·자해 1393·타인위해·약물·진단·eGFR<30 G4/G5)
  • find_forbidden      : 생성 후 금지표현 검출 (확진·완치·예방 단정·약물 직접 권고)
  • with_disclaimer     : 모든 응답 말미 책임 회피 문구

PoC(poc_langgraph_rag)는 EMERGENCY 정규식 1개뿐이었고, 여기서 05 명세 전체로 확장한다.
순서가 중요 — 응급·자해를 최우선으로 검사한다.
"""

from __future__ import annotations

import re

# ─────────────────────────────────────────────────────────────────────────────
# 고정 응답 (05 명세 — 그대로)
# ─────────────────────────────────────────────────────────────────────────────
EMERGENCY_RESPONSE = (
    "응급 상황이 의심됩니다. 즉시 119에 전화하거나 응급실로 가세요. 본 서비스는 응급 상담을 제공하지 않습니다."
)
SELFHARM_RESPONSE = (
    "자살예방상담 1393 또는 정신건강위기상담 1577-0199로 즉시 전화하세요. 24시간 무료입니다. "
    "혼자 견디지 마시고 전문가의 도움을 받으시길 바랍니다."
)
HARM_OTHERS_RESPONSE = "전문 상담을 권합니다. 자살예방상담 1393으로 연락하세요."
EMOTIONAL_RESPONSE = (
    "많이 힘드셨겠어요. 만성콩팥병을 관리하면서 우울하거나 지치는 감정을 느끼는 것은 드문 일이 아닙니다. "
    "마음이 힘든 시간이 계속 이어진다면 가까운 사람이나 전문가와 이야기를 나누는 것이 도움이 될 수 있어요. "
    "상담이 필요하시면 정신건강 상담전화(1577-0199)도 있습니다."
)
MEDICATION_RESPONSE = (
    "약물 변경·복용은 반드시 처방의 또는 약사와 상담하세요. 본 서비스는 약물 가이드를 제공하지 않습니다."
)
DIAGNOSIS_RESPONSE = "본 서비스는 진단·처방을 제공하지 않습니다. 정확한 진단은 병원 상담을 권장합니다."
RISK_GROUP_RESPONSE = (
    "현재 신장 기능(G4·G5 단계)에서는 자가 관리보다 주치의·신장내과 상담이 우선입니다. "
    "운동·식단 조절도 반드시 전문의와 상의하세요."
)

DISCLAIMER = (
    "\n\n---\n\n"
    "ℹ️ 본 정보는 교육·관리 보조 목적의 안내이며, 의학적 진단·처방을 대체하지 않습니다. "
    "정확한 판단은 주치의·신장내과 전문의와 상담하세요."
)

# ─────────────────────────────────────────────────────────────────────────────
# Pre-retrieval 트리거 (05 명세 + 2026-05-30 의료 리뷰 P0 — 응급·자해 최우선)
# ─────────────────────────────────────────────────────────────────────────────
# 응급(119): 일반 응급 + CKD 특이 응급(핍뇨/무뇨 AKI·고칼륨혈증 심계항진·기좌호흡·고혈압 위기).
#   결합 조건으로 정보 질문 과탐을 줄인다 (예: "출혈성 뇌졸중 알려줘"는 '출혈성'이라 미차단).
_EMERGENCY = re.compile(
    r"(쓰러|의식\s*없|기절|혼절|호흡\s*곤란|숨\s*(이\s*)?안\s*(쉬|와|넘어)|숨\s*막|"
    r"누우면\s*숨|누워도\s*숨|"  # 기좌호흡
    r"출혈\s*(이|중|있|이\s*있|이\s*안|이\s*멈)|피\s*가\s*(나|안\s*멈|멈추지)|토혈|혈변|"
    r"심한\s*통증|가슴\s*(통증|답답|조이|쥐어)|"
    r"소변.{0,10}(안|못)\s*(나|보|봐)|오줌.{0,10}안\s*나|핍뇨|무뇨|"  # 핍뇨/무뇨("한 번도 안" 등 부사 허용)
    r"심장\s*(이\s*)?(마구\s*)?(두근|빨리\s*뛰|불규칙)|심계\s*항진|맥박\s*(이\s*)?(불규칙|너무\s*빠)|"  # 고칼륨
    r"사지\s*마비|팔다리\s*(가\s*)?(마비|힘\s*없|힘\s*빠)|온몸\s*(이\s*)?마비|"
    r"혈압.{0,8}(\d{3}|이백|너무\s*높|확\s*올)|"  # 고혈압 위기(혈압 200대·급상승)
    r"응급실|119)"
)
_SELFHARM = re.compile(r"(자살|자해|죽고\s*싶|살기\s*싫|목\s*(을\s*)?매|손목\s*(을\s*)?긋|뛰어내리)")
# 정서적 고통 — 위기(자해)와 분리. 단독 "힘들다"는 과탐지 우려로 제외; 한정어 필요.
_EMOTIONAL = re.compile(r"(우울|너무\s*힘들|마음이\s*힘들|많이\s*지쳐|기운이\s*없어|살기\s*버거)")
_HARM_OTHERS = re.compile(r"(죽이고\s*싶|해치고\s*싶|죽여\s*버리)")
# 약물 변경·복용 의도 (약/약물 + 변경·중단·복용 동사) + 자가 용량조절(분리 표현, 2026-06-04 E2E 발견)
_MEDICATION = re.compile(
    # A. 약+조사+조절동사 인접 ("혈압약을 끊어도")
    r"(약물|약)\s*(을|를|\s)*\s*(바꾸|바꿔|변경|끊|중단|줄이|줄여|늘리|늘려|복용|드셔도|먹어도|처방)"
    # B. 복용/처방+조절동사
    r"|(복용|처방)\s*(을|를)?\s*(바꾸|바꿔|변경|중단|늘리|늘려|줄이|줄여)"
    # C. 약 … 용량/복용량/양/개수/알/정 … 조절 ("혈압약 용량을 제가 두 배로 늘려도")
    r"|(약물|약).{0,15}(용량|복용량|투여량|양|개수|알|정).{0,15}(늘리|늘려|줄이|줄여|바꾸|바꿔|변경|조절|두\s*배|세\s*배|배로|증량|감량)"
    # D. 약 … 두 배/증량 … (용량 단어 없이 직접 조절, "혈압약을 두 배로 먹어도")
    r"|(약물|약).{0,12}(두\s*배|세\s*배|배로|증량|감량|반으로).{0,8}(늘|줄|먹|복용|드)"
)
# 신독성 약물 직접 언급 + 복용/안전 문의 (NSAIDs·조영제·아미노글리코사이드·한약 등) → 주치의로.
#   약명이 변경 동사 없이 등장해도 위험하므로 별도 패턴. 복용·안전 의도와 결합해 정보 과탐 최소화.
_NEPHROTOXIC = re.compile(
    r"(이부프로펜|나프록센|소염\s*진통제|진통제|타이레놀|NSAID|"
    r"조영제|겐타마이신|아미카신|리튬|"
    r"한약|한방|민간요법|건강\s*보조\s*식품|보충제|영양제|칼륨\s*보충)"
    r".{0,20}(먹|복용|드셔도|드시면|써도|괜찮|안전|되나|해도\s*되|맞아도)"
)
# 진단 요청 ("진단해줘", "내가/제가 ~인가요"). "진단 기준/방법/후" 정보 질문은 통과.
_DIAGNOSIS = re.compile(
    r"(진단(해|줘|해줘|해\s*주|받고\s*싶|받을\s*수|부탁)|확진"
    r"|(내가|제가|나)\s*.{0,10}(인가요|일까요|병인가|병이에요|병일까))"
)
# eGFR<30(G4/G5) 동반 시 차단할 자가관리 행위
_RISK_ACTION = re.compile(r"(운동|챌린지|식단|식이|단백질|관리|조절|줄이|늘리)")


def pre_retrieval_guard(query: str, user_context: dict | None = None) -> str | None:
    """검색 전 가드. 차단 시 고정응답 문자열, 통과 시 None.

    검사 순서 = 위험 우선순위:
      응급 → 자해 → 타인위해 → 약물(변경·신독성) → 진단 → eGFR<30 자가관리.
    """
    if _EMERGENCY.search(query):
        return EMERGENCY_RESPONSE
    if _SELFHARM.search(query):
        return SELFHARM_RESPONSE
    if _EMOTIONAL.search(query):
        return EMOTIONAL_RESPONSE
    if _HARM_OTHERS.search(query):
        return HARM_OTHERS_RESPONSE
    if _MEDICATION.search(query) or _NEPHROTOXIC.search(query):
        return MEDICATION_RESPONSE
    if _DIAGNOSIS.search(query):
        return DIAGNOSIS_RESPONSE
    egfr = (user_context or {}).get("eGFR")
    if egfr is not None and egfr < 30 and _RISK_ACTION.search(query):
        return RISK_GROUP_RESPONSE
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Post-generation 금지표현 (05 명세 — 검출 시 면책 강화 / 재생성 후보)
# ─────────────────────────────────────────────────────────────────────────────
_PROTEIN_PRESCRIPTION_RX = re.compile(
    r"(?:"
    r"단백질.{0,40}\d{2,3}\s*g(?!\s*/\s*kg)"
    r"|\d{2,3}\s*g(?!\s*/\s*kg).{0,15}단백질"
    r")",
    re.DOTALL,
)
_PROTEIN_CONTEXT_RX = re.compile(
    r"(?:하루|일일|섭취량|권장량).{0,25}\d{2,3}\s*g(?!\s*/\s*kg)",
    re.DOTALL,
)


def _is_protein_prescription(text: str) -> bool:
    if _PROTEIN_PRESCRIPTION_RX.search(text):
        return True
    for m in _PROTEIN_CONTEXT_RX.finditer(text):
        window = text[max(0, m.start() - 200) : min(len(text), m.end() + 200)]
        if "단백질" in window:
            return True
    return False


_FORBIDDEN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(확진(합니다|됩니다|이?에요)|진단합니다|진단됩니다)"), "확정진단"),
    (re.compile(r"(완치|치료됩니다|치료해\s*드|낫습니다|나아집니다)"), "치료약속"),
    (re.compile(r"(막을\s*수\s*있습니다|예방됩니다|예방할\s*수\s*있습니다)"), "예방단정"),
    (re.compile(r"([가-힣A-Za-z]*\s*약)\s*(을|를)?\s*(드세요|복용하세요|드시면\s*됩니다)"), "약물직접권고"),
]


def find_forbidden(text: str) -> list[str]:
    """생성 답변에서 금지표현 카테고리를 검출 (없으면 빈 리스트)."""
    result = [cat for rx, cat in _FORBIDDEN if rx.search(text)]
    if _is_protein_prescription(text):
        result.append("단백질처방수치")
    return result


_PROTEIN_CAVEAT_PHRASES = ("신장 기능 단계와 표준체중", "검사 수치·단백뇨", "단백뇨 정도에 따라", "연령·성별 기준")
_PROTEIN_CAVEAT_G1 = (
    "\n\n(※ 이 권장량은 신장 기능 단계와 표준체중을 반영한 참고치입니다. "
    "정확한 양은 검사 수치·단백뇨 정도에 따라 다르므로 영양사·의료진과 상담하세요.)"
)
_PROTEIN_CAVEAT_GENERAL = (
    "\n\n(※ 본 권장량은 신장 기능이 정상인 성인의 연령·성별 기준 "
    "일반 권장 섭취량입니다. 개인의 건강 상태, 검사 수치 및 "
    "질환 유무에 따라 적정 섭취량은 달라질 수 있으므로 "
    "영양사 또는 의료진과 상담하시기 바랍니다.)"
)
_G_GROUPS = {"G1", "G2", "G3", "G4"}


def add_protein_caveat_if_missing(text: str, app_group: str | None = None) -> str:
    """단백질처방수치 감지 시 참고치 단서 누락이면 답변 끝에 추가. 단백질 없거나 이미 있으면 불변.

    app_group == "G1": 신장 기능 저하 → IBW×0.8 기반 문구
    app_group in G2·G3·G4: KDRIs 연령·성별 기준 문구
    CKD·DIALYSIS·None: 투석/진단군은 단백질 수치를 LLM이 출력하지 않아야 하므로
                        만일 출력하더라도 caveat 미부착 (잘못된 문구 방지)
    """
    if "단백질" not in text:
        return text
    if any(phrase in text for phrase in _PROTEIN_CAVEAT_PHRASES):
        return text
    if app_group not in _G_GROUPS:
        return text
    caveat = _PROTEIN_CAVEAT_G1 if app_group == "G1" else _PROTEIN_CAVEAT_GENERAL
    return text + caveat


def with_disclaimer(text: str) -> str:
    """이미 면책 문구가 있으면 중복 부착하지 않는다."""
    return text if "의학적 진단·처방을 대체하지" in text else text + DISCLAIMER


# ─────────────────────────────────────────────────────────────────────────────
# LLM 폴백 전용 가드 (검색 실패 차등 라우팅 — medical 필수 #3·#4)
# ─────────────────────────────────────────────────────────────────────────────
# 폴백 답변은 가이드라인 근거가 없으므로 RAG 답변보다 더 엄격히 검사한다. 매칭 시 답변을 대체.
_FALLBACK_FORBIDDEN: list[tuple[re.Pattern, str]] = [
    # 약물·용량 수치 (숫자+단위) — "아세트아미노펜 500mg", "0.8 g", "5 mEq". kg(체중)은 미포함.
    (re.compile(r"\d[\d,\.]*\s*(mg|mcg|μg|mL|ml|IU|mmol|mEq|g|정|캡슐)(?![A-Za-z/])"), "약물·용량수치"),
    (re.compile(r"(과용|독성|치사량|치명적|과다\s*복용|중독)"), "독성·과용"),
    # 식이 제한 수치 (CKD 개인별 처방 사항)
    (re.compile(r"(칼륨|포타슘|인|나트륨|소금).{0,20}(mg|g|mmol|mEq).{0,12}(이하|미만|이상|초과)"), "식이제한수치"),
]


def fallback_post_guard(text: str) -> list[str]:
    """폴백 답변의 위험 패턴(약물수치·독성·식이수치) 검출. find_forbidden 과 별도로 더 엄격."""
    return [cat for rx, cat in _FALLBACK_FORBIDDEN if rx.search(text)]


# 위험 패턴 검출 시 답변을 통째로 대체 (medical 필수 #3 — LLM 답변 그대로 전달 금지)
FALLBACK_REPLACED = "이 내용은 전문 의료진과 직접 상담이 필요한 사항입니다. 담당 의료진(신장내과 등)과 상의하세요."

# 폴백 in-domain 답변 하단 면책 (medical 필수 #4 — 일반성·가이드라인 미포함·의료인 상담 3요소)
FALLBACK_DISCLAIMER = (
    "\n\n---\n\n"
    "ℹ️ 위 내용은 특정 임상 가이드라인에 근거한 정보가 아닌 일반적인 의학 지식입니다. "
    "개인의 신장 기능·동반 질환·복용 약물에 따라 적용이 달라질 수 있으므로, "
    "담당 의료진(신장내과 또는 가정의학과)과 반드시 상담하세요. 이 정보를 자의적으로 적용하지 마세요."
)

# out-of-domain(비의료) scope 안내
SCOPE_NOTICE = (
    "저는 만성콩팥병(CKD) 및 신장 건강 관련 정보를 제공하는 도우미입니다. "
    "문의하신 내용은 제가 안내드릴 수 있는 범위를 벗어납니다. "
    "신장 건강·CKD 관리·신장 보호 생활습관에 관한 궁금한 점을 질문해 주세요."
)

# 인접 질환 비신장(DOMAIN_2_GENERAL) 전문진료 유도
REFERRAL_NOTICE = (
    "문의하신 내용은 만성콩팥병과 관련될 수 있는 중요한 주제입니다. 다만 해당 질환의 구체적인 "
    "관리·치료에 대한 조언은 해당 전문과(내분비내과·순환기내과 등) 의료진과 상담하시기를 권장합니다. "
    "만성콩팥병과의 연관성에 대해 알고 싶으시면 다시 질문해 주세요."
)


def fallback_finalize(text: str) -> str:
    """폴백 LLM 답변을 안전 검사 후 확정. 위험 패턴 시 대체, 통과 시 폴백 면책 부착."""
    if find_forbidden(text) or fallback_post_guard(text):
        return FALLBACK_REPLACED + FALLBACK_DISCLAIMER
    return text + FALLBACK_DISCLAIMER
