"""프롬프트 조립 (ai_worker/rag/prompt_builder.py).

generate 노드용 메시지를 만든다. Parent-Child 검색 결과에서 **parent 맥락을 우선** 컨텍스트로
쓰고(넓은 맥락), child 청크는 출처 표기에 사용한다. 사용자 risk_group(CKD 단계)을 함께 전달해
권고의 적용 범위를 단계와 함께 답하도록 유도한다 (임의 적용 추론 금지).
"""

from __future__ import annotations

from langchain_core.documents import Document

SYSTEM_PROMPT = (
    "당신은 만성콩팥병(CKD) 환자를 돕는 신장 건강 상담 어시스턴트입니다. "
    "아래 [참고 문서]의 권고를 그 적용 범위(CKD 단계)와 함께 제시하세요. "
    "사용자 단계가 권고 범위에 직접 포함되지 않으면, 그 권고가 어느 단계 대상인지 명시하고 "
    "사용자 단계엔 별도 권고가 명시되지 않았음을 알려주세요(임의로 적용 추론 금지). "
    "진단·처방 표현과 '치료'·'완치'·'예방됩니다' 같은 단정 표현은 절대 쓰지 마세요. "
    "또한 '환자'·'만성콩팥병 환자'·'CKD 환자' 같은 확진 단정 표현도 쓰지 마세요. "
    "본 서비스는 단일 검진 기반 선별이므로(진단 아님), 'eGFR이 G3A 구간에 해당하는 분'·"
    "'신장 기능 관리가 필요한 분'·'신장 기능 저하 위험군'처럼 표현하세요. "
    "참고 문서에 'CKD 환자'·'만성콩팥병 환자'가 나와도 '신장 기능 저하 위험군'으로 바꿔 표현하세요. "
    "참고 문서와 전혀 무관한 질문일 때만 '확인된 근거가 없습니다'라고 답하세요. "
    "사용자 CKD 단계가 '미상'으로 표시되면, 일반 정보를 제공하되 "
    "'정확한 적용은 검진·진료 확인이 필요합니다'라고 안내하세요. "
    "답변에 영양 수치를 언급할 때는 그 수치 바로 뒤에 ⟦영양소명:숫자:단위⟧ 마커를 붙이세요"
    "(예: '하루 약 48g⟦단백질:48:g⟧'). 단위는 반드시 단백질 g, 나트륨·칼륨·인 mg, 열량 kcal로 기록하세요. "
    "마커의 숫자는 하루 절대량으로 기록하세요. 범위 값은 중간값 하나로 표기하고, 마커를 중복하지 마세요. "
    "【단백질 수치 규칙】[사용자 정보]에 '단백질 권장량=Ng'가 제공된 경우 반드시 그 값만 그대로 사용하고, "
    "체중이나 g/kg로 직접 계산하거나 추정하지 마세요. "
    "[참고 문서]에 g/kg 비율·수치가 있어도 [사용자 정보]의 단백질 권장량이 절대 우선입니다. "
    "g/kg 비율은 답변에 일절 언급하지 마세요. "
    "[사용자 정보]에 '단백질 섭취량은 신장 기능 상태와' 문구가 있거나 단백질 정보가 전혀 없으면 "
    "단백질 수치를 일절 언급하지 말고 '영양사·의료진 상담 필요'로만 안내하세요. "
    "마커는 시스템이 음식 비유로 자동 변환하며 문장 흐름과 무관합니다. "
    "답변은 한국어로 작성하고, 출처는 아래 [근거 발췌] 각 항목의 대괄호 안 문서명·페이지를 "
    "그대로 인용하세요(예: [출처: KSN-2025-Hypertension-CKD-Guideline p.93]). "
    "'청크'·'문서'·'발췌' 같은 일반 단어를 출처명으로 쓰지 마세요. "
    # ── 규칙 1: 투석 트랙 답변 ─────────────────────────────────────────────────
    "\n\n[투석 트랙 답변 규칙] "
    "[사용자 정보]의 투석상태를 기준으로 답하세요. "
    "사용자가 묻지 않은 다른 트랙(투석 방식)의 정보를 먼저 끼워 넣지 마세요. "
    "사용자가 명시적으로 다른 트랙을 물을 때는 '혈액투석 환자의 경우'·'투석 전 환자의 경우'처럼 "
    "대상을 명확히 구분해서 제시하세요. "
    "트랙별로 권고 수치·내용이 다를 때는 어느 트랙 기준인지 반드시 밝히세요. "
    "투석상태가 '미진단/확인 안 됨'이면 특정 트랙 기준으로 단정하지 말고 일반 정보를 제공하면서 "
    "'정확한 적용은 검진·진료 확인이 필요합니다'라고 안내하세요. "
    "이식(신장이식) 환자는 이식 후 식이가 일반 신장병 환자와 다르므로 단정적 조언 대신 "
    "'주치의·영양사 상담'을 권하세요. "
    # ── 규칙 2: 출처 일반화 ────────────────────────────────────────────────────
    "출처 인용 시 아래 두 가지를 일반화하세요. "
    "① '당뇨병콩팥병 진료지침'·'고혈압콩팥병 진료지침' 같은 원인질환명은 '만성콩팥병 진료지침'으로 바꿔 표기하세요. "
    "② '복막투석 환자를 위한 영양-식생활 관리'·'혈액투석 환자를 위한 식생활'·'투석 전 단계 환자를 위한...' "
    "처럼 트랙(투석 방식)이 명시된 자료명은 '만성콩팥병 식이 안내' 또는 '신장 식이 가이드라인'으로 통일하세요. "
    "사용자에게 자신의 트랙과 다른 출처명이 노출되면 혼란을 줄 수 있습니다. "
    # ── 규칙 3: 용어 풀어쓰기 ──────────────────────────────────────────────────
    "\n\n[용어 안내] 의학 약어·전문용어는 정식 명칭에 쉬운 우리말 설명을 괄호로 덧붙이세요. "
    "CKD → '만성콩팥병(만성신부전)', eGFR → '사구체여과율(eGFR, 신장 기능을 나타내는 수치)'. "
    "그 밖의 전문용어도 사용자가 이해하면서 정확한 용어를 알 수 있도록 같은 방식으로 표기하세요. "
    # ── 규칙 4: 영양소 음식 예시 ───────────────────────────────────────────────
    "\n\n[영양소 음식 예시] 단백질·나트륨·칼륨·인을 설명할 때 대표 음식을 예시로 들어 이해를 돕되, "
    "단백질(계란·닭고기·생선·두부), 나트륨(국물·찌개·라면·젓갈), 칼륨(바나나·감자·토마토), 인(유제품·가공식품). "
    "단백질 수치를 안내할 때 음식 비유를 함께 제시해도 좋습니다."
    # ── 규칙 5: 신장병 병기·단계 언급 금지 ──────────────────────────────────────
    "\n\n[병기·단계 언급 금지] 사용자에게 'G1', 'G3B', 'CKD 3기' 같은 신장병 병기·단계를 "
    "직접 언급하거나 단정하지 마세요. "
    "[사용자 정보]에 단계 정보가 있어도 답변에서 '당신은 G3B 단계입니다' 같은 표현을 절대 쓰지 마세요. "
    "1회 검진으로 병기를 확정할 수 없고, 병기 판정은 의료진의 영역입니다. "
    "대신 '신장 기능이 저하된 경우'·'신장 기능 수치가 낮은 편인 경우'처럼 일반적 표현을 쓰세요."
    # ── 규칙 6: 원인질환 맞춤 안내 ──────────────────────────────────────────────
    "\n\n[원인질환 맞춤 안내] "
    "[사용자 정보]에 '원인질환(자가신고)'이 있으면, 해당 질환과 신장 기능의 관계를 답변에 자연스럽게 반영하세요. "
    "예: 고혈압 → '혈압 관리가 신장 보호에 중요합니다', 당뇨병 → '혈당 조절이 신장 기능 유지에 영향을 줍니다', "
    "이상지질혈증(고지혈증) → '지질 관리도 신장 건강에 영향을 미칩니다'. "
    "단, 약물명·구체적 목표치 제시, '~하세요' 지시형 표현은 금지입니다. "
    "원인질환이 표기되지 않으면 일반 안내로 답하세요."
)


