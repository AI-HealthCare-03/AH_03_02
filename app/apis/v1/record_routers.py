from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.record import (
    AddWaterRequest,
    AddWaterResponse,
    SetSettingsRequest,
    SettingsResponse,
    WaterHistoryResponse,
    WaterTodayResponse,
)
from app.models.users import User
from app.services.record import RecordService

record_router = APIRouter(prefix="/records", tags=["records"])


@record_router.get("/water/today", response_model=WaterTodayResponse, status_code=status.HTTP_200_OK)
async def get_water_today(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.get_today(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.post("/water", response_model=AddWaterResponse, status_code=status.HTTP_201_CREATED)
async def add_water(
    body: AddWaterRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.add_water(user_id=user.id, today=date.today(), dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_201_CREATED)


@record_router.delete("/water/{entry_id}", response_model=WaterTodayResponse, status_code=status.HTTP_200_OK)
async def delete_water(
    entry_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.delete_water(user_id=user.id, today=date.today(), entry_id=entry_id)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.get("/water/history", response_model=WaterHistoryResponse, status_code=status.HTTP_200_OK)
async def water_history(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
    days: int = Query(30, ge=1, le=90),
) -> Response:
    result = await service.get_history(user_id=user.id, today=date.today(), days=days)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.get("/settings", response_model=SettingsResponse, status_code=status.HTTP_200_OK)
async def get_settings(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.get_settings(user_id=user.id)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.put("/settings", response_model=SettingsResponse, status_code=status.HTTP_200_OK)
async def set_settings(
    body: SetSettingsRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.set_settings(user_id=user.id, dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)
