# src/schemas/routine.py
from pydantic import BaseModel, Field
from datetime import date
from typing import Optional
from fastapi import Form

# 특정 날짜의 체크리스트트
class RoutineUpsertRequest(BaseModel):  
    vitamin_taken: bool = False                     # 해당날짜
    date: date                                      # 영양제 줬는지여부
    health_check_done: bool = False                 # 건강 상태 확인 여부
    meal_count: int = Field(0, ge=0)                # 실제 밥준 횟수
    meal_target: Optional[int] = Field(None, ge=1)  # 밥줄 횟수 사용자가 정의한거
    walk_count: int = Field(0, ge=0)                # 실제 산책 횟수
    walk_target: Optional[int] = Field(None, ge=1)  # 산책 횟수 사용자가 정의한거거

    # multipart/form-data 지원
    @classmethod
    def as_form(
        cls,
        date: date          = Form(...), # date밑줄은 그냥 같은 명이어서 무상관임
        vitamin_taken: bool = Form(False),    
        health_check_done: bool = Form(False),
        meal_count: int     = Form(0, ge=0),
        meal_target: Optional[int] = Form(None, ge=1),
        walk_count: int     = Form(0, ge=0),
        walk_target: Optional[int] = Form(None, ge=1),
    ) -> "RoutineUpsertRequest":
        return cls(
            date=date,
            vitamin_taken=vitamin_taken,
            health_check_done=health_check_done,
            meal_count=meal_count,
            meal_target=meal_target,
            walk_count=walk_count,
            walk_target=walk_target,
        )

class RoutineSchema(RoutineUpsertRequest):
    id: int
    pet_id: int
    class Config: 
        from_attributes = True  # SQLAlchemy ↔ Pydantic 매핑
