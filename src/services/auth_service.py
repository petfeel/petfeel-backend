# src/services/auth_service.py
"""Authentication / Authorization helpers"""
from datetime import datetime, timedelta
import os

import bcrypt
from dotenv import load_dotenv
from fastapi import HTTPException
from jose import jwt

load_dotenv()

class AuthService:
    _encoding      = "utf-8"
    _secret_key    = os.getenv("SECRET_KEY", "changeme")
    _algorithm     = "HS256"
    _token_expired = timedelta(days=1)  # 토큰 만료 기간

    #  비밀번호 
    def hash_password(self, plain: str) -> str:
        hashed = bcrypt.hashpw(plain.encode(self._encoding), bcrypt.gensalt())
        return hashed.decode(self._encoding)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return bcrypt.checkpw(plain.encode(self._encoding), hashed.encode(self._encoding))

    #  JWT 
    def create_access_token(self, sub: str) -> str:
        payload = {
            "sub": sub,
            "exp": datetime.utcnow() + self._token_expired,
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode_token(self, token: str) -> str:
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
            return payload["sub"]
        except Exception:
            raise HTTPException(status_code=401, detail="토큰이 유효하지 않습니다.")