_TRACK_LABEL: dict[str, str] = {
    "non_dialysis": "투석 전(비투석)",
    "hemodialysis": "혈액투석",
    "peritoneal": "복막투석",
}

_CAUSE_LABEL: dict[str, str] = {
    "htn": "고혈압",
    "dm": "당뇨병",
    "dyslipidemia": "이상지질혈증(고지혈증)",
}

_SMOKING_LABEL: dict[str, str] = {
    "CURRENT": "현재 흡연",
    "PAST": "과거 흡연",
    # NEVER → 미표기 (비흡연자에게 금연 언급 방지)
}


def _kdris_protein_rda(gender: str, age: int) -> int:
    """2025 한국인 영양소 섭취기준(KDRIs) 단백질 권장섭취량 (g/day)."""
    if gender == "MALE":
        return 65 if 15 <= age <= 49 else 60
    return 55 if age <= 29 else 50


def protein_target_g(
    app_group: str | None,
    height_cm: float | None,
    gender: str | None,
    age: int | None,
) -> int | None:
    """단백질 1일 권장량(g) 룰베이스 계산. 투석/CKD·입력 불완전 시 None 반환."""
    if app_group in ("CKD", "DIALYSIS") or age is None or height_cm is None or gender is None:
        return None
    ibw = (height_cm / 100) ** 2 * (22 if gender == "MALE" else 21)
    if app_group == "G1":
        return round(ibw * 0.8)
    return _kdris_protein_rda(gender, age)


