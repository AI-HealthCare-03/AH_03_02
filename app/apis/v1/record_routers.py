from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import ORJSONResponse as Response

from app.dependencies.security import get_request_user
from app.dtos.record import (
    AddWaterRequest,
    AddWaterResponse,
    DropStressRequest,
    DropStressResponse,
    ExerciseHistoryResponse,
    ExerciseTodayResponse,
    LogExerciseRequest,
    LogExerciseResponse,
    LogSleepRequest,
    LogSleepResponse,
    LogWeightRequest,
    LogWeightResponse,
    SetSettingsRequest,
    SettingsResponse,
    SleepHistoryResponse,
    SleepTodayResponse,
    StressHistoryResponse,
    StressTodayResponse,
    WaterHistoryResponse,
    WaterTodayResponse,
    WeightHistoryResponse,
    WeightTodayResponse,
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


@record_router.get("/weight/today", response_model=WeightTodayResponse, status_code=status.HTTP_200_OK)
async def get_weight_today(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.get_weight_today(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.put("/weight", response_model=LogWeightResponse, status_code=status.HTTP_200_OK)
async def log_weight(
    body: LogWeightRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.log_weight(user_id=user.id, today=date.today(), dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.delete("/weight", response_model=WeightTodayResponse, status_code=status.HTTP_200_OK)
async def delete_weight(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.delete_weight(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.get("/weight/history", response_model=WeightHistoryResponse, status_code=status.HTTP_200_OK)
async def weight_history(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
    days: int = Query(7, ge=1, le=90),
) -> Response:
    result = await service.get_weight_history(user_id=user.id, today=date.today(), days=days)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.get("/sleep/today", response_model=SleepTodayResponse, status_code=status.HTTP_200_OK)
async def get_sleep_today(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.get_sleep_today(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.put("/sleep", response_model=LogSleepResponse, status_code=status.HTTP_200_OK)
async def log_sleep(
    body: LogSleepRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.log_sleep(user_id=user.id, today=date.today(), dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.delete("/sleep", response_model=SleepTodayResponse, status_code=status.HTTP_200_OK)
async def delete_sleep(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    result = await service.delete_sleep(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.get("/sleep/history", response_model=SleepHistoryResponse, status_code=status.HTTP_200_OK)
async def sleep_history(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
    days: int = Query(7, ge=1, le=30),
) -> Response:
    result = await service.get_sleep_history(user_id=user.id, today=date.today(), days=days)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


# ── 감정 쓰레기통(스트레스) 엔드포인트 ─────────────────────────────────────


@record_router.get("/stress/today", response_model=StressTodayResponse, status_code=status.HTTP_200_OK)
async def get_stress_today(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    """오늘의 감정 버킷 조회"""
    result = await service.get_stress_today(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.post("/stress", response_model=DropStressResponse, status_code=status.HTTP_201_CREATED)
async def drop_stress(
    body: DropStressRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    """감정 쓰레기통에 감정 투하 (1개 이상)"""
    result = await service.drop_stress(user_id=user.id, today=date.today(), dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_201_CREATED)


@record_router.get("/stress/history", response_model=StressHistoryResponse, status_code=status.HTTP_200_OK)
async def stress_history(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
    days: int = Query(7, ge=1, le=30),
) -> Response:
    """최근 N일 감정 집계 히스토리 조회"""
    result = await service.get_stress_history(user_id=user.id, today=date.today(), days=days)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


# ── 운동 피로도 엔드포인트 ────────────────────────────────────────────────────


@record_router.get("/exercise/today", response_model=ExerciseTodayResponse, status_code=status.HTTP_200_OK)
async def get_exercise_today(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    """오늘의 운동 기록 + 피로도 요약 조회"""
    result = await service.get_exercise_today(user_id=user.id, today=date.today())
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.post("/exercise", response_model=LogExerciseResponse, status_code=status.HTTP_201_CREATED)
async def log_exercise(
    body: LogExerciseRequest,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    """운동 기록 추가 (피로도·종류·시간 포함)"""
    result = await service.log_exercise(user_id=user.id, today=date.today(), dto=body)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_201_CREATED)


@record_router.delete("/exercise/{entry_id}", response_model=ExerciseTodayResponse, status_code=status.HTTP_200_OK)
async def delete_exercise(
    entry_id: int,
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
) -> Response:
    """운동 기록 단건 삭제 후 오늘 요약 반환"""
    result = await service.delete_exercise(user_id=user.id, today=date.today(), entry_id=entry_id)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)


@record_router.get("/exercise/history", response_model=ExerciseHistoryResponse, status_code=status.HTTP_200_OK)
async def exercise_history(
    user: Annotated[User, Depends(get_request_user)],
    service: Annotated[RecordService, Depends(RecordService)],
    days: int = Query(7, ge=1, le=30),
) -> Response:
    """최근 N일 운동 피로도 일별 평균 히스토리 조회"""
    result = await service.get_exercise_history(user_id=user.id, today=date.today(), days=days)
    return Response(result.model_dump(mode="json"), status_code=status.HTTP_200_OK)
