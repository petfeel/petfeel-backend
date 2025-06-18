# src/api/routine.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from db.session import get_db
from core.security import get_current_user
from db.repository import PrefRepository, RoutineRepository, PetRepository
from schemas.routine import RoutineSchema, RoutineUpsertRequest
from db.models import User

router = APIRouter(prefix="/pets/{pet_id}/routines", tags=["Routine"])

def _assert_pet_owned(pet_id: int, user_id: int, db: Session):
    if not PetRepository(db).get_by_id(owner_id=user_id, pet_id=pet_id):
        raise HTTPException(404, "반려동물을 찾을 수 없습니다.")

@router.post(
    "/",
    response_model=RoutineSchema,
    status_code=201,
    summary="루틴 생성(있으면 수정)",
)
def upsert_routine(
    pet_id: int,
    req   : RoutineUpsertRequest = Depends(RoutineUpsertRequest.as_form),
    user  : User = Depends(get_current_user),
    db    : Session = Depends(get_db),
):
    _assert_pet_owned(pet_id, user.id, db)
    pref_repo    = PrefRepository(db)
    routine_repo = RoutineRepository(db)
    routine = routine_repo.upsert(pet_id, req, pref_repo.get(pet_id))
    return routine                    # ← 201 Created + 저장된 객체

@router.get(
    "/",
    response_model=list[RoutineSchema],
    summary="지정 월(月) 루틴 목록",
)
def month_routines(
    pet_id: int,
    year : int = Query(..., ge=2020),
    month: int = Query(..., ge=1, le=12),
    user : User = Depends(get_current_user),
    db   : Session = Depends(get_db),
):
    _assert_pet_owned(pet_id, user.id, db)
    routines = RoutineRepository(db).month(pet_id, year, month)
    return routines   # [] 빈 배열이라도 200 OK