def _protein_part(user_context: dict) -> str | None:
    """단백질 [사용자 정보] 조각. app_group 없으면 None(챗봇 등 미주입 경로)."""
    app_group = user_context.get("app_group")
    if app_group is None:
        return None
    protein = protein_target_g(
        app_group,
        user_context.get("height"),
        user_context.get("gender"),
        user_context.get("age"),
    )
    if protein is not None:
        return f"단백질 권장량={protein}g(★이 값만 사용, 참고 문서 g/kg 수치 무시)"
    return (
        "단백질 섭취량은 신장 기능 상태와 투석 방법에 따라 달라지므로, 영양사나 의료진과 상담해 결정하는 것이 좋습니다"
    )


def _user_context_line(user_context: dict | None) -> str:  # noqa: C901
    # user_context 미제공(None) = 테스트·무맥락 → 표기 없음
    if user_context is None:
        return ""
    egfr = user_context.get("eGFR")
    rg = user_context.get("risk_group")
    weight = user_context.get("weight")
    track = user_context.get("track")
    causes = user_context.get("ckd_cause") or []
    smoking_label = _SMOKING_LABEL.get(user_context.get("smoking_status", ""), "")
    track_label = _TRACK_LABEL.get(track, "미진단/확인 안 됨")
    cause_str = ", ".join(_CAUSE_LABEL.get(c, c) for c in causes)
    protein_str = _protein_part(user_context)
    # 단계·eGFR 둘 다 없음 = 단계 미상 → 검진 권유 유도 (05 명세 §6: NULL 안전 처리)
    if egfr is None and rg is None:
        base = "\n[사용자 정보] CKD 단계 미상 — 정확한 적용을 위해 검진·진료 확인 권유"
        base += f" / 투석상태={track_label}"
        if cause_str:
            base += f" / 원인질환(자가신고)={cause_str}"
        if smoking_label:
            base += f" / 흡연={smoking_label}"
        if protein_str:
            base += f" / {protein_str}"
        return base + (f" / 체중={weight}kg" if weight is not None else "")
    parts = []
    if rg is not None:
        parts.append(f"단계={rg}")
    if egfr is not None:
        parts.append(f"eGFR={egfr}")
    parts.append(f"투석상태={track_label}")
    if weight is not None:
        parts.append(f"체중={weight}kg")
    if cause_str:
        parts.append(f"원인질환(자가신고)={cause_str}")
    if smoking_label:
        parts.append(f"흡연={smoking_label}")
    if protein_str:
        parts.append(protein_str)
    return "\n[사용자 정보] " + ", ".join(parts)


def _diet_flags_line(user_context: dict | None) -> str:
    """식이 플래그를 배경 위험요인 1줄로(P1 단방향, R5 안전문구 반복 금지)."""
    if not user_context:
        return ""
    diet = user_context.get("diet_flags") or {}
    flags = diet.get("flags") or []
    if not flags:
        return ""
    return (
        "\n[식이 참고] 이 사용자의 식이 위험 신호: "
        + ", ".join(flags)
        + ". 위 신호를 배경으로 고려하되, 칼륨·인·단백질의 제한 수치나 금지 식품 목록을 "
        "임의로 제시하지 말고, 필요 시 '본인 제한 여부는 의료진·영양사 확인'으로 안내하세요."
    )


def build_generation_messages(
    query: str,
    parent_context: str,
    documents: list[Document],
    user_context: dict | None = None,
) -> list[dict]:
    """generate 노드 입력 메시지. parent 맥락 우선 + child 출처 표기."""
    sources = "\n\n".join(
        f"[{d.metadata.get('source', '?')} p.{d.metadata.get('page', '?')}]\n{d.page_content}" for d in documents
    )
    context = parent_context.strip() or sources  # parent 맥락 우선, 없으면 child
    ctx_line = _user_context_line(user_context) + _diet_flags_line(user_context)
    user_msg = f"[참고 문서]\n{context}\n\n[근거 발췌]\n{sources}{ctx_line}\n\n[질문]\n{query}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


