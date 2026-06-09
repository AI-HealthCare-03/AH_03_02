"""MarkerSuppressor 순수 단위 테스트 (ai_worker/rag/test_stream_filter.py)."""

from ai_worker.rag.stream_filter import MarkerSuppressor


def test_plain_text_passes_through() -> None:
    s = MarkerSuppressor()
    assert s.feed("칼륨은 하루 약 1500mg 권장") == "칼륨은 하루 약 1500mg 권장"


def test_complete_marker_suppressed() -> None:
    s = MarkerSuppressor()
    assert s.feed("약 1500mg⟦칼륨:1500:mg⟧ 권장") == "약 1500mg 권장"


def test_marker_split_across_chunks() -> None:
    s = MarkerSuppressor()
    out = s.feed("약 1500mg⟦칼") + s.feed("륨:1500:mg⟧ 권장")
    assert out == "약 1500mg 권장"


def test_reset_clears_marker_state() -> None:
    s = MarkerSuppressor()
    s.feed("⟦미완성")  # 마커 안에서 끊김
    s.reset()
    assert s.feed("정상텍스트") == "정상텍스트"
