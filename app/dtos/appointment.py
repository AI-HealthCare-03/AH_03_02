from datetime import date

from pydantic import BaseModel

from app.dtos.base import BaseSerializerModel
from app.models.record import AppointmentType


class AppointmentCreateRequest(BaseModel):
    """진료 일정 신규 요청"""

    appt_date: date
    appt_type: AppointmentType
    appt_time: str | None = None
    hospital: str | None = None
    note: str | None = None


class AppointmentUpdateRequest(BaseModel):
    """진료 일정 수정 요청"""

    appt_date: date
    appt_type: AppointmentType
    appt_time: str | None = None
    hospital: str | None = None
    note: str | None = None


class AppointmentItem(BaseSerializerModel):
    """진료 일정 1건 항목"""

    id: int
    appt_date: date
    appt_time: str | None
    appt_type: AppointmentType
    hospital: str | None
    note: str | None


class NextAppointment(BaseSerializerModel):
    """다음 진료 일정 (d_day 포함)"""

    item: AppointmentItem
    d_day: int


class OverviewResponse(BaseSerializerModel):
    """진료 일정 개요 조회 응답"""

    next: NextAppointment | None
    upcoming: list[AppointmentItem]
    past: list[AppointmentItem]


class MonthResponse(BaseSerializerModel):
    """월별 진료 일정 조회 응답"""

    year: int
    month: int
    items: list[AppointmentItem]


class OkResponse(BaseSerializerModel):
    """성공 응답"""

    ok: bool
