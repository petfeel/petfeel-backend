from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from db.session import get_db
from db.models.pet import PetProfile
from detector.detection import process_video, USE_CAMERA, set_camera_mode
import os
from pathlib import Path
import asyncio
from typing import Optional, Dict, List
import logging
import json
import time
from datetime import datetime
 
# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 
router = APIRouter(prefix="/detection", tags=["detection"])
 
# 카메라 상태 관리를 위한 클래스
class CameraState:
    def __init__(self):
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
 
camera_state = CameraState()

# WebSocket 연결 관리를 위한 클래스
class ConnectionManager:
    def __init__(self):
        # 클라이언트 ID를 키로 하는 WebSocket 연결 딕셔너리
        self.active_connections: Dict[int, WebSocket] = {}
        # 연결 상태 모니터링
        self.last_ping: Dict[int, float] = {}
        # 핑 간격 (초)
        self.ping_interval = 30
        
    async def connect(self, websocket: WebSocket, client_id: int):
        try:
            await websocket.accept()
            self.active_connections[client_id] = websocket
            self.last_ping[client_id] = time.time()
            logger.info(f"클라이언트 {client_id} 연결됨, 현재 연결: {len(self.active_connections)}개")
            # 최초 연결 시 ping 전송
            asyncio.create_task(self._keep_alive(client_id))
            return True
        except Exception as e:
            logger.error(f"클라이언트 {client_id} 연결 실패: {str(e)}")
            return False
        
    def disconnect(self, client_id: int):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            if client_id in self.last_ping:
                del self.last_ping[client_id]
            logger.info(f"클라이언트 {client_id} 연결 해제됨, 현재 연결: {len(self.active_connections)}개")
    
    async def send_personal_message(self, message: str, client_id: int):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(message)
                self.last_ping[client_id] = time.time()  # 메시지 전송도 활동으로 간주
                return True
            except Exception as e:
                logger.error(f"메시지 전송 실패 (클라이언트 {client_id}): {str(e)}")
                self.disconnect(client_id)
                return False
        return False
        
    async def broadcast(self, message: str):
        disconnected_clients = []
        for client_id, connection in list(self.active_connections.items()):
            try:
                await connection.send_text(message)
                self.last_ping[client_id] = time.time()  # 메시지 전송도 활동으로 간주
            except Exception as e:
                logger.error(f"브로드캐스트 실패 (클라이언트 {client_id}): {str(e)}")
                disconnected_clients.append(client_id)
        
        # 연결이 끊긴 클라이언트 정리
        for client_id in disconnected_clients:
            self.disconnect(client_id)
            
    async def _keep_alive(self, client_id: int):
        """
        주기적으로 핑 메시지를 보내 연결을 유지합니다.
        """
        try:
            while client_id in self.active_connections:
                await asyncio.sleep(self.ping_interval)
                
                # 연결이 이미 끊어졌는지 확인
                if client_id not in self.active_connections:
                    break
                
                # 핑 메시지 전송
                try:
                    ping_message = json.dumps({"type": "ping", "time": time.time()})
                    await self.active_connections[client_id].send_text(ping_message)
                    self.last_ping[client_id] = time.time()
                    logger.debug(f"Ping sent to client {client_id}")
                except Exception as e:
                    logger.error(f"Ping 전송 실패 (클라이언트 {client_id}): {str(e)}")
                    self.disconnect(client_id)
                    break
        except asyncio.CancelledError:
            logger.info(f"Keep-alive task for client {client_id} cancelled")
            pass
        except Exception as e:
            logger.error(f"Keep-alive error for client {client_id}: {str(e)}")
            if client_id in self.active_connections:
                self.disconnect(client_id)

# 연결 관리자 인스턴스 생성
manager = ConnectionManager()

