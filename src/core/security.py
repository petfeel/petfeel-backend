# src/core/security.py
"""JWT Bearer token 추출 의존성"""
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from services.auth_service import AuthService
from db.repository import UserRepository
from db.models import User

_token_scheme = HTTPBearer(auto_error=False)  # Swagger Authorize 버튼에 자동 반영

def get_access_token(credentials: HTTPAuthorizationCredentials | None = Depends(_token_scheme)) -> str:
    """`Authorization: Bearer <token>` 헤더에서 토큰을 추출.
    FastAPI dependency 로 사용.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="인증 필요")
    return credentials.credentials

_bearer = HTTPBearer(auto_error=False)  # Swagger Authorize 버튼에 자동 반영dfd



def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Security(_bearer),
    repo: UserRepository = Depends(),
    auth: AuthService = Depends(),
) -> User:
    """Authorization 헤더 → User 객체."""
    if creds is None:
        raise HTTPException(status_code=401, detail="토큰 필요")

    username = auth.decode_token(creds.credentials)
    user = repo.get_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return user