"""safety_guard.py 단위 테스트 (05_medical_guard 명세 — 키·네트워크 불요).

pre_retrieval_guard 차단 분류·우선순위, find_forbidden 금지표현 검출, with_disclaimer.
prompt_builder 도 순수 함수라 함께 검증한다. 실행:
    cd 코드루트 && poc/.venv/bin/python ai_worker/rag/test_safety_guard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 코드루트

from langchain_core.documents import Document

from ai_worker.rag import prompt_builder
from ai_worker.rag import safety_guard as sg


# ── pre_retrieval_guard 차단 분류 ─────────────────────────────────────────────
def test_emergency_blocks_with_119():
    out = sg.pre_retrieval_guard("갑자기 가슴이 심한 통증이 오고 숨이 안 쉬어져요")
    assert out == sg.EMERGENCY_RESPONSE and "119" in out


def test_selfharm_blocks_with_1393():
    out = sg.pre_retrieval_guard("요즘 너무 힘들어서 죽고 싶어요")
    assert out == sg.SELFHARM_RESPONSE and "1393" in out


def test_harm_others_blocks():
    assert sg.pre_retrieval_guard("그 사람을 죽이고 싶어") == sg.HARM_OTHERS_RESPONSE


def test_medication_blocks():
    out = sg.pre_retrieval_guard("혈압약을 끊어도 되나요?")
    assert out == sg.MEDICATION_RESPONSE


def test_diagnosis_request_blocks():
    assert sg.pre_retrieval_guard("제가 당뇨병인가요?") == sg.DIAGNOSIS_RESPONSE
    assert sg.pre_retrieval_guard("진단해줘") == sg.DIAGNOSIS_RESPONSE


def test_egfr_under_30_self_care_blocks():
    out = sg.pre_retrieval_guard("운동 챌린지 추천해줘", user_context={"eGFR": 25})
    assert out == sg.RISK_GROUP_RESPONSE


def test_egfr_over_30_self_care_passes():
    # eGFR 정상이면 운동 질문 통과 (차단 아님)
    assert sg.pre_retrieval_guard("운동 추천해줘", user_context={"eGFR": 55}) is None


def test_egfr_missing_self_care_passes():
    assert sg.pre_retrieval_guard("운동 추천해줘") is None


def test_normal_question_passes():
    assert sg.pre_retrieval_guard("만성콩팥병 환자의 단백질 섭취 권장량은?") is None


def test_priority_emergency_over_selfharm():
    # 응급 + 자해 동시 → 응급(119)이 우선
    out = sg.pre_retrieval_guard("쓰러질 것 같고 죽고 싶어")
    assert out == sg.EMERGENCY_RESPONSE


# ── find_forbidden 금지표현 ────────────────────────────────────────────────────
def test_forbidden_cure_promise():
    assert "치료약속" in sg.find_forbidden("이 식단을 지키면 완치됩니다")


def test_forbidden_prevention_claim():
    assert "예방단정" in sg.find_forbidden("그렇게 하면 콩팥병을 막을 수 있습니다")


def test_forbidden_diagnosis():
    assert "확정진단" in sg.find_forbidden("검사 결과 당뇨로 확진합니다")


def test_no_forbidden_in_safe_text():
    assert sg.find_forbidden("식단 관리가 도움이 될 수 있습니다. 전문의와 상담하세요.") == []


# ── with_disclaimer ────────────────────────────────────────────────────────────
def test_disclaimer_appended():
    out = sg.with_disclaimer("답변 본문")
    assert "의학적 진단·처방을 대체하지" in out


def test_disclaimer_not_duplicated():
    once = sg.with_disclaimer("답변")
    twice = sg.with_disclaimer(once)
    assert once == twice


# ── prompt_builder (순수) ──────────────────────────────────────────────────────
def test_prompt_uses_parent_context_first():
    docs = [Document(page_content="child 본문", metadata={"source": "KDIGO", "page": 5})]
    msgs = prompt_builder.build_generation_messages(
        "질문",
        parent_context="넓은 parent 맥락",
        documents=docs,
        user_context={"eGFR": 50, "risk_group": "G2"},
    )
    assert msgs[0]["role"] == "system"
    user = msgs[1]["content"]
    assert "넓은 parent 맥락" in user  # parent 우선
    assert "KDIGO" in user  # child 출처 표기
    assert "G2" in user and "eGFR=50" in user


def test_prompt_falls_back_to_child_when_no_parent():
    docs = [Document(page_content="child 본문", metadata={"source": "KSN", "page": 1})]
    msgs = prompt_builder.build_generation_messages("질문", parent_context="", documents=docs)
    assert "child 본문" in msgs[1]["content"]


# ── 2026-05-30 의료 리뷰 P0 — CKD 특이 응급 (핍뇨·고칼륨·기좌호흡·고혈압 위기) ─────────
def test_emergency_oliguria():
    assert sg.pre_retrieval_guard("어제부터 소변이 안 나와요") == sg.EMERGENCY_RESPONSE
    # 부사가 끼는 실제 표현도 차단돼야 (통합 스모크에서 발견한 누락)
    assert sg.pre_retrieval_guard("어제부터 소변이 한 번도 안 나와요") == sg.EMERGENCY_RESPONSE


def test_emergency_orthopnea():
    assert sg.pre_retrieval_guard("누우면 숨이 차고 다리가 부어요") == sg.EMERGENCY_RESPONSE


def test_emergency_palpitation_hyperkalemia():
    assert sg.pre_retrieval_guard("심장이 마구 두근거리고 팔다리에 힘이 빠져요") == sg.EMERGENCY_RESPONSE


def test_emergency_hypertensive_crisis():
    assert sg.pre_retrieval_guard("혈압이 갑자기 210까지 올라갔어요") == sg.EMERGENCY_RESPONSE


def test_emergency_active_hemorrhage():
    assert sg.pre_retrieval_guard("출혈이 멈추지 않아요") == sg.EMERGENCY_RESPONSE


# ── P0 — 신독성 약물 직접 언급 차단 ────────────────────────────────────────────
def test_nephrotoxic_nsaid_blocks():
    assert sg.pre_retrieval_guard("이부프로펜 먹어도 되나요?") == sg.MEDICATION_RESPONSE


def test_nephrotoxic_herbal_blocks():
    assert sg.pre_retrieval_guard("한약 먹어도 괜찮을까요?") == sg.MEDICATION_RESPONSE


# ── Phase 6 (2026-06-04 E2E 발견) — 자가 약물 용량조절: "약"과 동사가 분리된 표현 ─────
def test_medication_dose_self_adjust_blocks():
    # E2E에서 발견한 누락: "약"과 조절 동사 사이에 명사·부사("용량을 제가 두 배로")가 끼어 미차단됐음
    assert sg.pre_retrieval_guard("혈압약 용량을 제가 두 배로 늘려도 되나요?") == sg.MEDICATION_RESPONSE
    assert sg.pre_retrieval_guard("당뇨약 양을 좀 줄여도 될까요?") == sg.MEDICATION_RESPONSE
    assert sg.pre_retrieval_guard("약 복용량을 제가 조절해도 되나요?") == sg.MEDICATION_RESPONSE
    assert sg.pre_retrieval_guard("혈압약을 두 배로 먹어도 돼요?") == sg.MEDICATION_RESPONSE


def test_medication_dose_info_question_passes():
    # 자가조절 의도 없는 순수 정보 질문은 과탐 차단하지 않음 (회귀 보호)
    assert sg.pre_retrieval_guard("혈압약은 콩팥에 어떤 영향을 주나요?") is None
    assert sg.pre_retrieval_guard("단백질 섭취량을 늘려도 되나요?") is None


# ── P0/버그 — 진단·출혈 정보 질문은 통과 (false positive 수정) ──────────────────
def test_diagnosis_info_question_passes():
    assert sg.pre_retrieval_guard("만성콩팥병 진단 기준이 뭔가요?") is None
    assert sg.pre_retrieval_guard("CKD 진단 방법을 알려줘") is None


def test_hemorrhage_info_question_passes():
    # "출혈성 뇌졸중"은 정보 질문 — 응급 차단되면 안 됨
    assert sg.pre_retrieval_guard("출혈성 뇌졸중에 대해 알려주세요") is None


# ── P0 — eGFR NULL(단계 미상) → 검진 권유 유도 (명세 §6) ────────────────────────
def test_prompt_egfr_null_adds_screening_hint():
    docs = [Document(page_content="x", metadata={"source": "K", "page": 1})]
    msgs = prompt_builder.build_generation_messages("질문", "parent", docs, user_context={})
    assert "단계 미상" in msgs[1]["content"]


def test_prompt_known_stage_no_screening_hint():
    docs = [Document(page_content="x", metadata={"source": "K", "page": 1})]
    msgs = prompt_builder.build_generation_messages(
        "질문", "parent", docs, user_context={"eGFR": 50, "risk_group": "G2"}
    )
    assert "단계 미상" not in msgs[1]["content"] and "G2" in msgs[1]["content"]


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
