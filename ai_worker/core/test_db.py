import pytest

from ai_worker.core import db


class _FakeConn:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def execute(self, query, *args):  # noqa: ANN001
        self.calls.append((query, args))


class _FakeAcquire:
    def __init__(self, conn) -> None:  # noqa: ANN001
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):  # noqa: ANN001
        return False


class _FakePool:
    def __init__(self, conn) -> None:  # noqa: ANN001
        self._conn = conn

    def acquire(self):
        return _FakeAcquire(self._conn)


@pytest.mark.asyncio
async def test_update_prediction(monkeypatch) -> None:  # noqa: ANN001
    conn = _FakeConn()

    async def fake_pool():
        return _FakePool(conn)

    monkeypatch.setattr(db, "get_pool", fake_pool)
    await db.update_prediction(health_check_id=12, ckd_risk_score=0.0848, app_group="G1")

    query, args = conn.calls[0]
    assert "UPDATE health_checks" in query
    assert args == (0.0848, "G1", 12)
