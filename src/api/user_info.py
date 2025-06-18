# src/api/user_info.py
"""현재 로그인한 사용자 정보 조회/users/me"""
from fastapi import APIRouter, Depends
from schemas.auth import UserSchema
from fastapi.security import HTTPBearer
from core.security import get_current_user
from db.models import User

router = APIRouter(prefix="/users", tags=["Users"])

bearer_scheme = HTTPBearer(auto_error=False)

@router.get("/me", response_model=UserSchema, summary="로그인된놈")
def read_me(current_user: User = Depends(get_current_user)):  # 토큰 → User 객체 자동 주입
    # Pydantic 모델로 직렬화
    return UserSchema.model_validate(current_user)