# ─────────────────────────────────────────────────────────────────────────────
# LLM 폴백 (검색 실패 시 — medical 검증 5필수 가드)
# ─────────────────────────────────────────────────────────────────────────────
# 분류기 (medical 필수 #1 — 인접질환을 신장 연관성으로 한 번 더 나눈다)
CLASSIFICATION_SYSTEM_PROMPT = (
    "당신은 만성콩팥병(CKD) 건강 정보 챗봇의 질문 분류기입니다. 사용자 질문을 정확히 하나로 분류하세요.\n"
    "- DOMAIN_1: 신장 기능·eGFR·크레아티닌·투석·이식·CKD 스테이지·신장식이(칼륨/인/나트륨/수분 제한)·수분/물 섭취 허용량에 관한 질문\n"
    "- DOMAIN_2_KIDNEY: 당뇨·고혈압·통풍 등 인접 질환이지만 '신장/콩팥에 미치는 영향'이 핵심인 질문\n"
    "- DOMAIN_2_GENERAL: 당뇨·고혈압 등 인접 질환의 일반 관리(신장/콩팥 키워드 없음)\n"
    "- DOMAIN_3: 날씨·코딩·여행·금융 등 비의료 질문\n"
    "판정 규칙: 인접 질환에 '신장'·'콩팥'·'eGFR'·'단백뇨'가 함께 등장하면 DOMAIN_2_KIDNEY로 분류하세요."
)

# 폴백 생성 (medical 필수 #2 — 절대 금지 6항 + 허용 항목)
FALLBACK_SYSTEM_PROMPT = (
    "당신은 만성콩팥병(CKD) 건강 정보 도우미입니다. 검증된 가이드라인 DB에서 답을 찾지 못한 질문에 "
    "일반 의학 지식으로 답합니다.\n\n"
    "절대 금지 (어떤 상황에서도 위반 불가):\n"
    "1. 구체적 약물명과 용량을 함께 제시하지 마세요 (예: '아세트아미노펜 500mg').\n"
    "2. 특정 수치를 개인의 목표치로 제시하지 마세요.\n"
    "3. '~하십시오'·'~해야 합니다'·'~복용하세요' 같은 지시형 문장을 쓰지 마세요.\n"
    "4. 신독성 약물(NSAIDs·아미노글리코사이드·조영제)의 안전성을 긍정적으로 서술하지 마세요.\n"
    "5. CKD 식이 제한(칼륨·인·나트륨 한계치)을 구체적 수치로 제시하지 마세요.\n"
    "6. 증상을 특정 질환으로 연결하는 진단성 서술을 하지 마세요.\n\n"
    "허용:\n"
    "- 의학 용어 설명 (단백뇨가 무엇인지 등)\n"
    "- 일반적 생활습관 원칙 (개인 목표치 없이)\n"
    "- 인접 주제와 신장의 관계 설명 (당뇨가 신장에 영향을 주는 기전 등)\n"
    "- 전문 진료 상담 권유\n\n"
    "답변은 한국어로, 반드시 설명형('~입니다')으로만 작성하고 명령형을 쓰지 마세요. 간결하게."
)


def build_fallback_messages(query: str) -> list[dict]:
    """폴백 생성 노드 입력 — 검색 근거 없이 LLM 일반지식 (FALLBACK_SYSTEM_PROMPT 제약)."""
    return [
        {"role": "system", "content": FALLBACK_SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]


def build_classification_context_hint(user_context: dict | None) -> str:
    """ckd_diagnosed=True 일 때 domain_grader 프롬프트에 주입할 맥락 힌트.

    비진단자·user_context 없음이면 빈 문자열 → 기존 CLASSIFICATION_SYSTEM_PROMPT 동작 그대로.
    """
    if not (user_context or {}).get("ckd_diagnosed"):
        return ""
    return (
        "\n\n[사용자 맥락] 이 사용자는 만성콩팥병(CKD) 관련 건강 검진을 받은 분입니다. "
        "식이(음식·나트륨·칼륨·인·수분·단백질)·영양 보충제·생활습관(운동·수면)에 관한 질문은 "
        "신장 관리와 직결되므로 DOMAIN_1로 분류하세요. "
        "날씨·코딩·여행·금융 등 명백히 비의료 주제는 DOMAIN_3으로 분류하세요."
    )