# WebSocket 연결 엔드포인트
@router.websocket("/notifications/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    logger.info(f"WebSocket 연결 시도: client_id={client_id}")
    
    # 연결이 이미 존재하면 기존 연결 해제
    if client_id in manager.active_connections:
        logger.info(f"클라이언트 {client_id}의 기존 연결이 있어 해제합니다")
        manager.disconnect(client_id)
    
    # 새 연결 수립
    connection_result = await manager.connect(websocket, client_id)
    if not connection_result:
        logger.error(f"클라이언트 {client_id} 연결 실패")
        return
    
    try:
        # 연결 확인 메시지 전송
        await manager.send_personal_message(
            json.dumps({
                "type": "connection_established",
                "message": "WebSocket 연결이 설정되었습니다",
                "client_id": client_id,
                "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }),
            client_id
        )
        
        # 클라이언트로부터 메시지 수신 대기
        while True:
            try:
                data = await websocket.receive_text()
                logger.info(f"클라이언트 {client_id}로부터 메시지 수신: {data}")
                
                # JSON 파싱
                try:
                    json_data = json.loads(data)
                    message_type = json_data.get("type", "")
                    
                    # 핑-퐁 메시지 처리
                    if message_type == "ping":
                        await manager.send_personal_message(
                            json.dumps({
                                "type": "pong",
                                "time": time.time(),
                                "client_id": client_id
                            }),
                            client_id
                        )
                        continue
                except json.JSONDecodeError:
                    pass  # JSON이 아닌 경우 무시하고 계속 진행
                
                # 일반 메시지에 대한 응답 (에코)
                await manager.send_personal_message(
                    json.dumps({
                        "type": "echo",
                        "message": f"메시지 수신 완료: {data}",
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }),
                    client_id
                )
            except WebSocketDisconnect:
                logger.info(f"클라이언트 {client_id} WebSocket 연결 종료")
                manager.disconnect(client_id)
                break
            except Exception as e:
                logger.error(f"WebSocket 처리 중 오류 (클라이언트 {client_id}): {str(e)}")
                break
    except Exception as e:
        logger.error(f"WebSocket 엔드포인트 오류 (클라이언트 {client_id}): {str(e)}")
    finally:
        # 연결 해제 (이미 해제되었을 수 있음)
        if client_id in manager.active_connections:
            manager.disconnect(client_id)

# 알림 브로드캐스트 엔드포인트
@router.websocket("/notifications/broadcast")
async def notification_broadcast(websocket: WebSocket):
    await websocket.accept()
    try:
        # 메시지 수신 및 브로드캐스트
        data = await websocket.receive_text()
        logger.info(f"브로드캐스트할 알림 수신: {data}")
        
        # 모든 연결된 클라이언트에게 브로드캐스트
        await manager.broadcast(data)
        
        # 전송 확인 응답
        await websocket.send_text(json.dumps({
            "type": "broadcast_result",
            "success": True,
            "client_count": len(manager.active_connections)
        }))
    except Exception as e:
        logger.error(f"알림 브로드캐스트 중 오류: {str(e)}")
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            # 이미 닫힌 연결에 대한 오류 무시
            logger.debug("WebSocket 연결이 이미 닫혀 있습니다.")
            pass

# HTTP 알림 엔드포인트 (WebSocket 백업)
@router.post("/notifications")
async def send_notification(notification: dict):
    try:
        # 알림 데이터 검증
        if "type" not in notification:
            notification["type"] = "notification"
            
        # WebSocket을 통해 브로드캐스트
        message = json.dumps(notification)
        await manager.broadcast(message)
        
        return {"success": True, "client_count": len(manager.active_connections)}
    except Exception as e:
        logger.error(f"HTTP 알림 전송 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
 
async def run_camera_process(db: Session, pet_id: int = None):
    """카메라 프로세스를 실행하는 비동기 함수"""
    try:
        logger.info("카메라 프로세스 시작")
        camera_state.is_running = True
        await process_video(db=db, pet_id=pet_id)
    except Exception as e:
        logger.error(f"카메라 프로세스 오류: {str(e)}")
        raise
    finally:
        camera_state.is_running = False
        logger.info("카메라 프로세스 종료")
 
@router.post("/set-camera-mode")
async def set_mode(use_camera: bool, pet_id: int = None, db: Session = Depends(get_db)):
    """
    카메라 모드 설정을 변경하는 API
   
    - **use_camera**: True는 실시간 카메라 모드, False는 영상 업로드 모드
    - **pet_id**: 반려동물 ID (지정된 경우)
    """
    try:
        # 카메라 모드 설정
        set_camera_mode(use_camera)
       
        if use_camera:
            if not camera_state.is_running:
                # 이전 태스크가 있다면 취소
                if camera_state.task and not camera_state.task.done():
                    camera_state.task.cancel()
                    try:
                        await camera_state.task
                    except asyncio.CancelledError:
                        pass
               
                # 새로운 태스크 시작
                camera_state.task = asyncio.create_task(run_camera_process(db, pet_id))
                logger.info(f"카메라 모드 활성화됨 (pet_id: {pet_id})")
                return {"message": "카메라 모드가 활성화되었습니다.", "use_camera": True, "pet_id": pet_id}
            else:
                return {"message": "카메라가 이미 실행 중입니다.", "use_camera": True}
        else:
            # 카메라 모드 비활성화
            if camera_state.task and not camera_state.task.done():
                camera_state.task.cancel()
                try:
                    await camera_state.task
                except asyncio.CancelledError:
                    pass
                camera_state.task = None
            logger.info("카메라 모드 비활성화됨")
            return {"message": "카메라 모드가 비활성화되었습니다.", "use_camera": False}
           
    except Exception as e:
        logger.error(f"카메라 모드 설정 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
 
@router.post("/analyze/{pet_id}")
async def analyze_video(
    pet_id: int,
    video: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    업로드된 영상을 분석하는 API
   
    - **pet_id**: 반려동물 ID
    - **video**: 분석할 영상 파일
    """
    try:
        # 반려동물 존재 확인
        pet = db.query(PetProfile).filter(PetProfile.id == pet_id).first()
        if not pet:
            raise HTTPException(status_code=404, detail="반려동물을 찾을 수 없습니다")
           
        # 임시 파일로 저장
        temp_dir = Path("temp_videos")
        temp_dir.mkdir(parents=True, exist_ok=True)
       
        temp_path = temp_dir / f"temp_{video.filename}"
        try:
            with open(temp_path, "wb") as buffer:
                content = await video.read()
                buffer.write(content)
           
            # 비디오 분석 실행
            result = await process_video(video_path=str(temp_path), db=db, pet_id=pet_id)
            return JSONResponse(content=result)
           
        finally:
            # 임시 파일 정리
            if os.path.exists(temp_path):
                os.remove(temp_path)
               
    except Exception as e:
        logger.error(f"비디오 분석 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))