# src/schemas/auth.py
"""요청용 Pydantic 모델"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class SignUpRequest(BaseModel):
    """회원 가입 요청"""
    username: str = Field(..., description="표시명/닉네임")
    email: EmailStr
    password: str


class LogInRequest(BaseModel):
    """로그인 요청 email & password"""
    email: EmailStr
    password: str


class UserSchema(BaseModel):
    id: int
    username: str
    email: EmailStr
    joined_at: datetime

    class Config:
        from_attributes = True  # SQLAlchemy ↔ Pydantic 매핑


class TokenSchema(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str  # ✅ 여기에 추가됨
 