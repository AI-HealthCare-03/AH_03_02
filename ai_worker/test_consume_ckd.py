import json

import pytest

from ai_worker import main


class _FakeRedis:
    def __init__(self, messages) -> None:  # noqa: ANN001
        self._messages = messages
        self.acked: list = []

    async def xreadgroup(self, group, consumer, streams, count, block):  # noqa: ANN001
        msgs, self._messages = self._messages, []
        return msgs

    async def xack(self, stream, group, msg_id):  # noqa: ANN001
        self.acked.append(msg_id)


@pytest.mark.asyncio
async def test_consume_ckd_once(monkeypatch) -> None:  # noqa: ANN001
    handled_jobs = []

    async def fake_handle(job):  # noqa: ANN001
        handled_jobs.append(job.health_check_id)

    monkeypatch.setattr(main, "handle_ckd_job", fake_handle)

    fields = {
        "health_check_id": "12",
        "egfr": "48.0",
        "checked_date": "2024-06-01",
        "payload": json.dumps({"gender": "MALE", "age": 58}),
    }
    redis = _FakeRedis([("ckd_jobs", [("1-0", fields)])])
    n = await main.consume_ckd_once(redis)

    assert n == 1
    assert handled_jobs == [12]
    assert redis.acked == ["1-0"]


@pytest.mark.asyncio
async def test_consume_ckd_acks_on_failure(monkeypatch) -> None:  # noqa: ANN001
    async def boom(job):  # noqa: ANN001
        raise RuntimeError("예측 실패")

    monkeypatch.setattr(main, "handle_ckd_job", boom)
    fields = {"health_check_id": "9", "egfr": "", "checked_date": "2024-06-01", "payload": "{}"}
    redis = _FakeRedis([("ckd_jobs", [("2-0", fields)])])

    n = await main.consume_ckd_once(redis)
    assert n == 1
    assert redis.acked == ["2-0"]  # 실패해도 ack
