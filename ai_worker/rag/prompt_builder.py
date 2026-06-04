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
    "참고 문서와 전혀 무관한 질문일 때만 '확인된 근거가 없습니다'라고 답하세요. "
    "사용자 CKD 단계가 '미상'으로 표시되면, 일반 정보를 제공하되 정확한 적용을 위해 "
    "검진(eGFR 확인)을 받도록 권하세요. "
    "답변에 영양 수치를 언급할 때는 그 수치 바로 뒤에 ⟦영양소명:숫자:단위⟧ 마커를 붙이세요"
    "(예: '하루 약 48g⟦단백질:48:g⟧'). 단위는 반드시 단백질 g, 나트륨·칼륨·인 mg, 열량 kcal로 기록하세요. "
    "마커의 숫자는 체중당 상대값(예: 0.8 g/kg)이 아니라 일반 성인(체중 60kg) 기준 하루 절대량으로 "
    "환산해 기록하세요(예: 0.8 g/kg → 약 48g → ⟦단백질:48:g⟧). 범위 값(예: 1.0~1.2 g/kg)은 "
    "중간 대표값 하나만 환산해 마커 하나로 표기하고, 같은 수치에 마커를 중복하지 마세요. "
    "마커는 시스템이 음식 비유로 자동 변환하며 문장 흐름과 무관합니다. "
    "답변은 한국어로 작성하고, 출처는 아래 [근거 발췌] 각 항목의 대괄호 안 문서명·페이지를 "
    "그대로 인용하세요(예: [출처: KSN-2025-Hypertension-CKD-Guideline p.93]). "
    "'청크'·'문서'·'발췌' 같은 일반 단어를 출처명으로 쓰지 마세요."
)


def _user_context_line(user_context: dict | None) -> str:
    # user_context 미제공(None) = 테스트·무맥락 → 표기 없음
    if user_context is None:
        return ""
    egfr = user_context.get("eGFR")
    rg = user_context.get("risk_group")
    # 단계·eGFR 둘 다 없음 = 단계 미상 → 검진 권유 유도 (05 명세 §6: NULL 안전 처리)
    if egfr is None and rg is None:
        return "\n[사용자 정보] CKD 단계 미상 — 정확한 적용을 위해 검진(eGFR 확인) 권유 필요"
    parts = []
    if rg is not None:
        parts.append(f"단계={rg}")
    if egfr is not None:
        parts.append(f"eGFR={egfr}")
    return "\n[사용자 정보] " + ", ".join(parts)


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
    user_msg = f"[참고 문서]\n{context}\n\n[근거 발췌]\n{sources}{_user_context_line(user_context)}\n\n[질문]\n{query}"
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
    "- DOMAIN_1: 신장 기능·eGFR·크레아티닌·투석·이식·CKD 스테이지·신장식이(칼륨/인/나트륨 제한)에 관한 질문\n"
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
