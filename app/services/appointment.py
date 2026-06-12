"""병원 진료일 캘린더 서비스."""

import calendar
from datetime import date

from fastapi import HTTPException
from starlette import status

from app.dtos.appointment import (
    AppointmentCreateRequest,
    AppointmentItem,
    AppointmentUpdateRequest,
    MonthResponse,
    NextAppointment,
    OverviewResponse,
)
from app.repositories.record_repository import AppointmentRepository
from app.services.appointment_reference import d_day

# 개요 조회 시 upcoming/past 각 최대 노출 건수
_UPCOMING_LIMIT = 5
_PAST_LIMIT = 5


class AppointmentService:
    """진료 일정 CRUD 및 개요·월별 조회 서비스."""

    def __init__(self) -> None:
        self._repo = AppointmentRepository()

    async def get_overview(self, user_id: int, today: date) -> OverviewResponse:
        """진료 일정 개요 조회. 다음 예정·upcoming·past 목록과 D-day 반환."""
        upcoming = await self._repo.upcoming(user_id, today, _UPCOMING_LIMIT)
        past = await self._repo.past(user_id, today, _PAST_LIMIT)

        # 가장 가까운 예정 일정 — D-day 계산 포함
        nxt = None
        if upcoming:
            first = upcoming[0]
            nxt = NextAppointment(
                item=AppointmentItem.model_validate(first),
                d_day=d_day(first.appt_date, today),
            )

        return OverviewResponse(
            next=nxt,
            upcoming=[AppointmentItem.model_validate(a) for a in upcoming],
            past=[AppointmentItem.model_validate(a) for a in past],
        )

    async def get_month(self, user_id: int, year: int, month: int) -> MonthResponse:
        """월별 진료 일정 목록 조회 (해당 월 1일~말일)."""
        last = calendar.monthrange(year, month)[1]
        start = date(year, month, 1)
        end = date(year, month, last)
        rows = await self._repo.list_between(user_id, start, end)
        return MonthResponse(
            year=year,
            month=month,
            items=[AppointmentItem.model_validate(a) for a in rows],
        )

    async def create_appointment(self, user_id: int, dto: AppointmentCreateRequest) -> AppointmentItem:
        """진료 일정 신규 등록."""
        obj = await self._repo.create(
            user_id,
            dto.appt_date,
            (dto.appt_time or None),
            dto.appt_type.value,
            dto.hospital,
            dto.note,
        )
        return AppointmentItem.model_validate(obj)

    async def update_appointment(
        self,
        user_id: int,
        appt_id: int,
        dto: AppointmentUpdateRequest,
    ) -> AppointmentItem:
        """진료 일정 수정. 본인 소유 일정이 아니거나 존재하지 않으면 404."""
        obj = await self._repo.update(
            appt_id,
            user_id,
            {
                "appt_date": dto.appt_date,
                "appt_time": (dto.appt_time or None),
                "appt_type": dto.appt_type.value,
                "hospital": dto.hospital,
                "note": dto.note,
            },
        )
        if obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="일정을 찾을 수 없습니다.",
            )
        return AppointmentItem.model_validate(obj)

    async def delete_appointment(self, user_id: int, appt_id: int) -> None:
        """진료 일정 삭제. 본인 소유 일정이 아니거나 존재하지 않으면 404."""
        ok = await self._repo.delete(appt_id, user_id)
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="일정을 찾을 수 없습니다.",
            )
