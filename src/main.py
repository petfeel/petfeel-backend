"""Unified FastAPI entrypoint for the Pet Care service.

This file merges the features that were split across the two previous
`main.py` files:
  • common router registrations
  • CORS & static mounts ("/static" and "/videos")
  • WebSocket notification hub (client‑specific and broadcast)
  • background `process_video` thread for continuous detection
  • summary/diary/event REST endpoints (single authoritative versions)

Remove the old duplicate `main.py` files and run this one instead.
"""

import os
import sys
import json
import threading
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional
import io

from fastapi import (
    FastAPI,
    Depends,
    File,
    UploadFile,
    Form,
    HTTPException,
    WebSocket,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import and_, MetaData
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import google.generativeai as genai

# ────────────────────────────────────────────────────────────
# Local‑package import path fix
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
    print(f"Added to path: {parent_dir}")

from db.session import engine, get_db, SessionLocal
from db.base import Base

# Routers
from api.pet import router as pet_router
from api.auth import router as auth_router
from api.user_info import router as user_router
from api.events import router as events_router
from api.detection import router as detection_router
from api.detection import manager as ws_manager
from api import routine, pref, stream, voice
from api.voice import router as voice_router
from api.record import router as record_router
from endpoints.daily_summary import router as daily_summary_router

# Models & utils
from db.models.event import Event, DailySummary
from db.models.pet import PetProfile
from utils.summary_generator import (
    generate_normal_summary,
    generate_abnormal_summary,
    generate_and_save_summaries,
)
from services.stream_service import cleanup
from detector.detection import process_video, USE_CAMERA

# ────────────────────────────────────────────────────────────
# Environment & external services
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    LLM = genai.GenerativeModel("models/gemini-2.5-flash-preview-05-20")

# Database metadata reflection (dev‑time convenience)
metadata = MetaData()
metadata.reflect(bind=engine)
Base.metadata = metadata

# ────────────────────────────────────────────────────────────
# FastAPI app setup
app = FastAPI(title="통합 반려동물 케어 서비스 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 마운트
BASE_DIR = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# 비디오 디렉토리 설정 및 마운트
UPLOAD_DIR = BASE_DIR / "results" / "videos"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/videos", StaticFiles(directory=str(UPLOAD_DIR)), name="videos")

# 추가 비디오 디렉토리 생성 및 마운트
VIDEOS_DIR = BASE_DIR / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/videos-alt", StaticFiles(directory=str(VIDEOS_DIR)), name="videos-alt")

# Router registration (single list keeps things tidy)
routers = [
    auth_router,
    user_router,
    pet_router,
    pref.router,
    routine.router,
    stream.router,
    events_router,
    voice_router,
    detection_router,
    record_router,
    daily_summary_router,
]
for r in routers:
    # events_router already carries prefix/tags inside the include above
    if r is events_router:
        app.include_router(r, prefix="/events", tags=["Events"])
    else:
        app.include_router(r)

# ────────────────────────────────────────────────────────────
# Lifecycle hooks
_detection_thread: threading.Thread | None = None

def _run_process_video():
    """
    비동기 process_video 함수를 스레드에서 실행하기 위한 래퍼 함수
    """
    import asyncio
    from db.session import SessionLocal
    
    # USE_CAMERA가 False이면 실행하지 않음
    if not USE_CAMERA:
        print("▶ 카메라 모드가 비활성화되어 있습니다. 영상 업로드 시 처리됩니다.")
        return
    
    # 새로운 이벤트 루프 생성
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # 데이터베이스 세션 생성
        db = SessionLocal()
        
        # 비동기 함수를 동기적으로 실행
        # process_video는 인자로 video_path, use_camera, db, pet_id를 받을 수 있음
        # 여기서는 카메라 모드로 기본 설정을 사용
        loop.run_until_complete(process_video(use_camera=USE_CAMERA, db=db))
    except Exception as e:
        print(f"⚠️ 영상 처리 오류: {e}")
        import traceback
        print(traceback.format_exc())
    finally:
        loop.close()

@app.on_event("startup")
def _startup():
    print("▶ create_all called")
    print("▶ Engine URL =", engine.url)
    Base.metadata.create_all(bind=engine, checkfirst=True)

    global _detection_thread
    _detection_thread = threading.Thread(target=_run_process_video, daemon=True)
    _detection_thread.start()
    print("▶ Detection process started")


@app.on_event("shutdown")
def _shutdown():
    cleanup()
    print("▶ Server shutting down")

# ────────────────────────────────────────────────────────────
# WebSocket endpoints
# 기존 WebSocket 엔드포인트는 api/detection.py에 정의되어 있지만,
# 클라이언트 호환성을 위해 detection 프리픽스 없이도 접근 가능하도록 추가 등록

@app.websocket("/notifications/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    """클라이언트 호환성을 위한 WebSocket 연결 엔드포인트"""
    print(f"WebSocket 연결 시도: client_id={client_id}")
    try:
        await ws_manager.connect(websocket, client_id)
        print(f"WebSocket 연결 수락: client_id={client_id}")
        
        # 연결 확인 메시지 전송
        await ws_manager.send_personal_message(
            json.dumps({
                "type": "connection_established",
                "message": "WebSocket 연결이 설정되었습니다"
            }),
            client_id
        )
        
        # 클라이언트로부터 메시지 수신 대기
        while True:
            try:
                data = await websocket.receive_text()
                print(f"클라이언트 {client_id}로부터 메시지 수신: {data}")
                
                # 클라이언트에게 응답 (에코)
                await ws_manager.send_personal_message(
                    json.dumps({
                        "type": "echo",
                        "message": f"메시지 수신 완료: {data}"
                    }),
                    client_id
                )
            except Exception as e:
                print(f"WebSocket 처리 중 오류: {str(e)}")
                break
    except Exception as e:
        print(f"WebSocket 연결 실패: {str(e)}")
    finally:
        ws_manager.disconnect(client_id)

@app.websocket("/notifications/broadcast")
async def notification_broadcast(websocket: WebSocket):
    """클라이언트 호환성을 위한 브로드캐스트 엔드포인트"""
    try:
        await websocket.accept()
        print(f"브로드캐스트 WebSocket 연결 수락")
        
        # 메시지 수신 및 브로드캐스트
        data = await websocket.receive_text()
        print(f"브로드캐스트할 알림 수신: {data}")
        
        # 모든 연결된 클라이언트에게 브로드캐스트
        await ws_manager.broadcast(data)
        
        # 전송 확인 응답
        await websocket.send_text(json.dumps({
            "type": "broadcast_result",
            "success": True,
            "client_count": len(ws_manager.active_connections)
        }))
    except Exception as e:
        print(f"알림 브로드캐스트 중 오류: {str(e)}")
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            # 이미 닫힌 연결에 대한 오류 무시
            pass

@app.post("/notifications")
async def send_notification(notification: dict):
    try:
        await ws_manager.broadcast(json.dumps(notification))
        return {"success": True, "client_count": len(ws_manager.active_connections)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# ────────────────────────────────────────────────────────────
# Health‑check
@app.get("/")
async def health_check():
    return {"status": "ok"}

# ────────────────────────────────────────────────────────────
# Diary & summary helpers

def _get_pet_or_404(db: Session, pet_id: int) -> PetProfile:
    pet = db.query(PetProfile).filter(PetProfile.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="반려동물을 찾을 수 없습니다")
    return pet


@app.get("/diary/{pet_id}/{year}/{month}/{day}")
def get_diary(pet_id: int, year: int, month: int, day: int, db: Session = Depends(get_db)):
    _get_pet_or_404(db, pet_id)
    target_date = date(year, month, day)
    normal, abnormal = generate_and_save_summaries(pet_id, target_date)
    return {
        "pet_id": pet_id,
        "date": f"{year:04d}-{month:02d}-{day:02d}",
        "normal_diary": normal,
        "abnormal_diary": abnormal,
    }


@app.get("/daily-summary/{pet_id}/{date}")
async def get_daily_summary(pet_id: int, date: str, db: Session = Depends(get_db)):
    _get_pet_or_404(db, pet_id)
    target_date = datetime.strptime(date, "%Y-%m-%d").date()
    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())

    normal_events = db.query(Event).filter(
        and_(Event.pet_id == pet_id, Event.created_at.between(start_dt, end_dt), Event.stage == 0)
    ).all()
    abnormal_events = db.query(Event).filter(
        and_(Event.pet_id == pet_id, Event.created_at.between(start_dt, end_dt), Event.stage > 0)
    ).all()

    normal_summary = generate_normal_summary(normal_events)
    abnormal_summary = generate_abnormal_summary(abnormal_events)

    # Upsert daily summary in DB
    summary_row = db.query(DailySummary).filter(
        and_(DailySummary.pet_id == pet_id, DailySummary.date == target_date)
    ).first()
    if summary_row:
        summary_row.normal_summary = normal_summary
        summary_row.abnormal_summary = abnormal_summary
    else:
        db.add(
            DailySummary(
                pet_id=pet_id,
                date=target_date,
                normal_summary=normal_summary,
                abnormal_summary=abnormal_summary,
            )
        )
    db.commit()

    return {
        "pet_id": pet_id,
        "date": date,
        "normal_summary": normal_summary,
        "abnormal_summary": abnormal_summary,
        "normal_events": [{"timestamp": e.created_at, "summary": e.summary} for e in normal_events],
        "abnormal_events": [
            {"timestamp": e.created_at, "stage": e.stage, "summary": e.summary}
            for e in abnormal_events
        ],
    }


@app.get("/weekly-summary/{pet_id}")
async def get_weekly_summary(pet_id: int, start_date: str, db: Session = Depends(get_db)):
    _get_pet_or_404(db, pet_id)
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = start + timedelta(days=6)

    summaries = (
        db.query(DailySummary)
        .filter(and_(DailySummary.pet_id == pet_id, DailySummary.date.between(start, end)))
        .order_by(DailySummary.date)
        .all()
    )

    return {
        "pet_id": pet_id,
        "start_date": start_date,
        "end_date": end.strftime("%Y-%m-%d"),
        "summaries": [
            {
                "date": s.date.strftime("%Y-%m-%d"),
                "normal_summary": s.normal_summary,
                "abnormal_summary": s.abnormal_summary,
            }
            for s in summaries
        ],
    }

# ────────────────────────────────────────────────────────────
# Event creation & listing
@app.post("/events")
@app.post("/event")
async def create_event(
    pet_id: int = Form(...),
    stage: int = Form(...),
    summary: str = Form(...),
    video_data: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    _get_pet_or_404(db, pet_id)

    video_name = None
    video_binary = None
    if video_data:
        content = await video_data.read()
        if len(content) > 500 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="영상 파일이 너무 큽니다 (최대 500MB)")
        video_name = video_data.filename
        video_binary = content

    event = Event(
        pet_id=pet_id,
        stage=stage,
        summary=summary,
        video_name=video_name,
        video_data=video_binary,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    # Send WebSocket notification (best effort)
    try:
        stage_msgs = {
            0: "반려동물이 정상적인 행동을 하고 있습니다.",
            1: "반려동물이 다소 불안한 행동을 보이고 있습니다.",
            2: "반려동물이 주의가 필요한 행동을 보이고 있습니다.",
            3: "반려동물이 심각한 이상행동을 보이고 있습니다.",
        }
        import re

        behavior_desc = re.search(r"1\.\s*(.*?)(?=\s*\d+\.|\s*$)", summary, re.DOTALL)
        action_plan = re.search(r"3\.\s*(.*?)(?=\s*\d+\.|\s*$)", summary, re.DOTALL)
        notification = {
            "type": "notification",
            "event_id": event.id,
            "pet_id": pet_id,
            "stage": str(stage),
            "message": "반려동물의 이상행동이 감지되었습니다.",
            "behavior_report": summary,
            "behavior_description": (behavior_desc.group(1).strip() if behavior_desc else stage_msgs.get(stage)),
            "action_plan": (action_plan.group(1).strip() if action_plan else "추가적인 이상행동이 있는지 주의 깊게 관찰하세요."),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        await ws_manager.broadcast(json.dumps(notification, ensure_ascii=False))
    except Exception as exc:
        print(f"⚠️ WebSocket 알림 전송 실패: {exc}")

    return {"message": "이벤트가 성공적으로 등록되었습니다", "event_id": event.id}


@app.get("/events")
async def get_events(
    pet_id: Optional[int] = None,
    since_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    query = db.query(Event).order_by(Event.created_at.desc())
    if pet_id is not None:
        query = query.filter(Event.pet_id == pet_id)
    if since_id is not None:
        query = query.filter(Event.id > since_id)
    events = query.offset(skip).limit(limit).all()
    return [
        {
            "id": e.id,
            "pet_id": e.pet_id,
            "created_at": e.created_at,
            "stage": e.stage,
            "summary": e.summary,
            "video_name": e.video_name,
            "has_video": e.video_data is not None,
        }
        for e in events
    ]

# 이벤트의 비디오 데이터를 가져오는 엔드포인트
@app.get("/events/{event_id}/video")
async def get_event_video(event_id: int, db: Session = Depends(get_db)):
    """이벤트 비디오 다운로드"""
    # 이벤트 존재 확인
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다")
    
    # 비디오 이름 확인
    if not event.video_name:
        raise HTTPException(status_code=404, detail="이 이벤트에는 비디오가 없습니다")
    
    print(f"비디오 요청: 이벤트 ID={event_id}, 비디오 이름={event.video_name}")
    
    # 이벤트의 video_data가 있는 경우 (바이너리 데이터)
    if event.video_data:
        print(f"비디오 데이터 크기: {len(event.video_data)} 바이트")
        video_stream = io.BytesIO(event.video_data)
        return StreamingResponse(
            video_stream, 
            media_type="video/mp4",
            headers={"Content-Disposition": f"attachment; filename={event.video_name}"}
        )
    
    # 비디오 파일 시스템에서 찾기
    try:
        # 비디오 파일 경로 (여러 가능한 위치 확인)
        video_dirs = [
            Path("./videos"),
            Path("./uploads/videos"),
            Path("./results/videos"),
            Path("./back_test/videos"),
            Path("./assets/videos"),
            Path("/videos"),
            BASE_DIR / "results" / "videos",
            BASE_DIR / "videos",
        ]
        
        found_video_path = None
        for video_dir in video_dirs:
            video_path = video_dir / event.video_name
            if video_path.exists():
                found_video_path = video_path
                print(f"비디오 파일 찾음: {video_path}")
                break
            
        if found_video_path:
            return StreamingResponse(
                open(found_video_path, "rb"),
                media_type="video/mp4",
                headers={"Content-Disposition": f"attachment; filename={event.video_name}"}
            )
    except Exception as e:
        print(f"파일 시스템 검색 중 오류: {e}")
    
    # 비디오 데이터가 없는 경우 404 반환
    raise HTTPException(status_code=404, detail="비디오 데이터를 찾을 수 없습니다")

# 호환성을 위한 대체 엔드포인트
@app.get("/event/{event_id}/video")
async def get_event_video_alt(event_id: int, db: Session = Depends(get_db)):
    """이벤트 비디오 다운로드 (대체 URL)"""
    return await get_event_video(event_id, db)

@app.get("/video/{event_id}")
async def get_video(event_id: int, db: Session = Depends(get_db)):
    """이벤트 비디오 다운로드 (대체 URL 2)"""
    return await get_event_video(event_id, db)

# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
