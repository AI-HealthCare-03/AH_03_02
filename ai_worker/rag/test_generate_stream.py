"""generate_node / fallback_generate_node 스트리밍 동작 단위 테스트 (ai_worker/rag/test_generate_stream.py)."""

from ai_worker.rag import nodes


class _FakeChunk:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeStreamLLM:
    def __init__(self, chunks):
        self._chunks = chunks

    def stream(self, msgs):  # noqa: ANN001
        for c in self._chunks:
            yield _FakeChunk(c)

    def invoke(self, msgs):  # noqa: ANN001
        return _FakeChunk("".join(self._chunks))

    def bind(self, **kwargs):  # noqa: ANN001
        """bind() 체이닝 지원 — fallback_generate_node용."""
        return self


class _FakeSink:
    def __init__(self):
        self.began = 0
        self.tokens = []

    def begin_generation(self):
        self.began += 1

    def token(self, text):  # noqa: ANN001
        self.tokens.append(text)


def test_generate_node_streams_to_sink(monkeypatch) -> None:  # noqa: ANN001
    fake = _FakeStreamLLM(["신장", " 건강", "관리"])
    monkeypatch.setattr(nodes.llm_client, "get_gen_llm", lambda: fake)
    monkeypatch.setattr(nodes.prompt_builder, "build_generation_messages", lambda *a, **k: ["msg"])
    sink = _FakeSink()
    state = {
        "messages": [{"role": "user", "content": "q"}],
        "documents": [],
        "parent_context": "",
        "user_context": {},
        "token_sink": sink,
    }
    out = nodes.generate_node(state)
    assert out["generation"] == "신장 건강관리"
    assert sink.began == 1
    assert sink.tokens == ["신장", " 건강", "관리"]


def test_generate_node_no_sink_uses_invoke(monkeypatch) -> None:  # noqa: ANN001
    fake = _FakeStreamLLM(["전체", " 답변"])
    monkeypatch.setattr(nodes.llm_client, "get_gen_llm", lambda: fake)
    monkeypatch.setattr(nodes.prompt_builder, "build_generation_messages", lambda *a, **k: ["msg"])
    state = {
        "messages": [{"role": "user", "content": "q"}],
        "documents": [],
        "parent_context": "",
        "user_context": {},
    }
    out = nodes.generate_node(state)
    assert out["generation"] == "전체 답변"  # invoke 경로(스트리밍 안 함)


def test_fallback_generate_node_streams_to_sink(monkeypatch) -> None:  # noqa: ANN001
    fake = _FakeStreamLLM(["폴백", " 답변"])
    monkeypatch.setattr(nodes.llm_client, "get_gen_llm", lambda: fake)
    monkeypatch.setattr(nodes.prompt_builder, "build_fallback_messages", lambda *a, **k: ["msg"])
    sink = _FakeSink()
    state = {
        "messages": [{"role": "user", "content": "q"}],
        "documents": [],
        "user_context": {},
        "token_sink": sink,
    }
    out = nodes.fallback_generate_node(state)
    assert out["generation"] == "폴백 답변"
    assert sink.began == 1
    assert sink.tokens == ["폴백", " 답변"]


def test_fallback_generate_node_no_sink_uses_invoke(monkeypatch) -> None:  # noqa: ANN001
    fake = _FakeStreamLLM(["전체", " 폴백"])
    monkeypatch.setattr(nodes.llm_client, "get_gen_llm", lambda: fake)
    monkeypatch.setattr(nodes.prompt_builder, "build_fallback_messages", lambda *a, **k: ["msg"])
    state = {
        "messages": [{"role": "user", "content": "q"}],
        "documents": [],
        "user_context": {},
    }
    out = nodes.fallback_generate_node(state)
    assert out["generation"] == "전체 폴백"
