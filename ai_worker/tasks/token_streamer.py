"""스트리밍 토큰 싱크 (ai_worker/tasks/token_streamer.py).

generate 노드가 호출: begin_generation()(2번째+면 reset) / token(text).
sync redis로 rag_resp:{job_id} 스트림에 token·reset 이벤트를 publish.
마커는 MarkerSuppressor로 억제.
"""

from __future__ import annotations

import json

from ai_worker.rag.stream_filter import MarkerSuppressor


class TokenStreamer:
    def __init__(self, sync_redis, resp_key: str) -> None:  # noqa: ANN001
        self._r = sync_redis
        self._key = resp_key
        self._filter = MarkerSuppressor()
        self._streamed = False

    def _xadd(self, ev: dict) -> None:
        self._r.xadd(self._key, {"data": json.dumps(ev, ensure_ascii=False)})

    def begin_generation(self) -> None:
        """generate 노드 진입 시 호출. 2번째+ 호출이면 reset 이벤트 발행."""
        if self._streamed:
            self._xadd({"type": "reset"})
            self._filter.reset()
        self._streamed = True

    def token(self, text: str) -> None:
        """LLM 토큰 청크를 마커 억제 후 스트림에 발행."""
        clean = self._filter.feed(text)
        if clean:
            self._xadd({"type": "token", "text": clean})
