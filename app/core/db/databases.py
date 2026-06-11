from aerich import Command
from tortoise import Tortoise

from app.core import config

TORTOISE_APP_MODELS = [
    "aerich.models",
    "app.models.users",
    "app.models.health_check",
    "app.models.lifestyle_survey",
    "app.models.challenge",
    "app.models.notification",
    "app.models.diet_survey",
    "app.models.notification_setting",
    "app.models.gamification",
    "app.models.password_reset",
    "app.models.email_verification",
    "app.models.chat",
    "app.models.slump",
    "app.models.admin_action_log",
    "app.models.safety_event",
    "app.models.user_consent",
    "app.models.record",
]

TORTOISE_ORM = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.asyncpg",
            "credentials": {
                "host": config.DB_HOST,
                "port": config.DB_PORT,
                "user": config.DB_USER,
                "password": config.DB_PASSWORD,
                "database": config.DB_NAME,
                "timeout": config.DB_CONNECT_TIMEOUT,
                "maxsize": config.DB_CONNECTION_POOL_MAXSIZE,
            },
        },
    },
    "apps": {
        "models": {
            "models": TORTOISE_APP_MODELS,
        },
    },
    "timezone": "Asia/Seoul",
}

AERICH_MIGRATION_LOCATION = "./app/core/db/migrations"


async def run_migrations() -> None:
    """앱 시작 시 미적용 마이그레이션을 자동으로 적용한다."""
    command = Command(
        tortoise_config=TORTOISE_ORM,
        app="models",
        location=AERICH_MIGRATION_LOCATION,
    )
    await command.init()
    await command.upgrade(run_in_transaction=True)
    await Tortoise.close_connections()
