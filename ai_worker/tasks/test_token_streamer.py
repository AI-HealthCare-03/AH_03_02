"""TokenStreamer 단위 테스트."""

import json

from ai_worker.tasks.token_streamer import TokenStreamer


class _FakeRedis:
    def __init__(self):
        self.adds = []

    def xadd(self, key, fields):  # noqa: ANN001
        self.adds.append((key, json.loads(fields["data"])))


def test_first_generation_no_reset_tokens_clean() -> None:
    r = _FakeRedis()
    s = TokenStreamer(r, "resp:1")
    s.begin_generation()
    s.token("신장 약 1500mg⟦칼륨:1500:mg⟧ 권장")
    types = [ev["type"] for _, ev in r.adds]
    assert "reset" not in types
    joined = "".join(ev["text"] for _, ev in r.adds if ev["type"] == "token")
    assert joined == "신장 약 1500mg 권장"  # 마커 억제


def test_second_generation_emits_reset() -> None:
    r = _FakeRedis()
    s = TokenStreamer(r, "resp:1")
    s.begin_generation()
    s.token("first")
    s.begin_generation()  # 재생성
    assert any(ev["type"] == "reset" for _, ev in r.adds)


def test_token_without_begin_generation_is_still_clean() -> None:
    """begin_generation 없이 token만 호출해도 마커 억제는 동작."""
    r = _FakeRedis()
    s = TokenStreamer(r, "resp:2")
    s.token("안녕⟦marker:x:y⟧하세요")
    joined = "".join(ev["text"] for _, ev in r.adds if ev["type"] == "token")
    assert joined == "안녕하세요"


def test_empty_clean_token_not_published() -> None:
    """마커만 있어 clean이 빈 문자열이면 xadd를 호출하지 않는다."""
    r = _FakeRedis()
    s = TokenStreamer(r, "resp:3")
    s.begin_generation()
    s.token("⟦칼륨:1500:mg⟧")  # 완전히 억제 대상
    token_events = [ev for _, ev in r.adds if ev["type"] == "token"]
    assert len(token_events) == 0


def test_resp_key_forwarded_to_xadd() -> None:
    """xadd에 올바른 resp_key가 전달된다."""
    r = _FakeRedis()
    s = TokenStreamer(r, "rag_resp:job-abc")
    s.begin_generation()
    s.token("안녕")
    keys = [k for k, _ in r.adds]
    assert all(k == "rag_resp:job-abc" for k in keys)
