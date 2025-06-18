# detector/detection.py
import os
import time
import cv2
import requests
import numpy as np
from datetime import datetime
from pathlib import Path
from ultralytics import YOLO
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
import google.generativeai as genai
import re
import warnings
import json
import glob
import base64
import io
from sqlalchemy.orm import Session
from db.models.pet import PetProfile
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import aiohttp
import asyncio
import websockets  # 웹소켓 기능 추가
 
# 경고 메시지 필터링
warnings.filterwarnings('ignore', category=UserWarning)
 
# 환경변수에서 로드
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")  # 실제 서버 주소로 변경 필요
API_EVENT_EP = f"{SERVER_URL}/events"  # /event -> /events로 수정
WS_SERVER_URL = SERVER_URL.replace("http", "ws")  # WebSocket 서버 URL
 
# API 키 직접 설정
GOOGLE_API_KEY = "AIzaSyAodNAwhpYmQkLWPA3dv-giw0WppjLhjMY"
genai.configure(api_key=GOOGLE_API_KEY)
LLM = genai.GenerativeModel(model_name="models/gemini-2.5-flash-preview-05-20")
 
# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).resolve().parents[1]
 
# ===== 입력 소스 설정 =====
# 카메라를 사용하려면 USE_CAMERA = True로 변경
# 영상 파일을 사용하려면 USE_CAMERA = False로 설정하고 VIDEO_PATH 지정
USE_CAMERA = False  # True: 카메라 사용, False: 비디오 파일 사용
CAMERA_ID = 2 # 카메라 사용 시 카메라 ID
VIDEO_PATH = "videos/test_video.mp4"  # 비디오 파일 경로
 
# ===== 파라미터 설정 =====
"""
[영상 처리 관련 파라미터]
FRAME_SKIP = 5    # 몇 프레임당 1번 처리할지 설정
                  # 예: 5로 설정 시 5프레임마다 1번 처리 (30fps 기준 1초에 6번 처리)
                  # 값이 작을수록 더 자주 체크하지만 처리 부하가 증가
                  # 값이 클수록 처리는 빠르지만 놓치는 행동이 많아질 수 있음
                  # 권장 범위: 3~10
 
WINDOW_SIZE = 5    # 한 번에 분석할 프레임 묶음 크기
                   # 예: 5로 설정 시 5프레임을 하나의 묶음으로 분석
                   # FRAME_SKIP과 연계되어 실제 시간 계산됨
                   # 현재 설정: 5프레임 × 5프레임 간격 = 25프레임(약 0.8초) 단위로 분석
 
DETECTION_WINDOWS = 5    # 이상행동 감지를 위해 체크할 윈도우 수
                        # 예: 5로 설정 시 5번의 연속된 윈도우 체크
                        # 현재 설정: 5번 × 0.8초 = 약 4초 동안의 행동 패턴 체크
 
BUFFER_SECONDS = 3     # 제미니 분석 및 DB 저장을 위한 영상 길이(초)
                      # 제미니에 보낼 영상과 DB에 저장할 영상의 길이
                      # 값이 크면 더 정확한 분석이 가능하지만 처리 시간 증가
                      # 권장 범위: 3~5초
 
FPS = 30.0            # 기본 FPS 설정
                      # 대부분의 카메라/영상의 기본값이므로 수정 불필요
 
MAX_FRAMES = int(FPS * BUFFER_SECONDS)  # 버퍼에 저장할 최대 프레임 수
                                       # 자동 계산되므로 수정 불필요
                                       # 현재 설정: 30fps × 3초 = 90프레임
 
[민감도 관련 파라미터]
STD_MULTIPLIER = 0.5   # 이상행동 감지 민감도
                      # 값이 작을수록 더 민감하게 감지
                      # 값이 클수록 확실한 이상행동만 감지
                      # 권장 범위: 0.3~1.0
 
IF_CONTAM = 0.2       # IsolationForest 모델의 이상치 비율
LOF_CONTAM = 0.2      # LocalOutlierFactor 모델의 이상치 비율
                      # 두 값이 클수록 더 많은 행동을 이상행동으로 판단
                      # 권장 범위: 0.1~0.3
 
[실제 시간 계산 예시]
현재 설정 기준:
1. 프레임 처리: 5프레임마다 1번 → 1초에 6번 처리 (30fps 기준)
2. 행동 분석: 5프레임 × 5번 = 25프레임(약 0.8초) 단위로 분석
3. 이상행동 감지: 5번의 연속된 분석 = 약 4초 동안의 패턴 체크
4. 영상 저장: 감지 후 4초 분량 저장 및 분석
 
설정 변경 시 고려사항:
1. 빠른 감지가 필요하면: FRAME_SKIP과 WINDOW_SIZE를 줄임
2. 정확한 분석이 필요하면: BUFFER_SECONDS를 늘림
3. 저장 용량 절약이 필요하면: FRAME_SKIP을 늘림
"""
 
