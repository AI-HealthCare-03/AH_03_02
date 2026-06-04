"""food_analogy.py 단위 테스트 — 결정론적 음식 비유 후처리.

마커 파싱·큐레이션 룩업·환산·치환 순수 함수를 검증한다. 실행:
    cd 코드루트 && poc/.venv/bin/python ai_worker/rag/test_food_analogy.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 코드루트

from ai_worker.rag import food_analogy as fa


# ── 하위작업 1: 큐레이션 테이블 로더 ──────────────────────────────────────────────
def test_load_table_has_representative():
    t = fa.load_food_table()
    assert "닭가슴살" in t["foods"]
    for nutrient in ["단백질", "나트륨", "칼륨", "인", "열량"]:
        assert t["representative"].get(nutrient), f"{nutrient} 대표 음식 없음"


# ── 하위작업 2: parse_markers ─────────────────────────────────────────────────
def test_parse_single_marker():
    out = fa.parse_markers("하루 약 48g⟦단백질:48:g⟧입니다.")
    assert out == [("단백질", 48.0, "g")]


def test_parse_multiple_and_decimal():
    out = fa.parse_markers("⟦나트륨:2000:mg⟧ 그리고 ⟦단백질:6.2:g⟧")
    assert out == [("나트륨", 2000.0, "mg"), ("단백질", 6.2, "g")]


def test_parse_no_marker_returns_empty():
    assert fa.parse_markers("마커 없는 일반 답변") == []


# ── 하위작업 3: convert ───────────────────────────────────────────────────────
def test_convert_protein_two_foods():
    out = fa.convert("단백질", 48.0)
    # 닭가슴살: 48/23*100 = 208.69g → step10 → round(208.69/10)*10 = 210g
    # 달걀: 48/6.2 = 7.74 → round = 8 → "약 8개"
    assert out[0] == ("닭가슴살", "약 210g")
    assert out[1] == ("달걀", "약 8개")
    assert len(out) == 2


def test_convert_unknown_nutrient_empty():
    assert fa.convert("비타민C", 30.0) == []


# ── 하위작업 4: apply_analogies ───────────────────────────────────────────────
def test_apply_replaces_marker_and_adds_disclaimer():
    out = fa.apply_analogies("하루 약 48g⟦단백질:48:g⟧입니다.")
    assert "닭가슴살" in out and "달걀" in out
    assert "⟦" not in out and "⟧" not in out
    assert "참고용" in out


def test_apply_unmatched_marker_removed_silently():
    out = fa.apply_analogies("비타민C 30mg⟦비타민C:30:mg⟧ 권장")
    assert "⟦" not in out
    assert "비타민C 30mg" in out
    assert "참고용" not in out


def test_apply_no_marker_unchanged():
    src = "마커 없는 일반 답변입니다."
    assert fa.apply_analogies(src) == src


# ── 직접 실행 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
