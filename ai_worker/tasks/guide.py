"""SHAP Top 변수 + 식이 위험요인 → RAG 질문 빌드 (ai_worker 자체, app import 금지)."""

from __future__ import annotations


def build_guide_question(
    shap_model1: list[dict] | None,
    shap_model2: dict | None,
    diet_hints: list[str] | None = None,
) -> str:
    """모델1 위험변수 Top3 + 모델2 생활습관 Top3 + 식이 위험요인을 자연어 질문으로 조합."""
    risk_features = ", ".join(item["feature"] for item in (shap_model1 or [])[:3])
    lifestyle_items = (shap_model2 or {}).get("items") or []
    life_features = ", ".join(item["feature"] for item in lifestyle_items[:3])
    diet_part = ""
    if diet_hints:
        diet_part = f"식이 위험 요인: {', '.join(diet_hints[:4])}. "

    return (
        f"다음은 한 사용자의 신장 건강 위험 기여 요인입니다. "
        f"검진 위험 변수: {risk_features or '특이사항 없음'}. "
        f"생활습관 위험 요인: {life_features or '특이사항 없음'}. "
        f"{diet_part}"
        f"이 요인들을 개선하기 위한 식이·운동·생활습관 행동 가이드를 "
        f"구체적이고 실천 가능하게 항목별로 알려주세요."
    )
