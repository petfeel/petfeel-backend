"""
Raspberry Pi 5 전용 스트리밍 + 녹화 모듈
────────────────────────────────────────
  • /stream               → MJPEG 실시간 스트림
  • /record/start/{id}    → 특정 반려동물 녹화 시작
  • /record/stop          → 녹화 종료 (파일만 저장, DB 저장은 rename 시에)
────────────────────────────────────────
- 파일은 <프로젝트 루트>/results/videos/record_{pet_id?}_{timestamp}.mp4 로 저장
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
import cv2, time, threading, queue
from sqlalchemy.orm import Session
from db.models.pet_recorded import PetRecorded

# ───────────────────────────────────────
# 프로젝트 루트 기준으로 results/videos 폴더로 통일
# (main.py 의 UPLOAD_DIR 과 같은 경로)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RECORD_DIR   = PROJECT_ROOT / "results" / "videos"
RECORD_DIR.mkdir(parents=True, exist_ok=True)

def _log(msg: str):
    print(f"[stream] {msg}")

# 1. 카메라 초기화
try:
    cap = cv2.VideoCapture(2)               # 필요 시 인덱스 변경
    if not cap.isOpened():
        raise RuntimeError("카메라를 열 수 없습니다")

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)

    FRAME_SIZE = (
        int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
    )
    _log(f"카메라 OK {FRAME_SIZE[0]}x{FRAME_SIZE[1]} @ {int(cap.get(cv2.CAP_PROP_FPS))}fps")
except Exception as e:
    _log(f"카메라 초기화 실패: {e}")
    raise

# 2. 전역 상태
_recording      = False
_writer         = None
_current_path   = None   # Path 객체
_current_pet_id = None
frame_q         = queue.Queue(maxsize=100)
stop_evt        = threading.Event()

# 3. 프레임 캡처 스레드
def _capture_loop():
    while not stop_evt.is_set():
        ok, frame = cap.read()
        if ok:
            try:
                frame_q.put_nowait(frame)
            except queue.Full:
                frame_q.get_nowait()
                frame_q.put_nowait(frame)
        else:
            time.sleep(0.02)

threading.Thread(target=_capture_loop, daemon=True).start()

# 4. VideoWriter 열기
def _open_writer(pet_id: int | None = None):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"record_{pet_id}_{ts}.mp4" if pet_id else f"record_{ts}.mp4"
    path = RECORD_DIR / name
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(path), fourcc, 30.0, FRAME_SIZE)
    if not vw.isOpened():
        raise RuntimeError("VideoWriter 열기 실패")
    return vw, path

# 5. 녹화 스레드
def _record_loop():
    global _writer, _recording
    while _recording:
        try:
            frame = frame_q.get(timeout=1)
            _writer.write(frame)
        except queue.Empty:
            pass
    _writer.release()
    _writer = None

# 6. DB 저장 유틸
def _save_to_db(db: Session, path: Path, pet_id: int):
    try:
        time.sleep(0.3)  # 파일 flush 대기
        with open(path, "rb") as f:
            data = f.read()
        if not data:
            raise ValueError("영상 파일이 비어 있음")

        db_rec = PetRecorded(
            pet_id=pet_id,
            recorded_video=data,
            video_name=path.name,
        )
        db.add(db_rec)
        db.commit()
        _log(f"DB 저장 완료 ({pet_id}, {path.name}, {len(data):,} bytes)")
    except Exception as e:
        _log(f"DB 저장 실패: {e}")

# 7-1. 녹화 시작
def start_recording(pet_id: int | None = None):
    global _recording, _writer, _current_path, _current_pet_id
    if _recording:
        return
    _writer, _current_path = _open_writer(pet_id)
    _current_pet_id = pet_id
    _recording = True
    threading.Thread(target=_record_loop, daemon=True).start()
    _log(f"[REC ▶] {_current_path}")

# 7-2. 녹화 중지 → (filename, abs_path) 반환, DB 저장은 rename 시에 수행
def stop_recording(db: Session | None = None) -> tuple[str | None, str | None]:
    global _recording, _current_path, _current_pet_id
    if not _recording:
        return None, None

    _recording = False
    time.sleep(0.5)  # Writer 종료 대기

    # — DB 저장은 rename 엔드포인트에서만 수행하도록 변경 —
    # if db and _current_path and _current_pet_id:
    #     _save_to_db(db, _current_path, _current_pet_id)

    _log(f"[REC ■] 저장 완료 → {_current_path}")
    fn, ap = (_current_path.name, str(_current_path)) if _current_path else (None, None)
    _current_path, _current_pet_id = None, None
    return fn, ap

def is_recording() -> bool:
    return _recording

# 8. MJPEG 제너레이터
def stream_generator():
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.01)
            continue
        _, buf = cv2.imencode(".jpg", frame)
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"

# 9. 정리
def cleanup():
    stop_evt.set()
    if _recording:
        stop_recording()
    cap.release()

if __name__ == "__main__":
    try:
        start_recording(pet_id=1)
        time.sleep(10)
        stop_recording()
    finally:
        cleanup()
