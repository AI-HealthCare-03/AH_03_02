"""ChatJob / ChatResult 스키마 단위 테스트."""

from ai_worker.schemas.chat import ChatJob, ChatResult


def test_chat_job_roundtrip():
    job = ChatJob(job_id="abc", question="q", user_context={"eGFR": 50})
    dumped = job.model_dump_json()
    restored = ChatJob.model_validate_json(dumped)
    assert restored.job_id == "abc"
    assert restored.user_context["eGFR"] == 50


def test_chat_result_error_or_answer():
    assert ChatResult(answer="ok").answer == "ok"
    assert ChatResult(error="boom").error == "boom"


def test_chatjob_stream_default_false() -> None:
    j = ChatJob(job_id="x", question="q")
    assert j.stream is False


def test_chatjob_stream_true() -> None:
    j = ChatJob(job_id="x", question="q", stream=True)
    assert j.stream is True
