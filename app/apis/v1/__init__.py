from fastapi import APIRouter

from app.apis.v1.admin_routers import admin_router
from app.apis.v1.appointment_routers import appointment_router
from app.apis.v1.auth_routers import auth_router
from app.apis.v1.challenge_routers import challenge_router, user_challenge_router
from app.apis.v1.chat_routers import chat_router
from app.apis.v1.dashboard_routers import dashboard_router
from app.apis.v1.diet_survey_routers import diet_survey_router, surveys_router
from app.apis.v1.gamification_routers import gamification_router, inventory_router
from app.apis.v1.health_check_routers import health_check_router
from app.apis.v1.lab_routers import lab_router
from app.apis.v1.lifestyle_survey_routers import lifestyle_survey_router
from app.apis.v1.notification_routers import notification_router
from app.apis.v1.points_routers import attendance_router, points_router
from app.apis.v1.record_routers import record_router
from app.apis.v1.user_routers import user_router

v1_routers = APIRouter(prefix="/api/v1")
v1_routers.include_router(auth_router)
v1_routers.include_router(user_router)
v1_routers.include_router(health_check_router)
v1_routers.include_router(lifestyle_survey_router)
v1_routers.include_router(diet_survey_router)
v1_routers.include_router(surveys_router)
v1_routers.include_router(dashboard_router)
v1_routers.include_router(notification_router)
v1_routers.include_router(challenge_router)
v1_routers.include_router(user_challenge_router)
v1_routers.include_router(gamification_router)
v1_routers.include_router(inventory_router)
v1_routers.include_router(points_router)
v1_routers.include_router(attendance_router)
v1_routers.include_router(chat_router)
v1_routers.include_router(record_router)
v1_routers.include_router(lab_router)
v1_routers.include_router(appointment_router)
v1_routers.include_router(admin_router)
