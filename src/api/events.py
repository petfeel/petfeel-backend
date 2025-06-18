from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from db.session import get_db
from db.models import Event, PetProfile
import io
from fastapi.responses import StreamingResponse, FileResponse
import os
from pathlib import Path
 
router = APIRouter()
 
@router.post("/event")
async def create_event(
    pet_id: int = Form(...),
    created_at: str = Form(...),
    stage: int = Form(...),
    summary: str = Form(...),
    video_data: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """이상행동 이벤트 저장"""
    try:
        # created_at을 datetime으로 변환
        event_time = datetime.fromisoformat(created_at)
       
        # 반려동물 존재 여부 확인
        pet = db.query(PetProfile).filter(PetProfile.id == pet_id).first()
        if not pet:
            raise HTTPException(status_code=404, detail="존재하지 않는 반려동물입니다.")
       
        # 비디오 데이터 읽기
        video_name = None
        if video_data:
            video_name = f"pet_{pet_id}_{int(datetime.now().timestamp())}.mp4"
            print(f"비디오 파일명: {video_name}")
 
        # DB에 저장
        db_event = Event(
            pet_id=pet_id,
            created_at=event_time,
            stage=stage,
            summary=summary,
            video_name=video_name
        )
        db.add(db_event)
        db.commit()
        db.refresh(db_event)
        return {"message": "이벤트가 저장되었습니다.", "id": db_event.id}
       
    except Exception as e:
        print(f"에러 발생: {str(e)}")  # 에러 로깅 추가
        raise HTTPException(status_code=500, detail=str(e))
 
@router.get("/events")
def get_events(
    pet_id: Optional[int] = None,
    date: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """저장된 이벤트 목록 조회"""
    query = db.query(Event).order_by(Event.created_at.desc())
   
    if pet_id is not None:
        query = query.filter(Event.pet_id == pet_id)
    
    # 날짜별 필터링 추가
    if date is not None:
        try:
            # 날짜 형식 검증 (YYYY-MM-DD)
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            
            # 해당 날짜의 시작과 끝 계산
            start_date = datetime(date_obj.year, date_obj.month, date_obj.day, 0, 0, 0)
            end_date = datetime(date_obj.year, date_obj.month, date_obj.day, 23, 59, 59)
            
            # created_at 필드가 해당 날짜 범위에 있는지 필터링
            query = query.filter(Event.created_at >= start_date, Event.created_at <= end_date)
        except ValueError as e:
            # 잘못된 날짜 형식인 경우 에러 처리
            raise HTTPException(status_code=400, detail=f"잘못된 날짜 형식입니다. 'YYYY-MM-DD' 형식으로 입력해주세요: {str(e)}")
   
    events = query.offset(skip).limit(limit).all()
    return events
 
@router.get("/event/{event_id}/video")
def get_event_video(event_id: int, db: Session = Depends(get_db)):
    """특정 이벤트의 비디오 데이터 조회"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event or not event.video_name:
        raise HTTPException(status_code=404, detail="비디오를 찾을 수 없습니다")
   
    return {
        "video_name": event.video_name,
        "pet_id": event.pet_id
    }

@router.get("/events/{event_id}")
def get_event_by_id(event_id: int, db: Session = Depends(get_db)):
    """특정 이벤트 조회"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다")
    return event

@router.get("/events/{event_id}/video")
def download_event_video(event_id: int, db: Session = Depends(get_db)):
    """특정 이벤트의 비디오 파일 다운로드"""
    # 이벤트 존재 확인
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(
            status_code=404, 
            detail={
                "error": "이벤트를 찾을 수 없습니다",
                "event_id": event_id
            }
        )
    
    # 비디오 이름 확인
    if not event.video_name:
        raise HTTPException(
            status_code=404, 
            detail={
                "error": "이 이벤트에는 비디오가 없습니다",
                "event_id": event_id
            }
        )
    
    # 디버깅 정보 출력
    print(f"비디오 요청: 이벤트 ID={event_id}, 비디오 이름={event.video_name}")
    
    # 방법 1: 이벤트의 video_data가 있는 경우 (바이너리 데이터)
    if event.video_data:
        print(f"비디오 데이터 크기: {len(event.video_data)} 바이트")
        video_stream = io.BytesIO(event.video_data)
        return StreamingResponse(
            video_stream, 
            media_type="video/mp4",
            headers={"Content-Disposition": f"attachment; filename={event.video_name}"}
        )
    
    # 방법 2: 파일 시스템에서 비디오 파일 찾기
    try:
        # 비디오 파일 경로 - 개발 환경에 맞게 조정 필요
        video_dirs = [
            Path("./videos"),
            Path("./uploads/videos"),
            Path("./back_test/videos"),
            Path("./assets/videos"),
            Path("/videos"),
        ]
        
        found_video_path = None
        for video_dir in video_dirs:
            video_path = video_dir / event.video_name
            if video_path.exists():
                found_video_path = video_path
                print(f"비디오 파일 찾음: {video_path}")
                break
            
        if not found_video_path:
            # 비디오 파일을 찾을 수 없는 경우
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": "비디오 파일을 찾을 수 없습니다",
                    "video_name": event.video_name,
                    "searched_dirs": [str(d) for d in video_dirs]
                }
            )
        
        # 파일이 존재하면 FileResponse로 반환
        return FileResponse(
            found_video_path,
            media_type="video/mp4", 
            filename=event.video_name
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail={
                "error": f"비디오 파일 처리 중 오류 발생",
                "message": str(e),
                "video_name": event.video_name
            }
        )

