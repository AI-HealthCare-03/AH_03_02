from tortoise import fields, models


class DietSurvey(models.Model):
    id = fields.BigIntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="diet_surveys")
    surveyed_date = fields.DateField(description="설문 응답일")

    # Q1: 나트륨 — 하루 국·찌개·탕류 횟수
    soup_stew_per_day = fields.IntField(description="하루 국·찌개·탕류 섭취 횟수")
    # Q2: 당류 — 하루 단 음료(커피 포함) 잔 수
    sweet_drink_per_day = fields.IntField(description="하루 단 음료 잔 수")
    # Q3: 지방 — 주 튀긴 음식 섭취 횟수
    fried_food_per_week = fields.IntField(description="주 튀긴 음식 섭취 횟수")
    # Q4: 식이섬유 — 매 끼 채소 반찬 여부
    vegetables_every_meal = fields.BooleanField(description="매 끼 채소 반찬 섭취 여부")
    # Q5: 칼륨 — 과일·채소·콩류 하루 횟수 (A·B·진단자만 응답, null=미응답)
    potassium_food_freq = fields.IntField(
        null=True, description="칼륨: 과일·채소·콩류 하루 횟수 (0 적음/1 보통/2 많음)"
    )
    # Q6: 단백질 — 고기·생선·계란 하루 횟수 (A·B·진단자만 응답, null=미응답)
    protein_food_freq = fields.IntField(
        null=True, description="단백질: 고기·생선·계란 하루 횟수 (0 적음/1 보통/2 많음)"
    )

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "diet_surveys"
        ordering = ["-surveyed_date"]
