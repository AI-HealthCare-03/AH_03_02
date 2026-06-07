from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "health_checks" ADD "shap_model1" JSONB;
        ALTER TABLE "health_checks" ADD "shap_model2" JSONB;
        COMMENT ON COLUMN "health_checks"."shap_model1" IS '모델1 위험변수 SHAP Top-N';
        COMMENT ON COLUMN "health_checks"."shap_model2" IS '모델2 생활습관 SHAP + 또래비교';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "health_checks" DROP COLUMN "shap_model1";
        ALTER TABLE "health_checks" DROP COLUMN "shap_model2";"""
