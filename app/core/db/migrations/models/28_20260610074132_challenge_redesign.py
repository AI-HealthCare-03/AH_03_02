from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "daily_checklist_logs" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "log_date" DATE NOT NULL,
    "item_key" VARCHAR(40) NOT NULL,
    "checked" BOOL NOT NULL DEFAULT False,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_daily_check_user_id_837103" UNIQUE ("user_id", "log_date", "item_key")
);
COMMENT ON COLUMN "daily_checklist_logs"."item_key" IS 'medication/diet_fluid/appointment/symptom 등';
COMMENT ON TABLE "daily_checklist_logs" IS '매일 필수 체크리스트 일별 기록 (트랙별 고정 항목).';
        CREATE TABLE IF NOT EXISTS "user_challenge_profiles" (
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "track" VARCHAR(9) NOT NULL,
    "stage" INT NOT NULL DEFAULT 1,
    "auto_assigned" BOOL NOT NULL DEFAULT True,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" BIGINT NOT NULL UNIQUE REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "user_challenge_profiles"."track" IS 'DIALYSIS: DIALYSIS\nCKD: CKD\nINTENSIVE: INTENSIVE\nDAILY: DAILY\nWELLNESS: WELLNESS';
COMMENT ON COLUMN "user_challenge_profiles"."stage" IS '1~4';
COMMENT ON COLUMN "user_challenge_profiles"."auto_assigned" IS '자동배정 후 사용자 변경 시 False';
COMMENT ON TABLE "user_challenge_profiles" IS '사용자별 챌린지 트랙/스테이지 선택 (자동배정 결과 저장 + 수동변경).';
        ALTER TABLE "challenges" ALTER COLUMN "track" TYPE VARCHAR(9) USING "track"::VARCHAR(9);
        COMMENT ON COLUMN "challenges"."track" IS 'DIALYSIS: DIALYSIS
CKD: CKD
INTENSIVE: INTENSIVE
DAILY: DAILY
WELLNESS: WELLNESS';
        ALTER TABLE "challenges" ALTER COLUMN "name" TYPE VARCHAR(200) USING "name"::VARCHAR(200);
        ALTER TABLE "challenges" ALTER COLUMN "category" TYPE VARCHAR(10) USING "category"::VARCHAR(10);
        COMMENT ON COLUMN "challenges"."category" IS 'HYDRATION: HYDRATION
EXERCISE: EXERCISE
DIET: DIET
SLEEP: SLEEP
STRESS: STRESS
EDUCATION: EDUCATION
RECORD: RECORD
MONITORING: MONITORING
EMOTION: EMOTION';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        COMMENT ON COLUMN "challenges"."track" IS 'A: A
B: B';
        ALTER TABLE "challenges" ALTER COLUMN "track" TYPE VARCHAR(1) USING "track"::VARCHAR(1);
        ALTER TABLE "challenges" ALTER COLUMN "name" TYPE VARCHAR(100) USING "name"::VARCHAR(100);
        COMMENT ON COLUMN "challenges"."category" IS 'HYDRATION: HYDRATION
EXERCISE: EXERCISE
DIET: DIET
SLEEP: SLEEP
STRESS: STRESS';
        ALTER TABLE "challenges" ALTER COLUMN "category" TYPE VARCHAR(9) USING "category"::VARCHAR(9);
        DROP TABLE IF EXISTS "daily_checklist_logs";
        DROP TABLE IF EXISTS "user_challenge_profiles";"""


MODELS_STATE = (
    "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"
)
