# src/api/auth.py
"""Auth route /auth prefix"""
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.auth import SignUpRequest, LogInRequest
from schemas.auth import UserSchema, TokenSchema
from services.auth_service import AuthService
from  db.repository import UserRepository
from db.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])

# 회원가입
@router.post("/signup", response_model=UserSchema, status_code=status.HTTP_201_CREATED,summary="회원가입")
def signup(
    req: SignUpRequest,
    repo: UserRepository = Depends(),
    auth: AuthService = Depends(),
):
    # 닉네임/이메일 중복 췤
    repo.ensure_unique(username=req.username, email=req.email)

    # 비밀번호 해싱, 저장
    hashed_pw = auth.hash_password(req.password)
    user = repo.save(User.create(req.username, req.email, hashed_pw))
    return user

# 로그인
@router.post("/login", response_model=TokenSchema,summary="로그인")
def login(
    req: LogInRequest,
    repo: UserRepository = Depends(),
    auth: AuthService = Depends(),
):
    user = repo.get_by_email(req.email)
    if not user or not auth.verify_password(req.password, user.password):
        raise HTTPException(status_code=401, detail="이메일이나 비밀번호가 올바르지 않습니다.")

    token = auth.create_access_token(user.username)  # sub = username (변경 가능)
    return TokenSchema(access_token=token, username=user.username)