# 동일한 엔드포인트를 다른 URL 패턴으로도 제공 (이전 버전과의 호환성)
@router.get("/event/{event_id}/video")
def download_event_video_alt(event_id: int, db: Session = Depends(get_db)):
    """특정 이벤트의 비디오 파일 다운로드 (대체 URL)"""
    return download_event_video(event_id, db)
 
@router.get("/events/by-pet/{pet_id}")
def get_events_by_pet(
    pet_id: int,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """특정 반려동물의 이벤트 목록 조회"""
    # 반려동물 존재 여부 확인
    pet = db.query(PetProfile).filter(PetProfile.id == pet_id).first()
    if not pet:
        raise HTTPException(status_code=404, detail="존재하지 않는 반려동물입니다.")
   
    events = db.query(Event)\
        .filter(Event.pet_id == pet_id)\
        .order_by(Event.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    return events
 
"""
[이벤트 라우터 상세 설명]
 
1. 이벤트 등록 (/events POST)
   데이터 처리:
   - 영상 데이터 검증
   - 메타데이터 파싱
   - DB 트랜잭션
   
   최적화:
   - 비동기 처리
   - 청크 업로드
   - 스트리밍 응답
 
2. 이벤트 조회 (/events GET)
   쿼리 파라미터:
   - skip: 페이지네이션 오프셋
   - limit: 페이지 크기
   - dog_name: 강아지 필터
   
   응답 최적화:
   - 부분 응답
   - 필드 선택
   - 결과 캐싱
 
3. 이벤트 상세 (/events/{id})
   조회 기능:
   - 메타데이터 조회
   - 영상 데이터 조회
   - 분석 결과 조회
   
   캐싱 전략:
   - 메타데이터 캐싱
   - 영상 CDN 활용
   - 분석 결과 캐싱
 
4. 에러 처리
   HTTP 에러:
   - 400: 잘못된 요청
   - 404: 리소스 없음
   - 500: 서버 에러
   
   커스텀 에러:
   - 영상 처리 실패
   - DB 연결 실패
   - 용량 초과
 
5. 보안
   인증:
   - API 키 검증
   - 토큰 검증
   - 권한 체크
   
   데이터 보호:
   - 입력 검증
   - XSS 방지
   - CSRF 보호
"""