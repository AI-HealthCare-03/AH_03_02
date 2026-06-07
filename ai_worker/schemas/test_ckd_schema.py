from ai_worker.schemas.ckd import CkdJob


def test_ckd_job_parse() -> None:
    job = CkdJob(
        health_check_id=12,
        egfr=48.0,
        checked_date="2024-06-01",
        payload={"gender": "MALE", "age": 58},
    )
    assert job.health_check_id == 12
    assert job.egfr == 48.0
    assert job.payload["age"] == 58


def test_ckd_job_egfr_optional() -> None:
    job = CkdJob(health_check_id=1, checked_date="2024-06-01", payload={})
    assert job.egfr is None
