from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from pathlib import Path
from urllib.parse import quote
import time

from db.session import get_db
from services import stream_service
from db.models.pet_recorded import PetRecorded

router = APIRouter()

@router.get("/stream")
def video_stream():
    """MJPEG 실시간 스트림"""
    return StreamingResponse(
        stream_service.stream_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

@router.post("/record/start/{pet_id}")
def start_recording(pet_id: int, db: Session = Depends(get_db)):
    """녹화 시작"""
    if stream_service.is_recording():
        raise HTTPException(status_code=400, detail="이미 녹화 중입니다")
    try:
        stream_service.start_recording(pet_id)
        return {"status": "success", "message": f"ID {pet_id} 녹화를 시작했습니다"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/record/stop")
def stop_recording(request: Request, db: Session = Depends(get_db)):
    """
    녹화 중지 → 파일 생성 후
    file_name, file_path, file_url 반환 (DB 저장은 rename 시점에)
    """
    if not stream_service.is_recording():
        raise HTTPException(status_code=400, detail="현재 녹화 중이 아닙니다")
    try:
        filename, abs_path = stream_service.stop_recording()

        if not filename:
            raise RuntimeError("파일 생성 실패")

        base_url = str(request.base_url).rstrip("/")
        file_url = f"{base_url}/record/file/{quote(filename)}"
        return {
            "status": "success",
            "file_name": filename,
            "file_path": abs_path,
            "file_url": file_url,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/record/status")
def record_status():
    """현재 녹화 상태 조회"""
    return {"is_recording": stream_service.is_recording()}

@router.get("/record/list")
def list_recorded_videos(request: Request, db: Session = Depends(get_db)):
    """
    녹화 영상 목록 조회
    id, title, channel, thumbnail, url 제공
    """
    base_url = str(request.base_url).rstrip("/")
    records = (
        db.query(PetRecorded)
          .order_by(PetRecorded.created_at.desc())
          .all()
    )

    items = []
    for r in records:
        encoded = quote(r.video_name)
        pet_name = r.pet.pet_name if getattr(r, "pet", None) else ""
        items.append({
            "id": str(r.id),
            "title": r.video_name,
            "channel": pet_name,
            "thumbnail": "",
            "url": f"{base_url}/record/file/{encoded}",
        })

    return {"status": "success", "items": items}

@router.get("/record/files")
def debug_list_files():
    """
    디버그용: 디스크에 저장된 파일명 리스트 반환
    """
    record_dir = Path(stream_service.RECORD_DIR)
    if not record_dir.exists():
        raise HTTPException(status_code=500, detail="녹화 폴더를 찾을 수 없습니다")
    files = [p.name for p in record_dir.iterdir() if p.is_file()]
    return {"files": files}

@router.get("/record/file/{filename}")
def serve_recorded_file(filename: str):
    """
    Record 파일 재생/다운로드
    """
    record_dir = Path(stream_service.RECORD_DIR)
    path = record_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="파일이 없습니다")
    return FileResponse(path, media_type="video/mp4")

class RenameRequest(BaseModel):
    video_name: str

@router.post("/record/stop/rename")
def rename_recorded_video(
    payload: RenameRequest,
    db: Session = Depends(get_db),
):
    """
    최신 디스크 파일 이름 변경 후 DB에 저장
    """
    record_dir = Path(stream_service.RECORD_DIR)

    # 1) 최신 파일 찾기
    files = sorted(
        [p for p in record_dir.iterdir() if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    if not files:
        raise HTTPException(status_code=404, detail="녹화 파일을 찾을 수 없습니다")
    old_path = files[0]
    old_name = old_path.name

    new_name = payload.video_name
    new_path = record_dir / new_name

    if not old_path.exists():
        raise HTTPException(status_code=404, detail=f"원본 파일이 없습니다: {old_name}")

    # ✅ 이미 존재하면 삭제 (잠금 방지 위해 대기)
    if new_path.exists():
        try:
            time.sleep(0.2)
            new_path.unlink()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"기존 파일 삭제 실패: {e}")

    # 2) 이름 변경
    try:
        old_path.rename(new_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일명 변경 실패: {e}")

    # 3) DB 저장
    try:
        with open(new_path, "rb") as f:
            data = f.read()
        pet_id = int(old_name.split("_")[1])
        db_rec = PetRecorded(
            pet_id=pet_id,
            recorded_video=data,
            video_name=new_name,
        )
        db.add(db_rec)
        db.commit()
    except Exception as e:
        new_path.rename(old_path)
        raise HTTPException(status_code=500, detail=f"DB 저장 실패: {e}")

    return {"status": "success", "video_name": new_name}

@router.delete("/record/{video_id}")
def delete_recorded_video(
    video_id: int,
    db: Session = Depends(get_db),
):
    """
    녹화 영상 삭제 (디스크 + DB)
    """
    rec = db.query(PetRecorded).filter(PetRecorded.id == video_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="녹화 레코드를 찾을 수 없습니다")

    record_dir = Path(stream_service.RECORD_DIR)
    path = record_dir / rec.video_name
    if path.exists():
        try:
            path.unlink()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"파일 삭제 실패: {e}")

    try:
        db.delete(rec)
        db.commit()
        return {"status": "success", "message": "삭제되었습니다"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB 삭제 실패: {e}")
