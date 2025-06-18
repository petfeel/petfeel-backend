# src/api/record.py

from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from db.session import get_db
from db.models.pet_recorded import PetRecorded
from db.models.pet import PetProfile

# 프로젝트 루트/results/videos 폴더
VIDEO_DIR = (
    Path(__file__).resolve()
        .parent.parent.parent  # -> 프로젝트 루트(back_test)
    / "results"
    / "videos"
)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)  # 폴더가 없으면 자동 생성

router = APIRouter(prefix="/record", tags=["record"])


@router.post("/upload", summary="펫 영상 업로드 (DB 저장)")
async def upload_video(
    pet_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith((".mp4", ".avi", ".mov")):
        raise HTTPException(status_code=400, detail="지원되지 않는 비디오 형식입니다.")

    pet = db.query(PetProfile).get(pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="해당하는 PetProfile이 없습니다.")

    content = await file.read()
    rec = PetRecorded(
        pet_id=pet_id,
        video_name=file.filename,
        recorded_video=content
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    return JSONResponse(
        status_code=201,
        content={"id": rec.id, "video_name": rec.video_name}
    )


@router.get("/list", summary="영상 목록 조회 + 누락된 파일 자동 DB 등록")
def list_recorded_videos(request: Request, db: Session = Depends(get_db)):
    # 1) 폴더 스캔 → DB 자동 등록
    for fp in VIDEO_DIR.iterdir():
        if not fp.is_file() or not fp.name.lower().endswith((".mp4", ".avi", ".mov")):
            continue
        exists = db.query(PetRecorded).filter_by(video_name=fp.name).first()
        if exists:
            continue
        pet = db.query(PetProfile).first()
        if not pet:
            raise HTTPException(status_code=500, detail="펫 프로필이 없습니다.")
        new_rec = PetRecorded(
            pet_id=pet.id,
            video_name=fp.name,
            recorded_video=fp.read_bytes()
        )
        db.add(new_rec)
        db.commit()
        db.refresh(new_rec)

    # 2) DB 전체 조회 후 리턴
    base_url = str(request.base_url).rstrip("/")
    items = []
    for r in db.query(PetRecorded).order_by(PetRecorded.created_at.desc()).all():
        pet = db.query(PetProfile).get(r.pet_id)
        items.append({
            "id": str(r.id),
            "title": r.video_name,
            "thumbnail": f"{base_url}/videos/{r.video_name}",
            "channel": pet.name if pet else None,
            "url": f"{base_url}/videos/{r.video_name}",
        })

    return JSONResponse(
        status_code=200,
        content={"status": "success", "items": items}
    )


@router.get("/play/{record_id}", summary="영상 스트리밍/다운로드")
def play_video(record_id: int, db: Session = Depends(get_db)):
    rec = db.query(PetRecorded).get(record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="해당 ID의 영상이 없습니다.")

    phys = VIDEO_DIR / rec.video_name
    if phys.exists():
        return FileResponse(str(phys), media_type="video/mp4", filename=rec.video_name)

    # blob fallback
    tmp = Path("/tmp") / rec.video_name
    tmp.write_bytes(rec.recorded_video)
    return FileResponse(str(tmp), media_type="video/mp4", filename=rec.video_name)


@router.put("/rename/{record_id}", summary="영상 이름 변경")
async def rename_video(
    record_id: int,
    new_name: str = Form(...),
    db: Session = Depends(get_db),
):
    rec = db.query(PetRecorded).get(record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="해당 ID의 영상이 없습니다.")

    old_fname = rec.video_name
    ext = Path(old_fname).suffix
    new_fname = f"{new_name}{ext}"
    old_path = VIDEO_DIR / old_fname
    new_path = VIDEO_DIR / new_fname

    if not old_path.exists():
        raise HTTPException(status_code=404, detail="기존 영상 파일을 찾을 수 없습니다.")

    try:
        old_path.rename(new_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일명 변경 중 오류: {e}")

    rec.video_name = new_fname
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        new_path.rename(old_path)
        raise HTTPException(status_code=500, detail=f"DB 업데이트 중 오류: {e}")

    return {"id": rec.id, "video_name": rec.video_name}


@router.delete("/delete/{record_id}", summary="영상 메타·파일 삭제")
def delete_video(record_id: int, db: Session = Depends(get_db)):
    rec = db.query(PetRecorded).get(record_id)
    if not rec:
        raise HTTPException(status_code=404, detail="삭제할 영상이 없습니다.")

    db.delete(rec)
    db.commit()

    phys = VIDEO_DIR / rec.video_name
    if phys.exists():
        phys.unlink(missing_ok=True)

    return JSONResponse(
        status_code=200,
        content={"detail": "삭제 완료"}
    )
