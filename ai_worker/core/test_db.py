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
    # shap 미전달 시 shap1·shap2는 NULL(None)로 바인딩 (risk, group, shap1, shap2, id)
    assert args == (0.0848, "G1", None, None, 12)


@pytest.mark.asyncio
async def test_update_prediction_with_shap(monkeypatch) -> None:  # noqa: ANN001
    """shap_model1·shap_model2 전달 시 JSONB로 직렬화돼 바인딩된다."""
    import json

    conn = _FakeConn()

    async def fake_pool():
        return _FakePool(conn)

    monkeypatch.setattr(db, "get_pool", fake_pool)
    await db.update_prediction(
        health_check_id=7,
        ckd_risk_score=0.5,
        app_group="G3",
        shap_model1=[{"feature": "중성지방", "value": 135, "shap": 0.08, "note": "x"}],
        shap_model2={"items": [], "lifestyle_score": 0.2, "peer_top_pct": 22, "peer_relative": "상"},
    )

    query, args = conn.calls[0]
    assert "shap_model1 = $3::jsonb" in query
    assert args[0] == 0.5
    assert args[1] == "G3"
    assert args[4] == 7
    assert json.loads(args[2])[0]["feature"] == "중성지방"
    assert json.loads(args[3])["peer_top_pct"] == 22


@pytest.mark.asyncio
async def test_update_guide(monkeypatch) -> None:  # noqa: ANN001
    """ai_guide를 health_checks.ai_guide에 UPDATE."""
    conn = _FakeConn()

    async def fake_pool():
        return _FakePool(conn)

    monkeypatch.setattr(db, "get_pool", fake_pool)
    await db.update_guide(health_check_id=5, ai_guide="가이드 텍스트")

    query, args = conn.calls[0]
    assert "UPDATE health_checks" in query
    assert "ai_guide = $1" in query
    assert args == ("가이드 텍스트", 5)
