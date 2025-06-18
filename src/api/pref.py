# src/api/pref.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.repository import PrefRepository, PetRepository   # Pet 존재·소유권 확인용
from db.session import get_db
from core.security import get_current_user
from db.models import User
from schemas.pref import PrefRequest

router = APIRouter(prefix="/pets/{pet_id}/preferences", tags=["일일목표치"])

def _assert_pet_owned(pet_id: int, user_id: int, db: Session):
    """pet_id 가 실제 존재하고, 요청 유저가 소유 중인지 확인. 없으면 404 / 403 던짐."""
    pet = PetRepository(db).get_by_id(owner_id=user_id, pet_id=pet_id)
    if not pet:
        raise HTTPException(404, detail="반려동물을 찾을 수 없습니다.")
    return pet  # 필요하면 리턴

@router.get("/", response_model=PrefRequest, summary="반려견 기본 목표 조회")
def get_pref(
    pet_id: int,
    user : User = Depends(get_current_user),
    db   : Session = Depends(get_db),
):
    _assert_pet_owned(pet_id, user.id, db)          # ❶ 소유권 확인
    pref = PrefRepository(db).get(pet_id)           # ❷ 없으면 기본값 생성
    return PrefRequest.model_validate(pref, from_attributes=True)         # Pydantic 변환

@router.put("/", response_model=PrefRequest, summary="목표치(횟수) 설정·수정")
def set_pref(
    pet_id: int,
    body  : PrefRequest,
    user  : User = Depends(get_current_user),
    db    : Session = Depends(get_db),
):
    _assert_pet_owned(pet_id, user.id, db)
    PrefRepository(db).update(pet_id, body.meals_target, body.walks_target)
    return body   # 200 OK + 변경 내용 echo
