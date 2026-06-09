"""스트리밍 토큰 마커 억제 (ai_worker/rag/stream_filter.py) — 순수, 의존성 無.

generate가 뱉는 ⟦영양소:값:단위⟧ 음식비유 마커를 스트리밍 중 노출하지 않도록
⟦~⟧ 구간을 버퍼링·폐기한다. chunk 경계로 마커가 쪼개져 도착해도 안전.
산문 수치(예: '약 1500mg')는 마커 밖이라 그대로 통과. 음식비유 괄호+면책은 최종(done) 본에 포함.
"""

from __future__ import annotations

_OPEN = "⟦"
_CLOSE = "⟧"


class MarkerSuppressor:
    def __init__(self) -> None:
        self._in_marker = False

    def feed(self, chunk: str) -> str:
        """토큰 청크에서 마커 구간을 제거하고 방출할 clean text 반환."""
        out: list[str] = []
        for ch in chunk:
            if self._in_marker:
                if ch == _CLOSE:
                    self._in_marker = False
                # 마커 내부 문자는 버린다
            elif ch == _OPEN:
                self._in_marker = True
            else:
                out.append(ch)
        return "".join(out)

    def reset(self) -> None:
        """재생성(reset) 시 마커 상태 초기화."""
        self._in_marker = False