FRAME_SKIP         = 5   # 2프레임당 1프레임 처리 (성능 최적화)
WINDOW_SIZE        = 5   # 이상행동 감지 윈도우 크기
DETECTION_WINDOWS  = 5  # 연속 감지 윈도우 수
ALLOWED_NORMAL     = 1   # 허용되는 정상 윈도우 수
FPS               = 30.0  # 기본 FPS
BUFFER_SECONDS    = 10    # 버퍼 크기 (초) - 저장되는 영상의 길이
MAX_FRAMES        = int(BUFFER_SECONDS * FPS / FRAME_SKIP)  # 최대 프레임 수
STD_MULTIPLIER    = 0.5 # 이상치 감지 표준편차 배수
IF_CONTAM         = 0.2 # IsolationForest contamination
LOF_CONTAM        = 0.2  # LocalOutlierFactor contamination
LOF_NEIGHBORS     = 4   # LocalOutlierFactor neighbors
 
# 카메라 제어를 위한 전역 변수
camera_running = False
current_camera = None
 
# 카메라 모드 설정을 위한 전역 변수
USE_CAMERA = False
 
def set_camera_mode(use_camera: bool):
    """카메라 모드 설정을 변경하는 함수"""
    global USE_CAMERA, camera_running
    USE_CAMERA = use_camera
    if not use_camera:
        camera_running = False
 
def get_pet_name(db: Session, pet_id: int) -> str:
    """pet_id로 pet_name을 가져오는 함수"""
    try:
        pet = db.query(PetProfile).filter(PetProfile.id == pet_id).first()
        return pet.pet_name if pet else "테스트강아지"
    except Exception as e:
        print(f"⚠️ pet_name 조회 중 오류: {e}")
        return "테스트강아지"
 
# Gemini 프롬프트 – 0~4단계 명시
def get_prompt(db: Session = None, pet_id: int = None):
    """Gemini 프롬프트 생성"""
    if db and pet_id:
        dog_name = get_pet_name(db, pet_id)
    else:
        dog_name = "멍멍규"
       
    return f"""강아지 {dog_name}의 현재 행동을 분석해주세요.
강아지의 자세와 움직임을 기반으로 행동을 해석하고, 아래 형식으로 답변해주세요.
 
응답 형식:
1. 현재 행동 설명 (1줄)
2. 심각도: [0-3]단계
- 0단계: 정상적인 행동 (평온, 휴식, 일상적 활동)
- 1단계: 주의 관찰 필요 (과도한 움직임, 불안한 징후)
- 2단계: 경미한 문제 행동 (반복적인 이상 행동)
- 3단계: 심각한 문제 행동 또는 위험 상황 (공격성, 자해 위험, 즉각 조치 필요)
3. 심각도에 따른 대처 방법 (1-2줄)
4. 심각도가 0 단계일 경우 강아지가 무슨 행동을 하고 있는지 설명해주세요.
* 3단계 이상일 경우 응답을 **굵은 글씨**로 표시
* 불필요한 인사말이나 예의적 표현은 생략
* 제공된 정보만으로는 파악이 어려워도 최대한 파악해서 행동 분석해서 답변해주세요.
* 반드시 단계를 숫자로 명시해주세요 (예: '2단계' 또는 '단계: 2')"""
 
# 모델 로드
MODEL_PATH = PROJECT_ROOT / "dog_pose_model.pt"
print(f"모델 파일 경로: {MODEL_PATH}")
yolo      = YOLO(str(MODEL_PATH))
if_model  = IsolationForest(contamination=IF_CONTAM, random_state=42)
lof_model = LocalOutlierFactor(n_neighbors=LOF_NEIGHBORS, contamination=LOF_CONTAM, novelty=True)
 
