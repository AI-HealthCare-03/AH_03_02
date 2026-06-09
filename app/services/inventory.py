"""인벤토리 / 구매 서비스.

명세: docs/gamification-spec-v1.md §1-4
- 스트릭 보호권 500pt, 최대 2개 캡
- 회복 미니알 부스터 200pt, 무제한
- 스킨 (소) 300pt / (중) 700pt / (대) 1,200pt — 중복 구매 차단
"""

from fastapi import HTTPException
from starlette import status
from tortoise.functions import Max
from tortoise.transactions import in_transaction

from app.models.gamification import ItemCode, PointReason, UserEgg
from app.repositories.gamification_repository import InventoryRepository, PointRepository
from app.services.points import PointService

ITEM_PRICE: dict[ItemCode, int] = {
    ItemCode.PROTECT: 500,
    ItemCode.MINI_BOOSTER: 200,
    ItemCode.SKIN_S_BLUE: 300,
    ItemCode.SKIN_S_GREEN: 300,
    ItemCode.SKIN_M_RED: 700,
    ItemCode.SKIN_M_PURPLE: 700,
    ItemCode.SKIN_L_GOLD: 1200,
    # 동물 스킨 — 단계별 가격: 1=400, 2=700, 3=1200 (색상 소·중·대 단가 체계 그대로)
    ItemCode.SKIN_TURTLE_1: 400,
    ItemCode.SKIN_PENGUIN_1: 400,
    ItemCode.SKIN_SQUIRREL_1: 400,
    ItemCode.SKIN_RABBIT_1: 400,
    ItemCode.SKIN_PANDA_1: 400,
    ItemCode.SKIN_TURTLE_2: 700,
    ItemCode.SKIN_PENGUIN_2: 700,
    ItemCode.SKIN_SQUIRREL_2: 700,
    ItemCode.SKIN_RABBIT_2: 700,
    ItemCode.SKIN_PANDA_2: 700,
    ItemCode.SKIN_TURTLE_3: 1200,
    ItemCode.SKIN_PENGUIN_3: 1200,
    ItemCode.SKIN_SQUIRREL_3: 1200,
    ItemCode.SKIN_RABBIT_3: 1200,
    ItemCode.SKIN_PANDA_3: 1200,
}

# 동물 스킨 → 요구 진화 단계 (사용자 누적 최고 stage가 이 값 이상이어야 구매 가능)
ANIMAL_SKIN_REQUIRED_STAGE: dict[ItemCode, int] = {
    ItemCode.SKIN_TURTLE_1: 1,
    ItemCode.SKIN_PENGUIN_1: 1,
    ItemCode.SKIN_SQUIRREL_1: 1,
    ItemCode.SKIN_RABBIT_1: 1,
    ItemCode.SKIN_PANDA_1: 1,
    ItemCode.SKIN_TURTLE_2: 2,
    ItemCode.SKIN_PENGUIN_2: 2,
    ItemCode.SKIN_SQUIRREL_2: 2,
    ItemCode.SKIN_RABBIT_2: 2,
    ItemCode.SKIN_PANDA_2: 2,
    ItemCode.SKIN_TURTLE_3: 3,
    ItemCode.SKIN_PENGUIN_3: 3,
    ItemCode.SKIN_SQUIRREL_3: 3,
    ItemCode.SKIN_RABBIT_3: 3,
    ItemCode.SKIN_PANDA_3: 3,
}

# 보유 한도 (없으면 무제한)
ITEM_MAX_QUANTITY: dict[ItemCode, int] = {
    ItemCode.PROTECT: 2,
    # 부스터는 1개 캡 — 사용 후 재방문 유도 (자주 사두는 패턴 차단)
    ItemCode.MINI_BOOSTER: 1,
    # 스킨은 1개씩 (중복 구매 차단)
    ItemCode.SKIN_S_BLUE: 1,
    ItemCode.SKIN_S_GREEN: 1,
    ItemCode.SKIN_M_RED: 1,
    ItemCode.SKIN_M_PURPLE: 1,
    ItemCode.SKIN_L_GOLD: 1,
    ItemCode.SKIN_TURTLE_1: 1,
    ItemCode.SKIN_PENGUIN_1: 1,
    ItemCode.SKIN_SQUIRREL_1: 1,
    ItemCode.SKIN_RABBIT_1: 1,
    ItemCode.SKIN_PANDA_1: 1,
    ItemCode.SKIN_TURTLE_2: 1,
    ItemCode.SKIN_PENGUIN_2: 1,
    ItemCode.SKIN_SQUIRREL_2: 1,
    ItemCode.SKIN_RABBIT_2: 1,
    ItemCode.SKIN_PANDA_2: 1,
    ItemCode.SKIN_TURTLE_3: 1,
    ItemCode.SKIN_PENGUIN_3: 1,
    ItemCode.SKIN_SQUIRREL_3: 1,
    ItemCode.SKIN_RABBIT_3: 1,
    ItemCode.SKIN_PANDA_3: 1,
}


class InventoryService:
    def __init__(self) -> None:
        self._inv = InventoryRepository()
        self._points = PointService()
        self._point_repo = PointRepository()

    @staticmethod
    async def get_max_stage_ever(user_id: int) -> int:
        """사용자의 누적 최고 진화 단계 (모든 알 중 max current_stage). 알이 없으면 0."""
        result = await UserEgg.filter(user_id=user_id).annotate(max_stage=Max("current_stage")).values("max_stage")
        if not result or result[0]["max_stage"] is None:
            return 0
        return int(result[0]["max_stage"])

    async def purchase(self, user_id: int, item_code: ItemCode) -> tuple[int, int, int]:
        """아이템 구매. 반환: (new_quantity, spent, new_balance)."""
        price = ITEM_PRICE.get(item_code)
        if price is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="잘못된 아이템 코드입니다.")

        # 동물 스킨 진화 게이팅 — 누적 최고 단계 >= 스킨 요구 단계
        required_stage = ANIMAL_SKIN_REQUIRED_STAGE.get(item_code)
        if required_stage is not None:
            max_stage = await self.get_max_stage_ever(user_id)
            if max_stage < required_stage:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"{required_stage}단계 진화 후 구매 가능합니다. (현재 누적 최고 {max_stage}단계)",
                )

        # 동시 구매 race·부분 커밋 차단:
        # 사용자별 advisory lock으로 같은 유저의 동시 구매를 직렬화하고,
        # 한도·잔액 검증·포인트 차감·인벤토리 적재를 단일 트랜잭션으로 원자화한다.
        async with in_transaction() as conn:
            await conn.execute_query("SELECT pg_advisory_xact_lock($1)", [user_id])

            # 보유 한도 검증
            current_qty = await self._inv.get_quantity(user_id, item_code)
            max_qty = ITEM_MAX_QUANTITY.get(item_code)
            if max_qty is not None and current_qty >= max_qty:
                if max_qty == 1:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 보유한 아이템입니다.")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"최대 {max_qty}개까지만 보유할 수 있습니다.",
                )

            # 잔액 검증
            balance = await self._point_repo.get_balance(user_id)
            if balance < price:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"포인트가 부족합니다. (잔액 {balance}pt / 필요 {price}pt)",
                )

            # 차감·적재 (한 트랜잭션 — 부분 커밋 방지)
            await self._points.deduct(
                user_id=user_id, amount=price, reason=PointReason.PURCHASE, extra={"item_code": item_code.value}
            )
            row = await self._inv.add_quantity(user_id, item_code, +1)
            new_balance = balance - price
        return row.quantity, price, new_balance

    async def list_items(self, user_id: int) -> list:
        return await self._inv.list_for_user(user_id)
