# src/schemas/request.py
"""요청용 Pydantic 모델"""
from pydantic import BaseModel, EmailStr, Field
from fastapi import Form

class CreateOTPRequest(BaseModel):
    email: EmailStr

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp:   int
    