def z_norm(a):
    return (a - a.mean()) / (a.std() or 1.0)
 
# WebSocket을 통해 알림 전송
async def send_notification_ws(event_data, pet_id):
    """
    WebSocket을 통해 알림을 전송하는 함수
    
    Args:
        event_data: 이벤트 데이터 (DB에 저장된 결과)
        pet_id: 반려동물 ID
    """
    try:
        # 알림 데이터 준비
        notification = {
            "type": "notification",
            "event_id": event_data.get("id", 0),
            "pet_id": pet_id,
            "stage": event_data.get("stage", "0"),
            "message": "반려동물의 이상행동이 감지되었습니다.",
            "behavior_report": event_data.get("summary", ""),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        
        # WebSocket URL 준비
        ws_endpoint = f"{WS_SERVER_URL}/notifications/broadcast"
        
        print(f"\n📣 WebSocket 알림 전송 시도:")
        print(f"   - 엔드포인트: {ws_endpoint}")
        
        # WebSocket 연결 및 메시지 전송
        try:
            # 타임아웃 설정 - 연결 및 송신에 최대 3초만 허용
            async with websockets.connect(ws_endpoint, close_timeout=3) as websocket:
                await websocket.send(json.dumps(notification))
                print("✅ WebSocket 알림 전송 완료!")
                # 응답을 기다리지 않고 바로 리턴 (원래 코드는 응답을 기다림)
        except websockets.exceptions.WebSocketException as ws_err:
            print(f"⚠️ WebSocket 연결 실패, HTTP 폴백 시도: {str(ws_err)}")
            
            # WebSocket 실패 시 HTTP로 폴백
            try:
                async with aiohttp.ClientSession() as session:
                    http_endpoint = f"{SERVER_URL}/notifications"
                    async with session.post(http_endpoint, json=notification, timeout=3) as response:
                        if response.status == 200:
                            print("✅ HTTP 폴백 알림 전송 완료!")
                        else:
                            print(f"⚠️ HTTP 폴백 알림 전송 실패: {await response.text()}")
            except asyncio.TimeoutError:
                print("⚠️ HTTP 요청 타임아웃")
            except Exception as http_err:
                print(f"⚠️ HTTP 폴백 알림 전송 실패: {str(http_err)}")
                
    except Exception as e:
        print(f"⚠️ 알림 전송 중 오류: {str(e)}")
        # 알림 전송 실패가 전체 프로세스를 중단시키지 않도록 예외를 여기서 처리
 
async def post_event(stage, summary, frames, fps, db: Session = None, pet_id: int = None):
    """
    서버 /event 로 이벤트 데이터 전송 및 저장
    """
    try:
        # pet_id가 없는 경우 오류 출력
        if pet_id is None:
            print("⚠️ 경고: pet_id가 지정되지 않았습니다. 기본값 1을 사용합니다.")
            pet_id = 1
            
        # 기본 데이터 준비
        data = {
            'pet_id': pet_id,
            'stage': str(stage),
            'summary': summary,
            'created_at': datetime.now().isoformat()
        }
        
        print(f"\n📤 서버로 전송 시도 중... (URL: {API_EVENT_EP})")
        print(f"- pet_id: {pet_id}")
       
        # 영상이 있는 경우
        if frames is not None and len(frames) > 0:
            try:
                # 임시 디렉토리 생성
                temp_dir = Path("temp_videos")
                temp_dir.mkdir(exist_ok=True)
               
                current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                temp_path = temp_dir / f"temp_{current_time}.mp4"
               
                print("\n📹 영상 저장 중...")
                print(f"- 프레임 수: {len(frames)}")
                print(f"- 영상 길이: {len(frames)/fps*FRAME_SKIP:.2f}초")
               
                # 영상 저장 - 높은 품질 설정
                h, w = frames[0].shape[:2]
                
                # H.264 코덱 사용 (더 나은 호환성)
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # H.264 코덱
                
                # 비트레이트와 해상도 향상
                out = cv2.VideoWriter(
                    str(temp_path), 
                    fourcc, 
                    fps/FRAME_SKIP,  # 프레임 레이트 
                    (w, h),  # 해상도
                    True   # 컬러 영상
                )
                
                # 프레임이 적을 경우 반복하여 최소 길이 보장 (최소 2초)
                min_frames = int(2 * fps / FRAME_SKIP)
                
                if len(frames) < min_frames:
                    print(f"⚠️ 프레임이 너무 적습니다. 반복하여 최소 {min_frames}개 확보...")
                    # 프레임 반복하여 최소 길이 보장
                    repeated_frames = []
                    while len(repeated_frames) < min_frames:
                        repeated_frames.extend(frames)
                    frames = repeated_frames[:min_frames]
                    print(f"✅ 프레임 반복 완료: {len(frames)}개")
               
                # 영상 저장 (각 프레임 품질 체크)
                frames_written = 0
                for frame in frames:
                    if frame is None or frame.size == 0:
                        print(f"⚠️ 빈 프레임 건너뜀 ({frames_written}/{len(frames)})")
                        continue
                        
                    # 프레임 품질 향상 (선택 사항)
                    # frame = cv2.GaussianBlur(frame, (3, 3), 0)  # 노이즈 감소
                    
                    out.write(frame)
                    frames_written += 1
                
                # 비디오 라이터 종료 및 자원 해제
                out.release()
                
                print(f"✅ 영상 저장 완료: {frames_written}/{len(frames)} 프레임")
                
                # 파일이 제대로 생성되었는지 확인
                if os.path.exists(temp_path):
                    file_size = os.path.getsize(temp_path)
                    if file_size < 1000:  # 파일이 너무 작으면 문제 있음
                        print(f"⚠️ 저장된 파일이 너무 작습니다: {file_size}바이트")
                        # 파일 검사를 위해 읽기 시도
                        cap = cv2.VideoCapture(str(temp_path))
                        if not cap.isOpened():
                            print("❌ 생성된 영상 파일을 열 수 없습니다!")
                            return None
                        cap.release()
                else:
                    print("❌ 영상 파일이 생성되지 않았습니다!")
                    return None
               
                # 파일 크기 확인
                file_size = os.path.getsize(temp_path)
                print(f"📤 서버로 전송 중... (크기: {file_size/1024:.1f}KB)")
               
                # 파일 전송
                async with aiohttp.ClientSession() as session:
                    data = aiohttp.FormData()
                    data.add_field('pet_id', str(pet_id))
                    data.add_field('stage', str(stage))
                    data.add_field('summary', summary)
                    data.add_field('created_at', datetime.now().isoformat())
                   
                    with open(temp_path, 'rb') as f:
                        file_contents = f.read()
                        data.add_field('video_data',
                                     file_contents,
                                     filename=f"{current_time}.mp4",
                                     content_type='video/mp4')
                                     
                        # 영상 미리보기를 로컬에 저장 (디버깅용)
                        preview_dir = Path("video_previews")
                        preview_dir.mkdir(exist_ok=True)
                        preview_path = preview_dir / f"{current_time}.mp4"
                        with open(preview_path, 'wb') as preview_file:
                            preview_file.write(file_contents)
                            print(f"💾 미리보기 영상 저장됨: {preview_path}")
                       
                        # POST 요청 전송
                        async with session.post(API_EVENT_EP, data=data, timeout=30) as response:
                            if response.status == 200:
                                result = await response.json()
                                print("✅ DB 저장 완료!")
                                # WebSocket 알림 전송
                                await send_notification_ws(result, pet_id)
                                return result
                            else:
                                response_text = await response.text()
                                print(f"⚠️ DB 저장 실패: 상태 코드 {response.status}")
                                print(f"서버 응답: {response_text}")
                                return None
               
            except Exception as e:
                print(f"⚠️ 영상 처리 중 오류: {str(e)}")
                import traceback
                print(traceback.format_exc())
                return None
            finally:
                # 임시 파일 정리
                if os.path.exists(temp_path):
                    os.remove(temp_path)
               
        else:
            # 영상 없는 경우 간단히 처리
            async with aiohttp.ClientSession() as session:
                data['created_at'] = datetime.now().isoformat()
                async with session.post(API_EVENT_EP, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        print("✅ DB 저장 완료!")
                        # WebSocket 알림 전송
                        await send_notification_ws(result, pet_id)
                        return result
                    print(f"⚠️ DB 저장 실패: {await response.text()}")
                    return None
               
    except Exception as e:
        print(f"⚠️ 전체 처리 실패: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return None
 
async def analyze_with_gemini(frames_count, db: Session = None, pet_id: int = None):
    """
    Gemini AI를 사용한 행동 분석
   
    매개변수:
    - frames_count: 분석할 프레임 수
    - db: 데이터베이스 세션
    - pet_id: 반려동물 ID
   
    반환값:
    - stage: 행동 단계 (0-4)
    - text: 분석 결과 텍스트
    """
    try:
        print("\n🤖 Gemini 분석 시작...")
        print(f"- pet_id: {pet_id}")
        
        # 분석할 영상 찾기
        gemini_videos = sorted(glob.glob('gemini_videos/*.mp4'))
        if not gemini_videos:
            print("⚠️ 분석할 영상 없음")
            return 0, "분석 실패: 영상 없음"
           
        latest_video = gemini_videos[-1]
        print(f"📁 분석할 영상: {latest_video}")
       
        if not os.path.exists(latest_video):
            print(f"⚠️ 영상 파일이 존재하지 않음: {latest_video}")
            return 0, "분석 실패: 영상 파일 없음"
           
        file_size = os.path.getsize(latest_video)
        print(f"📊 영상 파일 크기: {file_size/1024:.1f}KB")
       
        if file_size == 0:
            print("⚠️ 영상 파일이 비어있음")
            return 0, "분석 실패: 빈 영상 파일"
       
        print("🔄 영상 파일 업로드 중...")
        video_file = await asyncio.to_thread(genai.upload_file, path=latest_video)
        print(f"✅ 업로드 완료: {video_file.name}")
       
        print("⏳ 영상 처리 대기 중...")
        retry_count = 0
        while video_file.state.name == "PROCESSING" and retry_count < 10:
            await asyncio.sleep(0.5)
            video_file = await asyncio.to_thread(genai.get_file, video_file.name)
            retry_count += 1
            print(f"   - 상태: {video_file.state.name} (시도: {retry_count})")
           
        if video_file.state.name == "FAILED" or retry_count >= 10:
            print(f"⚠️ 영상 처리 실패 (상태: {video_file.state.name})")
            return 0, "분석 실패: 영상 처리 오류"
 
        print("\n📝 프롬프트 전송...")
       
        resp = await asyncio.to_thread(LLM.generate_content, [get_prompt(db, pet_id), video_file])
       
        if not resp:
            print("⚠️ 응답 없음")
            return 0, "분석 실패: 응답 없음"
           
        text = resp.text.strip()
        print("\n✅ 분석 완료:")
        print(text)
       
        stage = 0
        if "단계" in text:
            stage_match = re.search(r'(\d+)단계|단계[:\s]*(\d+)|심각도[:\s]*(\d+)', text)
            if stage_match:
                stage = int(stage_match.group(1) or stage_match.group(2) or stage_match.group(3))
       
        if stage < 0 or stage > 4:
            print(f"⚠️ 잘못된 단계 값 ({stage})")
            stage = 0
           
        print(f"\n📊 분석 결과:")
        print(f"- 단계: {stage}")
        print(f"- 텍스트 길이: {len(text)}자")
       
        return stage, text
       
    except Exception as e:
        print(f"\n❌ 분석 오류:")
        print(f"- 유형: {type(e).__name__}")
        print(f"- 내용: {str(e)}")
        import traceback
        print(f"- 상세:\n{traceback.format_exc()}")
        return 0, f"분석 실패: {str(e)}"
 
async def process_video(video_path: str = None, use_camera: bool = None, db: Session = None, pet_id: int = None) -> dict:
    """
    비디오 처리 메인 함수
    카메라 또는 비디오 파일에서 프레임을 읽어 처리
 
    Args:
        video_path: 비디오 파일 경로 (use_camera=False일 때 사용)
        use_camera: True면 카메라 사용, False면 비디오 파일 사용 (None이면 전역 USE_CAMERA 사용)
        db: 데이터베이스 세션
        pet_id: 반려동물 ID
    """
    global camera_running, USE_CAMERA
    
    print("\n🔄 process_video 함수 호출:")
    print(f"- video_path: {video_path}")
    print(f"- use_camera: {use_camera}")
    print(f"- pet_id: {pet_id}")
   
    # 파일 경로가 있으면 무조건 파일 모드로 설정
    if video_path:
        USE_CAMERA = False
    # 파일 경로가 없고 use_camera가 지정된 경우 해당 값 사용
    elif use_camera is not None:
        USE_CAMERA = use_camera
   
    print("🎥 영상 소스 초기화 중...")
    print(f"- 모드: {'카메라' if USE_CAMERA else '비디오 파일'}")
   
    if USE_CAMERA:
        # 카메라 모드
        camera_running = True
        cap = cv2.VideoCapture(CAMERA_ID)
        if not cap.isOpened():
            print(f"카메라 {CAMERA_ID} 열기 실패, 카메라 0 시도...")
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                print("❌ 카메라를 열 수 없습니다!")
                camera_running = False
                return {"error": "카메라를 열 수 없습니다"}
        print(f"✅ 카메라 연결 성공")
        try:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        except Exception as e:
            print(f"⚠️ 해상도 설정 실패 (무시하고 계속): {str(e)}")
    else:
        # 비디오 파일 모드
        if not video_path:
            raise ValueError("비디오 파일 경로가 필요합니다")
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"❌ 비디오 파일을 열 수 없습니다: {video_path}")
            return {"error": "비디오 파일을 열 수 없습니다"}
        print(f"✅ 비디오 파일 로드됨: {video_path}")
 
    # 비디오 정보 출력
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or FPS
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
 
    print(f"- 해상도: {width}x{height}")
    print(f"- FPS: {fps:.1f}")
    print(f"- 프레임 스킵: {FRAME_SKIP} (처리 FPS: {fps/FRAME_SKIP:.1f})")
    print(f"- 버퍼 크기: {BUFFER_SECONDS}초 ({MAX_FRAMES} 프레임)")
    if not USE_CAMERA:
        print(f"- 총 프레임 수: {total_frames}")
        print(f"- 예상 재생 시간: {total_frames/fps:.1f}초")
 
    # 윈도우 생성
    window_name = "Dog Pose Detection"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)
    cv2.moveWindow(window_name, 0, 0)
 
    # 초기화
    features = []
    frames_vis = []
    frames_original = []
    frame_idxs = []
    frame_times = []
    frame_no = 0
    last_event_time = 0
    is_recording = False
    current_stage = 0
    current_summary = ""
    recording_start_time = 0
    abnormal_windows = []
    continuous_detection = False
 
    # Gemini 비디오 저장 폴더 생성
    os.makedirs('gemini_videos', exist_ok=True)
 
    try:
        while camera_running if USE_CAMERA else True:
            ret, frame = cap.read()
            if not ret:
                if USE_CAMERA:
                    print("⚠️ 카메라 프레임을 읽을 수 없습니다.")
                    continue
                else:
                    print("✅ 영상 처리 완료!")
                    break
               
            if frame is None or frame.size == 0:
                print("⚠️ 빈 프레임을 받았습니다.")
                continue
               
            frame_no += 1
            current_time = time.time()
           
            # 진행률 표시 (비디오 파일 모드일 때만)
            if not USE_CAMERA and frame_no % 30 == 0:
                progress = (frame_no / total_frames) * 100
                print(f"\r진행률: {progress:.1f}%", end="")
 
            # YOLO로 포즈 예측 및 시각화 (매 프레임 처리)
            result = yolo.predict(frame, conf=0.7, verbose=False)[0]
            vis = result.plot()
 
            # 화면에 상태 표시
            fps_text = f"FPS: {fps/FRAME_SKIP:.1f}"
            cv2.putText(vis, fps_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
           
            status = "정상" if not is_recording else "이상행동 감지 중"
            cv2.putText(vis, status, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1,
                       (0, 255, 0) if not is_recording else (0, 0, 255), 2)
 
            # 화면 표시
            cv2.imshow(window_name, vis)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("\n사용자가 종료를 요청했습니다.")
                break
            elif key == ord('f'):
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN) == cv2.WINDOW_FULLSCREEN:
                    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                else:
                    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
 
            # 이상행동 감지는 FRAME_SKIP 간격으로
            if frame_no % FRAME_SKIP != 0:
                continue
 
            # 이상행동 감지 로직
            if result.keypoints is not None and len(result.keypoints.data) > 0:
                kpts = result.keypoints.data[0]
                if kpts.shape[0] == 24:
                    # 특징점 추출
                    pelvis = kpts[14][:2]
                    l_sh, r_sh = kpts[11][:2], kpts[12][:2]
                    scale = np.linalg.norm(l_sh - r_sh) or 1.0
 
                    feat = []
                    for x, y, v in kpts:
                        if v < 0.5:
                            feat += [0.0, 0.0]
                        else:
                            feat += [(x - pelvis[0]) / scale,
                                    (y - pelvis[1]) / scale]
                    features.append(feat)
                    frames_vis.append(vis.copy())
                    frames_original.append(frame.copy())
                    frame_idxs.append(frame_no)
                    frame_times.append(current_time)
 
                    # 이상행동 감지
                    if len(features) >= WINDOW_SIZE:
                        X = np.array(features[-WINDOW_SIZE:])
                        if_model.fit(X)
                        lof_model.fit(X)
                        if_scores = if_model.decision_function(X)
                        lof_scores = lof_model.decision_function(X)
                        combined = (z_norm(if_scores) + z_norm(lof_scores)) / 2.0
                       
                        threshold = combined.mean() - STD_MULTIPLIER * combined.std()
                        is_abnormal = combined[-1] < threshold
 
                        abnormal_windows.append(is_abnormal)
                        if len(abnormal_windows) > DETECTION_WINDOWS:
                            abnormal_windows.pop(0)
 
                        if len(abnormal_windows) == DETECTION_WINDOWS:
                            abnormal_count = sum(abnormal_windows)
                            if abnormal_count >= (DETECTION_WINDOWS - ALLOWED_NORMAL) and not continuous_detection:
                                continuous_detection = True
                                is_recording = True
                                recording_start_time = time.time()
                                frames_vis = []
                                frames_original = []
                                print("\n🔍 연속적인 이상행동 감지 - 영상 수집 시작")
 
                        if is_recording:
                            current_duration = current_time - recording_start_time
                            if current_duration >= BUFFER_SECONDS:
                                print(f"\n📹 영상 수집 완료:")
                                print(f"   - 수집된 프레임 수: {len(frames_original)}")
                                print(f"   - 목표 프레임 수: {MAX_FRAMES}")
                                print(f"   - 실제 수집 시간: {current_duration:.2f}초")
                                print(f"   - 목표 수집 시간: {BUFFER_SECONDS}초")
 
                                try:
                                    # Gemini 분석용 임시 영상 생성
                                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    temp_video_path = os.path.join("gemini_videos", f"temp_{timestamp_str}.mp4")
                                    print(f"\n💾 분석용 영상 저장 중: {temp_video_path}")
                                   
                                    target_fps = fps / FRAME_SKIP
                                    h, w = frames_original[0].shape[:2]
                                   
                                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                                    out = cv2.VideoWriter(temp_video_path, fourcc, target_fps, (w, h))
                                   
                                    frames_written = 0
                                    for frame in frames_original:
                                        if frame is None or frame.size == 0:
                                            print(f"⚠️ 빈 프레임 건너뜀 ({frames_written}/{len(frames_original)})")
                                            continue
                                        out.write(frame)
                                        frames_written += 1
                                   
                                    out.release()
                                    
                                    # 파일 검증
                                    if os.path.exists(temp_video_path):
                                        file_size = os.path.getsize(temp_video_path)
                                        print(f"📊 저장된 분석용 영상 크기: {file_size/1024:.1f}KB")
                                        
                                        if file_size < 1000:  # 파일이 너무 작으면 문제 있음
                                            print(f"⚠️ 저장된 분석용 영상이 너무 작습니다!")
                                    else:
                                        print(f"❌ 분석용 영상 저장 실패!")
                                    
                                    time.sleep(0.5)

                                    # 제미니 분석 실행
                                    analysis_start_time = time.time()
                                    current_stage, current_summary = await analyze_with_gemini(len(frames_original), db, pet_id)
                                    print(f"⏱️ 제미니 분석 시간: {time.time() - analysis_start_time:.2f}초")
 
                                    # 0단계(정상)와 1~3단계(이상행동) 구분 처리
                                    if current_stage > 0:
                                        # 1~3단계: 영상과 함께 저장
                                        print(f"📝 이상행동 감지 (단계: {current_stage}) - 영상과 함께 저장")
                                        result = await post_event(current_stage,
                                                                current_summary,
                                                                frames_original,  # 영상 포함
                                                                fps,
                                                                db=db,
                                                                pet_id=pet_id)
                                        if result:
                                            print(f"✅ DB 저장 완료!")
                                            print(f"   - 행동 단계: {current_stage}")
                                            # WebSocket 알림 전송
                                            await send_notification_ws(result, pet_id)
                                        else:
                                            print("⚠️ DB 저장 실패")
                                    else:
                                        # 0단계: 영상 없이 설명만 저장
                                        print(f"📝 정상 행동 감지 (단계: {current_stage}) - 설명만 저장")
                                        result = await post_event(current_stage,
                                                                current_summary,
                                                                None,  # 영상 제외
                                                                fps,
                                                                db=db,
                                                                pet_id=pet_id)
                                        if result:
                                            print(f"✅ DB 저장 완료! (영상 없음)")
                                            print(f"   - 행동 단계: {current_stage}")
                                            # WebSocket 알림 전송
                                            await send_notification_ws(result, pet_id)
                                        else:
                                            print("⚠️ DB 저장 실패")
 
                                except Exception as e:
                                    print(f"❌ 영상 처리 중 오류 발생:")
                                    print(f"   - 내용: {str(e)}")
                                    return {"error": "영상 처리 중 오류가 발생했습니다"}
                                finally:
                                    if os.path.exists(temp_video_path):
                                        os.remove(temp_video_path)
 
                                # 상태 초기화
                                frames_vis = []
                                frames_original = []
                                frame_times = []
                                is_recording = False
                                continuous_detection = False
                                abnormal_windows = []
                                current_stage = 0
                                current_summary = ""
 
                    # 버퍼 관리
                    if len(features) > WINDOW_SIZE:
                        features.pop(0)
                    if len(frames_vis) > MAX_FRAMES:
                        frames_vis.pop(0)
                    if len(frames_original) > MAX_FRAMES:
                        frames_original.pop(0)
                    if len(frame_idxs) > MAX_FRAMES:
                        frame_idxs.pop(0)
                    if len(frame_times) > MAX_FRAMES:
                        frame_times.pop(0)
 
    finally:
        camera_running = False
        cap.release()
        cv2.destroyAllWindows()
        return {"message": "비디오 분석이 완료되었습니다"}
 
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
        if sys.argv[2] if len(sys.argv) > 2 else None == "camera":
            asyncio.run(process_video(use_camera=True))
        else:
            asyncio.run(process_video(video_path=video_path))
    else:
        print("사용법: python detection.py <비디오_파일_경로 | camera>")
 
"""
[반려견 행동 감지 시스템 - 메인 감지 모듈]
 
시스템 구성 및 데이터 흐름:
1. 입력 소스 처리
   - 카메라 또는 비디오 파일에서 프레임 읽기
   - FRAME_SKIP을 통한 성능 최적화
 
2. 행동 감지 파이프라인
   - YOLO 모델: 강아지 포즈 감지
   - IsolationForest/LOF: 이상행동 패턴 감지
   - 연속된 이상행동 체크 (DETECTION_WINDOWS)
 
3. 영상 처리 및 저장
   - 버퍼 관리: MAX_FRAMES 기준
   - 임시 저장: gemini_videos/ 디렉토리
   - 최종 저장: temp_videos/ 디렉토리
 
4. Gemini AI 분석
   - 행동 패턴 분석
   - 단계 분류 (0-3)
   - 상세 행동 설명 생성
 
5. 서버 통신
   - /events 엔드포인트로 데이터 전송
   - 영상 데이터 multipart/form-data 형식 사용
   - 분석 결과 DB 저장
 
주요 데이터 포인트:
- features: 강아지 포즈의 특징점 데이터
- frames_vis: 시각화된 프레임 버퍼
- frames_original: 원본 프레임 버퍼
- abnormal_windows: 이상행동 감지 윈도우
 
에러 처리:
- 파일 저장/삭제 실패
- 서버 통신 오류
- Gemini API 오류
- 영상 처리 오류
 
성능 최적화:
- FRAME_SKIP으로 처리량 조절
- 버퍼 크기 관리
- 이전 분석 영상 자동 정리
"""
 