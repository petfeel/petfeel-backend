# src/schemas/pet.py
"""요청용 Pydantic 모델"""
from pydantic import BaseModel, Field
from datetime import date
from fastapi import UploadFile, File
from typing import Annotated
from fastapi import Form
from datetime import datetime,date
from db.models.common import GenderEnum

class PetCreateRequest(BaseModel):
    pet_name: str
    pet_species: str
    age: int | None = None
    birth_date: date | None = None
    gender: GenderEnum | None = None
    weight: float | None = None
       
    @classmethod
    def as_form(
        cls,
        pet_name: str       = Form(...),
        pet_species: str    = Form(...),
        age: int | None     = Form(None),
        birth_date: date | None = Form(None),
        gender: GenderEnum | None  = Form(None),
        weight: float | None = Form(None),
    ) -> "PetCreateRequest":
        return cls(
            pet_name=pet_name,
            pet_species=pet_species,
            age=age,
            birth_date=birth_date,
            gender=gender,
            weight=weight,
        )

class PetUpdateRequest(PetCreateRequest):
    pet_name:    str | None = None
    pet_species: str | None = None
    age:         int | None = None
    birth_date:  date | None = None
    gender:      GenderEnum | None = None      # 남/여
    weight:      float | None = None

    @classmethod
    def as_form(
        cls,
        pet_name:    str | None = Form(None),
        pet_species: str | None = Form(None),
        age:         int | None = Form(None),
        birth_date:  date | None = Form(None),
        gender:      GenderEnum | None = Form(None),
        weight:      float | None = Form(None),
    ):
        return cls(
            pet_name=pet_name,
            pet_species=pet_species,
            age=age,
            birth_date=birth_date,
            gender=gender,
            weight=weight,
        )
# ───── multipart/form-data 용 별도 Dependency ─────
PetPhoto = Annotated[UploadFile | None, File(None)]

class PetSchema(BaseModel):
    id: int
    pet_name: str
    pet_species: str
    age: int | None
    birth_date: date | None
    gender: GenderEnum | None
    weight: float | None
    image_path: str | None = Field(  
        default=None,
        description="이미지 파일 URL (예: /static/pets/xxx.jpg)"
    )
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True   # alias 매핑용, 지금은없음

