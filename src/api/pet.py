# src/api/pet.py
"""Pet route /pets prefix"""

from fastapi import APIRouter, Depends, File, UploadFile, status, HTTPException
from db.models import User
from db.repository import PetRepository
from schemas.pet import PetCreateRequest, PetUpdateRequest
from schemas.pet import PetSchema
from core.security import get_current_user
from utils.file import save_pet_image


router = APIRouter(prefix="/pets", tags=["Pet Profile"])

@router.post("/", response_model=PetSchema, status_code=201, summary="반려동물 등록")
def create_pet(
    req: PetCreateRequest = Depends(PetCreateRequest.as_form),  # 폼 변환 util 사용
    pet_photo: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
    repo: PetRepository = Depends(),
):
    image_path = None
    if pet_photo:
        image_path = save_pet_image(pet_photo)  # utils.file의 함수로 일원화

    pet = repo.create(owner_id=current_user.id, data=req, image_path=image_path)
    return pet

# 25-05-21 전부 추가
@router.get("/{pet_id}", response_model=PetSchema, summary="반려동물 단건조회")
def get_pet(
    pet_id: int,
    current_user: User = Depends(get_current_user),
    repo: PetRepository = Depends(),
):
    pet = repo.get_by_id(current_user.id, pet_id)
    if not pet:
        raise HTTPException(404, "반려동물을 찾을 수 없습니다.")
    return pet

# 25-05-21 전부 추가
@router.patch("/{pet_id}", response_model=PetSchema, summary="반려동물 정보 수정")  # PUT 도 동일 로직, 원하는 verb 선택
def update_pet(
    pet_id: int,
    data: PetUpdateRequest = Depends(PetUpdateRequest.as_form),
    pet_photo: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
    repo: PetRepository = Depends(),
):
    pet = repo.get_by_id(current_user.id, pet_id)
    if not pet:
        raise HTTPException(404, "반려동물을 찾을 수 없습니다.")

    new_path: str | None = None
    if pet_photo:
        new_path = save_pet_image(pet_photo)   # util 재사용

    pet = repo.update(pet, data, new_photo=new_path)
    return pet

# 25-05-21 전부 추가
@router.delete("/{pet_id}", status_code=204, summary="노예 해방")
def delete_pet(
    pet_id: int,
    current_user: User = Depends(get_current_user),
    repo: PetRepository = Depends(),
):
    pet = repo.get_by_id(current_user.id, pet_id)
    if not pet:
        raise HTTPException(404, "반려동물을 찾을 수 없습니다.")
    repo.delete(pet)


@router.get("/", response_model=list[PetSchema],summary="반려동물 리스트업")
def list_my_pets(
    current_user: User = Depends(get_current_user),
    repo: PetRepository = Depends(),
):
    pets = repo.get_all(owner_id=current_user.id)

    if not pets:
        raise HTTPException(status_code=404,detail="등록된 반려동물이 없습니다.")
    return pets
