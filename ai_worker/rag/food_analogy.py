"""음식 비유 후처리 (ai_worker/rag/food_analogy.py) — 결정론적, LLM 無.

generate가 영양 수치 뒤에 붙인 ⟦영양소:값:단위⟧ 마커를 큐레이션 테이블 기반으로
음식 비유(영양소당 2개)로 치환한다. 환각 가드 통과 후 실행되어 충돌 0.

food_table.json serving_label 규칙:
  "g"로 끝나면 무게(g) 기준 환산, 그 외(개·컵·장·공기·쪽·큰술 등)는 개수 기준 환산.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_TABLE_PATH = Path(__file__).resolve().parent / "food_table.json"
_table: dict | None = None

# ⟦영양소:값:단위⟧ 마커 정규식 (양수 값만 매칭 — 정상 치환용)
_MARKER_RE = re.compile(r"⟦([^:⟧]+):([\d.]+):([^⟧]+)⟧")
# 느슨한 마커 제거용 정규식 — 음수·형식 이상 등 _MARKER_RE가 놓친 잔여 마커까지 제거
_LOOSE_MARKER_RE = re.compile(r"⟦[^⟧]*⟧")
# 문장 경계: 마침표·!·? 뒤에 공백/줄바꿈/끝, 또는 줄바꿈 자체
# 숫자 소수점(2.5g)은 뒤가 공백·줄바꿈·끝이 아니므로 매칭 제외
_SENT_END_RE = re.compile(r"[.!?](?=[ \t\n]|$)|\n")

ANALOGY_DISCLAIMER = (
    "\n\n> ⚠️ 위 음식 예시는 단백질 양이 어느 정도인지 가늠하기 위한 것이며, "
    "실제로 드시는 양은 조리법·식품에 따라 달라질 수 있어요. "
    "식품 선택은 영양사·주치의와 상담하세요."
)


def load_food_table() -> dict:
    """food_table.json 로드 (모듈 캐시)."""
    global _table
    if _table is None:
        _table = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
    return _table


def parse_markers(text: str) -> list[tuple[str, float, str]]:
    """⟦영양소:값:단위⟧ 마커를 (영양소, float 값, 단위) 리스트로 추출."""
    return [(m.group(1), float(m.group(2)), m.group(3)) for m in _MARKER_RE.finditer(text)]


def _round_amount(grams: float) -> str:
    """g 어림수: 100 이상 10단위, 미만 5단위."""
    step = 10 if grams >= 100 else 5
    return f"약 {int(round(grams / step) * step)}g"


def convert(nutrient: str, value: float) -> list[tuple[str, str]]:
    """영양소 값 → 대표 음식(최대 2개)의 양 환산. [(음식, '약 200g'|'약 8개'), ...].

    입력 ``value``의 단위는 테이블 영양소 기준 단위와 일치해야 한다 —
    단백질 g, 나트륨·칼륨·인 mg, 열량 kcal.
    generate 노드의 마커가 이 단위로 기록한다고 가정한다
    (단위 불일치 시 조용히 틀린 비유가 나올 수 있음).
    """
    if value <= 0:  # 0/음수 값은 비유 무의미 → 빈 리스트
        return []
    table = load_food_table()
    result: list[tuple[str, str]] = []
    for food in table["representative"].get(nutrient, []):
        if len(result) >= 2:
            break
        data = table["foods"].get(food)
        if not data:
            continue
        per = data["nutrients"].get(nutrient)
        if per is None or per == 0:  # 영양소 미보유(None) 또는 0나눗셈 방지
            continue
        label = data["serving_label"]
        if label.endswith("g"):
            # g 단위 — 100g 당 영양소 per g, 필요량 = value/per * serving_g
            grams = value / per * data["serving_g"]
            result.append((food, _round_amount(grams)))
        else:
            # 개·장·컵·큰술 등 개수 단위 — 1serving 당 per, 필요 개수 반올림
            count = max(1, round(value / per))
            result.append((food, f"약 {count}{label}"))
    return result


def apply_analogies(text: str) -> str:
    """답변의 ⟦영양소:값:단위⟧ 마커를 음식 비유로 치환. 매칭 실패 마커는 제거.

    비유가 1개 이상 삽입되면 면책 부착. 마커는 절대 노출하지 않는다.

    단위 검증: food_table.json의 nutrient_units와 마커 단위가 다르면 조용히 제거
    (LLM이 프롬프트 지시를 어겨 단위를 오기록한 경우 엉터리 비유 방지).
    기대 단위 정보가 없는 영양소는 기존대로 통과(하위호환).
    """
    inserted = False
    table = load_food_table()
    units = table.get("nutrient_units", {})

    def _sub(m: re.Match) -> str:
        nonlocal inserted
        nutrient, value, unit = m.group(1), float(m.group(2)), m.group(3).strip().lower()
        # 단위 검증: 기대 단위가 있고 마커 단위와 다르면 → 마커 제거 (잘못된 비유 방지)
        expected = units.get(nutrient)
        if expected and unit != expected.lower():
            return ""
        foods = convert(nutrient, value)
        if not foods:
            return ""  # 매칭 실패 → 마커 제거
        inserted = True
        phrase = " 또는 ".join(f"{food} {amount}" for food, amount in foods)
        return f" ({phrase} 분량)"

    out = _MARKER_RE.sub(_sub, text)
    # 형식 이상(음수 등) 잔여 마커까지 제거 → 노출 0 보장
    out = _LOOSE_MARKER_RE.sub("", out)
    if not inserted:
        return out
    last_idx = out.rfind("분량)")
    if last_idx == -1:
        return out + ANALOGY_DISCLAIMER  # 폴백: 분량) 못 찾으면 맨 끝
    insert_at = last_idx + len("분량)")
    # "분량)" 뒤 첫 문장 경계 다음에 삽입 → 마커가 문장 중간이어도 면책이 그 문장 끝 이후에 위치
    tail = out[insert_at:]
    sent_m = _SENT_END_RE.search(tail)
    if sent_m:
        shift = sent_m.end()
        remainder = out[insert_at + shift :]
        # 잔여 텍스트가 줄바꿈 없이 이어지면 blockquote 밖으로 분리
        if remainder and not remainder.startswith("\n"):
            return out[: insert_at + shift] + ANALOGY_DISCLAIMER + "\n\n" + remainder.lstrip()
        return out[: insert_at + shift] + ANALOGY_DISCLAIMER + remainder
    return out + ANALOGY_DISCLAIMER  # 문장 경계 없음(분량)이 이미 끝) → 맨 끝 append
