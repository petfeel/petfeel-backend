# src/dbb/repository.py
from __future__ import annotations

from calendar import monthrange
from datetime import date

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.session import get_db
from db.models.pet import PetProfile, PetPreference, PetRoutine
from db.models.user import User
from schemas.pet import PetCreateRequest, PetUpdateRequest
from schemas.routine import RoutineUpsertRequest


# ────────────────────────── User ──────────────────────────
class UserRepository:
    def __init__(self, session: Session = Depends(get_db)):
        self.session = session

    # 조회
    def get_by_username(self, username: str) -> User | None:
        return self.session.scalar(
            select(User).where(User.username == username)
        )

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(
            select(User).where(User.email == email)
        )

    # 저장
    def save(self, user: User) -> User:
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    # 중복 검사
    def ensure_unique(self, *, username: str, email: str) -> None:
        if self.get_by_username(username):
            raise HTTPException(409, "이미 존재하는 사용자명입니다.")
        if self.get_by_email(email):
            raise HTTPException(409, "이미 사용 중인 이메일입니다.")


# ────────────────────────── Pet ──────────────────────────
class PetRepository:
    def __init__(self, session: Session = Depends(get_db)):
        self.session = session

    def create(self, owner_id: int, data: PetCreateRequest,
               image_path: str | None) -> PetProfile:
        pet = PetProfile(owner_id=owner_id, **data.model_dump(),
                         image_path=image_path)
        self.session.add(pet)
        self.session.commit()
        self.session.refresh(pet)
        return pet

    def get_by_id(self, owner_id: int, pet_id: int) -> PetProfile | None:
        return self.session.scalar(
            select(PetProfile)
            .where(PetProfile.id == pet_id,
                   PetProfile.owner_id == owner_id)
        )

    def get_all(self, owner_id: int) -> list[PetProfile]:
        return self.session.scalars(
            select(PetProfile).where(PetProfile.owner_id == owner_id)
        ).all()

    def update(self, pet: PetProfile, data: PetUpdateRequest,
               new_photo: str | None = None) -> PetProfile:
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(pet, k, v)
        if new_photo:
            pet.image_path = new_photo
        self.session.commit()
        self.session.refresh(pet)
        return pet

    def delete(self, pet: PetProfile) -> None:
        self.session.delete(pet)
        self.session.commit()


# ────────────────────────── Preference ──────────────────────────
class PrefRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, pet_id: int) -> PetPreference:
        pref = self.session.get(PetPreference, pet_id)
        if not pref:
            pref = PetPreference(pet_id=pet_id)
            self.session.add(pref)
            self.session.commit()
        return pref

    def update(self, pet_id: int, meals: int, walks: int) -> None:
        self.session.merge(
            PetPreference(pet_id=pet_id,
                          meals_target=meals,
                          walks_target=walks)
        )
        self.session.commit()


# ────────────────────────── Routine ──────────────────────────
class RoutineRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert(self, pet_id: int, data: RoutineUpsertRequest,
               defaults: PetPreference) -> PetRoutine:
        payload = data.dict()
        payload["meal_target"] = payload["meal_target"] or defaults.meals_target
        payload["walk_target"] = payload["walk_target"] or defaults.walks_target

        obj = (
            self.session.query(PetRoutine)
            .filter_by(pet_id=pet_id, date=data.date)
            .first()
        )
        if obj:
            for k, v in payload.items():
                setattr(obj, k, v)
        else:
            obj = PetRoutine(pet_id=pet_id, **payload)
            self.session.add(obj)

        self.session.commit()
        self.session.refresh(obj)
        return obj

    def month(self, pet_id: int, y: int, m: int) -> list[PetRoutine]:
        first = date(y, m, 1)
        last  = date(y, m, monthrange(y, m)[1])
        return (
            self.session.query(PetRoutine)
            .filter(PetRoutine.pet_id == pet_id,
                    PetRoutine.date.between(first, last))
            .all()
        )
