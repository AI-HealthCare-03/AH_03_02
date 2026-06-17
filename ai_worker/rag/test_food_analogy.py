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


def test_parse_integer_value():
    """정수 값 마커도 float 로 파싱됨."""
    out = fa.parse_markers("⟦칼륨:2000:mg⟧")
    assert out == [("칼륨", 2000.0, "mg")]


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


def test_convert_sodium_g_unit():
    """나트륨 2000mg → 소금·간장 g/큰술 환산."""
    out = fa.convert("나트륨", 2000.0)
    # 소금: 2000/388*1 = 5.15g → step5(100 미만) → round(5.15/5)*5 = 5g
    assert out[0][0] == "소금"
    assert out[0][1] == "약 5g"
    # 간장: 큰술 단위 — 2000/900 = 2.22 → round = 2 → "약 2큰술"
    assert out[1][0] == "간장"
    assert out[1][1] == "약 2큰술"


def test_convert_max_two_results():
    """대표 음식이 3개여도 최대 2개만 반환."""
    out = fa.convert("단백질", 48.0)
    assert len(out) == 2  # 닭가슴살·달걀만 (두부는 제외)


# ── 하위작업 4: apply_analogies ───────────────────────────────────────────────
def test_apply_replaces_marker_and_adds_disclaimer():
    out = fa.apply_analogies("하루 약 48g⟦단백질:48:g⟧입니다.")
    assert "닭가슴살" in out and "달걀" in out
    assert "⟦" not in out and "⟧" not in out
    assert "가늠하기" in out
    # 면책이 "분량)" 직후에 삽입되어 "입니다." 앞에 위치하는지 확인
    assert out.index("가늠하기") < out.index("입니다.")


def test_apply_unmatched_marker_removed_silently():
    out = fa.apply_analogies("비타민C 30mg⟦비타민C:30:mg⟧ 권장")
    assert "⟦" not in out
    assert "비타민C 30mg" in out
    assert "참고용" not in out


def test_apply_no_marker_unchanged():
    src = "마커 없는 일반 답변입니다."
    assert fa.apply_analogies(src) == src


def test_apply_multiple_markers():
    """마커 2개 모두 치환되고 면책은 1번만 붙음."""
    out = fa.apply_analogies("단백질 48g⟦단백질:48:g⟧, 나트륨 2000mg⟦나트륨:2000:mg⟧.")
    assert "닭가슴살" in out
    assert "소금" in out
    assert out.count("가늠하기") == 1  # 면책 중복 없음


def test_apply_marker_not_exposed():
    """⟦⟧ 문자가 출력에 절대 노출되지 않음."""
    out = fa.apply_analogies("칼륨 3500mg⟦칼륨:3500:mg⟧입니다.")
    assert "⟦" not in out and "⟧" not in out


# ── 하위작업 5: generate 프롬프트 마커 지시 ──────────────────────────────────────
def test_system_prompt_has_marker_instruction():
    from ai_worker.rag import prompt_builder

    assert "⟦" in prompt_builder.SYSTEM_PROMPT


# ── 하위작업 6: analogy 노드 ──────────────────────────────────────────────────
def test_analogy_node_applies_to_generation():
    from ai_worker.rag import nodes

    state = {"generation": "하루 약 48g⟦단백질:48:g⟧입니다."}
    out = nodes.analogy_node(state)
    assert "닭가슴살" in out["generation"]
    assert "⟦" not in out["generation"]


# ── 하위작업 7: 단위 검증 (수정1) ───────────────────────────────────────────────
def test_apply_unit_mismatch_removed():
    """단위 불일치(나트륨을 g로 오기록) → 마커 제거, 잘못된 비유 안 나옴."""
    out = fa.apply_analogies("나트륨 약 2g⟦나트륨:2:g⟧")
    assert "⟦" not in out and "소금" not in out and "가늠하기" not in out


def test_apply_unit_match_ok():
    """올바른 단위(나트륨 mg)는 정상 비유 생성."""
    out = fa.apply_analogies("나트륨 2000mg⟦나트륨:2000:mg⟧")
    assert "소금" in out and "가늠하기" in out


# ── 수정1: 음수 마커 노출 방지 ────────────────────────────────────────────────
def test_apply_negative_marker_not_exposed():
    # 음수 등 형식 이상 마커도 노출되면 안 됨 (마커 누출 0 불변식)
    out = fa.apply_analogies("단백질 약 -10g⟦단백질:-10:g⟧입니다")
    assert "⟦" not in out and "⟧" not in out


# ── 수정2: value=0 비유 방지 ──────────────────────────────────────────────────
def test_convert_zero_value_empty():
    assert fa.convert("단백질", 0.0) == []


# ── 수정4: 회귀 보호 테스트 ───────────────────────────────────────────────────
def test_apply_duplicate_same_nutrient_markers():
    # 동일 영양소 마커 2회도 각각 정상 치환·마커 미노출
    out = fa.apply_analogies("아침 ⟦단백질:48:g⟧ 저녁 ⟦단백질:48:g⟧")
    assert out.count("닭가슴살") == 2 and "⟦" not in out


def test_analogy_node_no_marker_no_disclaimer():
    from ai_worker.rag import nodes

    out = nodes.analogy_node({"generation": "마커 없는 일반 답변"})
    assert out["generation"] == "마커 없는 일반 답변"  # 비유·면책 없음


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
