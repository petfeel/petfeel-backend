# src/utils/file.py
"""파일 업로드 관련 공통 유틸"""
from __future__ import annotations
from pathlib import Path
import uuid, shutil, os

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # 프로젝트 루트
UPLOAD_DIR = BASE_DIR / "static" / "pets"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def save_pet_image(upload_file) -> str:
    """
    UploadFile을 받아서 /static/pets/ 이하에 저장한 뒤
    **브라우저에서 접근 가능한 URL Path**(`/static/pets/xxx.jpg`)를 반환.
    """
    # 원본 확장자 유지 (없으면 .jpg 기본)
    ext = os.path.splitext(upload_file.filename)[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / filename

    with dest.open("wb") as target:
        shutil.copyfileobj(upload_file.file, target)

    # 리턴 경로는 슬래시(`/`)로 통일해야 브라우저에서 접근 가능
    return f"/static/pets/{filename.replace(os.sep, '/')}"
