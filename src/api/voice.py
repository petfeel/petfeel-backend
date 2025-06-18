from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Request
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, root_validator
from sqlalchemy.orm import Session

import mimetypes
import io

from db.session import get_db
from services.voice_service import VoiceService

router = APIRouter(prefix="/voice", tags=["voice"])
voice_service = VoiceService()


# ───────────────────────── Pydantic 모델 ─────────────────────────
class VoiceResponse(BaseModel):
    id: int
    pet_name: str
    filename: str
    recorded_at: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "pet_name": "멍멍이",
                "filename": "음성명령1.mp3",
                "recorded_at": datetime.now().isoformat(),
            }
        }


class VoiceItem(BaseModel):
    id: int
    title: str
    subtitle: Optional[str] = ""
    duration: str
    file_path: str


class VoiceListResponse(BaseModel):
    items: List[VoiceItem]


class RenameRequest(BaseModel):
    title: Optional[str] = None
    filename: Optional[str] = None
    subtitle: Optional[str] = None

    @root_validator(pre=True)
    def coerce_title_to_filename(cls, values):
        # 클라이언트가 title만 보냈을 때 filename으로 복사
        if 'title' in values and not values.get('filename'):
            values['filename'] = values['title']
        return values


# ───────────────────────── 업로드 ─────────────────────────
@router.post("/upload/{pet_name}", response_model=VoiceResponse)
async def upload_voice(
    pet_name: str,
    file: UploadFile = File(..., description="음성 파일"),
    db: Session = Depends(get_db),
) -> VoiceResponse:
    try:
        voice_data = await file.read()
        return await voice_service.save_voice_recording(
            db=db,
            pet_name=pet_name,
            voice_data=voice_data,
            filename=file.filename,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────── 전체 목록 (Flutter용) ─────────────────────────
@router.get("/list", response_model=VoiceListResponse)
async def list_voices(request: Request, db: Session = Depends(get_db)) -> VoiceListResponse:
    try:
        base = str(request.base_url).rstrip("/")
        rows = await voice_service.get_all_recordings(db)
        items = [
            VoiceItem(
                id=r.get("id"),
                title=r.get("filename", ""),
                subtitle=r.get("pet_name", ""),
                duration=r.get("duration", "00:00"),
                file_path=f"{base}/voice/play/{r['id']}",
            )
            for r in rows
        ]
        return VoiceListResponse(items=items)
    except Exception as e:
        print(f"[voice.list] internal error: {e}")
        raise HTTPException(status_code=500, detail="목록 조회 중 오류가 발생했습니다")


# ───────────────────────── 이름 변경 ─────────────────────────
@router.patch(
    "/{recording_id}",
    response_model=VoiceResponse,
    summary="녹음 파일 이름/부제목 변경"
)
async def rename_recording(
    recording_id: int,
    payload: RenameRequest,
    db: Session = Depends(get_db),
) -> VoiceResponse:
    try:
        updated_record = await voice_service.rename_recording(
            db=db,
            recording_id=recording_id,
            new_filename=payload.filename,
            new_subtitle=payload.subtitle,
        )
        return updated_record
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────── 삭제 ─────────────────────────
@router.delete("/{recording_id}")
async def delete_recording(
    recording_id: int,
    db: Session = Depends(get_db),
):
    try:
        await voice_service.delete_recording(db, recording_id)
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ───────────────────────── 스트리밍 (ID 기반) ─────────────────────────
@router.get("/play/{recording_id}")
async def stream_voice(recording_id: int, db: Session = Depends(get_db)):
    file_info = await voice_service.get_voice_file(recording_id, db)
    if not file_info:
        raise HTTPException(status_code=404, detail="음성 파일을 찾을 수 없습니다")

    # 파일명 기반으로 MIME 타입 추출
    mime_type, _ = mimetypes.guess_type(file_info["filename"])
    buffer = io.BytesIO(file_info["voice_data"])

    return StreamingResponse(
        buffer,
        media_type=mime_type or "application/octet-stream",
        headers={"Accept-Ranges": "bytes"},
    )


# ───────────────────────── 파일 이름 목록 (pet_name) ─────────────────────────
@router.get("/filenames/{pet_name}", response_model=List[str])
async def get_voice_filenames(pet_name: str, db: Session = Depends(get_db)) -> List[str]:
    return await voice_service.get_voice_filenames(db, pet_name)


# ───────────────────────── pet_name별 녹음 메타데이터 ─────────────────────────
@router.get(
    "/recordings/{pet_name}",
    response_model=List[VoiceResponse],
    description="특정 반려동물의 모든 음성 녹음",
)
async def get_recordings_by_pet(pet_name: str, db: Session = Depends(get_db)) -> List[VoiceResponse]:
    return await voice_service.get_recordings_by_pet_name(db, pet_name)


# ───────────────────────── 파일 다운로드 ─────────────────────────
@router.get(
    "/file/{recording_id}",
    responses={200: {"content": {"audio/mpeg": {}}, "description": "음성 파일 데이터"}},
    description="녹음 파일 다운로드",
)
async def download_voice_file(recording_id: int, db: Session = Depends(get_db)) -> Response:
    file_info = await voice_service.get_voice_file(recording_id, db)
    if not file_info:
        raise HTTPException(status_code=404, detail="음성 파일을 찾을 수 없습니다")
    return Response(
        content=file_info["voice_data"],
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'attachment; filename="{file_info["filename"]}"'},
    )


# ───────────────────────── 서버에서 음성 재생 ─────────────────────────
class ServerPlayResponse(BaseModel):
    success: bool
    message: str
    path: Optional[str] = None


@router.post(
    "/play-on-server/{recording_id}",
    response_model=ServerPlayResponse,
    description="서버 컴퓨터에서 음성 재생",
)
async def play_voice_on_server(recording_id: int, db: Session = Depends(get_db)) -> ServerPlayResponse:
    """
    서버 컴퓨터에서 음성 파일을 재생합니다.
    이 기능을 사용하려면 서버에 playsound 라이브러리가 설치되어 있어야 합니다.
    """
    try:
        result = await voice_service.play_voice_on_server(recording_id, db)
        return ServerPlayResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        # 에러 로그 출력
        import traceback
        print(f"서버 재생 오류 상세: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"서버 재생 오류: {e}")
 