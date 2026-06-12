"""결정론적 상담 카드 고정 문구 (RAG 우회, R3·P3·R5).

칼륨·단백질 상담 트리거는 LLM 검색/생성 대신 고정 문구를 사용한다.
혈액검사 기반 개별화는 의료진 영역이므로 자동 조언을 생성하지 않는다.
"""

from __future__ import annotations

CONSULT_CARDS: dict[str, str] = {
    "칼륨_상담": (
        "과일·채소 섭취가 많은 편입니다. 칼륨 조절 필요 여부는 혈액검사로 결정되므로 다음 진료 때 상담하세요."
    ),
    "단백질_부족_위험": ("투석 중에는 단백질이 부족하면 영양 위험이 있습니다. 식사량을 진료 시 상담하세요."),
}


def render(card_keys: list[str] | None) -> str:
    """상담카드 키 목록 → 결합된 안내 문구(중복 제거, 순서 보존). 없으면 빈 문자열."""
    if not card_keys:
        return ""
    seen: set[str] = set()
    lines: list[str] = []
    for key in card_keys:
        text = CONSULT_CARDS.get(key)
        if text and key not in seen:
            seen.add(key)
            lines.append(f"• {text}")
    if not lines:
        return ""
    return "[상담 권장]\n" + "\n".join(lines)
