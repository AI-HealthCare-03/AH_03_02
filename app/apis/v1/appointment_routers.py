"""병원 진료일 캘린더 라우터 — /records/appointments 하위 5개 엔드포인트."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.appointment import (
    AppointmentCreateRequest,
    AppointmentItem,
    AppointmentUpdateRequest,
    MonthResponse,
    OkResponse,
    OverviewResponse,
)
from app.models.users import User
from app.services.appointment import AppointmentService

appointment_router = APIRouter(prefix="/records/appointments", tags=["appointments"])


@appointment_router.get("/overview", response_model=OverviewResponse, status_code=status.HTTP_200_OK)
async def get_overview(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[AppointmentService, Depends(AppointmentService)],
) -> Response:
    """다가오는/지난 진료 예약 요약 조회 (다음 예약 D-day 포함)."""
    result = await service.get_overview(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@appointment_router.get("/month", response_model=MonthResponse, status_code=status.HTTP_200_OK)
async def get_month(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[AppointmentService, Depends(AppointmentService)],
    year: Annotated[int, Query(ge=2000, le=2100)],
    month: Annotated[int, Query(ge=1, le=12)],
) -> Response:
    """특정 연월의 진료 예약 목록 조회."""
    result = await service.get_month(user_id=user.id, year=year, month=month)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@appointment_router.post("", response_model=AppointmentItem, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    body: AppointmentCreateRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[AppointmentService, Depends(AppointmentService)],
) -> Response:
    """새 진료 예약 등록."""
    result = await service.create_appointment(user_id=user.id, dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_201_CREATED)


@appointment_router.put("/{appt_id}", response_model=AppointmentItem, status_code=status.HTTP_200_OK)
async def update_appointment(
    appt_id: int,
    body: AppointmentUpdateRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[AppointmentService, Depends(AppointmentService)],
) -> Response:
    """진료 예약 수정 (날짜·종류·병원·시간 교체)."""
    result = await service.update_appointment(user_id=user.id, appt_id=appt_id, dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@appointment_router.delete("/{appt_id}", response_model=OkResponse, status_code=status.HTTP_200_OK)
async def delete_appointment(
    appt_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[AppointmentService, Depends(AppointmentService)],
) -> Response:
    """진료 예약 삭제."""
    await service.delete_appointment(user_id=user.id, appt_id=appt_id)
    return Response(OkResponse(ok=True).model_dump(mode="json"), status_code=status.HTTP_200_OK)
