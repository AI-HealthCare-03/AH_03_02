from datetime import date

from pydantic import BaseModel

from app.dtos.base import BaseSerializerModel
from app.dtos.record import AutoCheckinResult


class MetricDef(BaseSerializerModel):
    """검사 지표 정의"""

    key: str
    label: str
    unit: str
    decimals: int
    range_low: float | None = None
    range_high: float | None = None


class MetricsResponse(BaseSerializerModel):
    """활성 지표 목록 조회 응답"""

    active_keys: list[str]
    active: list[MetricDef]
    catalog: list[MetricDef]


class SetMetricsRequest(BaseModel):
    """활성 지표 설정 요청"""

    metric_keys: list[str]


class SaveLabRequest(BaseModel):
    """검사 수치 저장 요청"""

    measured_date: date
    values: dict[str, float]


class LabPoint(BaseSerializerModel):
    """검사 수치 시계열 포인트"""

    date: date
    value: float


class MetricOverview(BaseSerializerModel):
    """지표 개요 (최신/이전값, 차이, 범위, 시계열)"""

    key: str
    label: str
    unit: str
    decimals: int
    latest: float | None
    prev: float | None
    delta: float | None
    range_low: float | None
    range_high: float | None
    points: list[LabPoint]


class OverviewResponse(BaseSerializerModel):
    """검사 수치 개요 조회 응답"""

    metrics: list[MetricOverview]
    disclaimer: str


class SaveLabResponse(BaseSerializerModel):
    """검사 수치 저장 응답"""

    measured_date: date
    saved_keys: list[str]
    auto_checkin: AutoCheckinResult


class LabRecordResponse(BaseSerializerModel):
    """검사 기록 조회 응답"""

    measured_date: date | None
    values: dict[str, float]
    has_record: bool
