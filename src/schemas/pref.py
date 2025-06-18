# src/schemas/pref.py

from pydantic import BaseModel, Field

class PrefRequest(BaseModel):
    meals_target: int = Field(2, ge=1)  # 기본값 2 / 의미 :  하루에 사료 몇번줄기
    walks_target: int = Field(1, ge=1)  # 기본값 1 / 의미 :  하루에 산책을 몇번할지
