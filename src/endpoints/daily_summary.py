from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session
from datetime import datetime

from db.session import get_db
from db.models.event import DailySummary
from db.models.pet import PetProfile

router = APIRouter()

@router.get("/daily-summary-view/{pet_id}/{date}")
async def get_daily_summary_view(pet_id: int, date: str, db: Session = Depends(get_db)):
    """
    특정 날짜의 반려동물 행동 요약을 조회만 합니다 (요약 생성 없음).
    기존에 저장된 요약 데이터가 없으면 404를 반환합니다.
    """
    try:
        # 반려동물 존재 확인
        pet = db.query(PetProfile).filter(PetProfile.id == pet_id).first()
        if not pet:
            raise HTTPException(status_code=404, detail="반려동물을 찾을 수 없습니다")
 
        # 날짜 변환
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        
        # DB에서 기존 요약 조회
        existing_summary = db.query(DailySummary).filter(
            and_(
                DailySummary.pet_id == pet_id,
                DailySummary.date == target_date
            )
        ).first()
       
        # 기존 요약이 없으면 404 반환
        if not existing_summary:
            raise HTTPException(status_code=404, detail="해당 날짜의 요약 데이터가 없습니다")
       
        # 기존 요약 데이터 반환
        return {
            "pet_id": pet_id,
            "date": date,
            "normal_summary": existing_summary.normal_summary,
            "abnormal_summary": existing_summary.abnormal_summary
        }
       
    except HTTPException:
        # HTTP 예외는 그대로 전달
        raise
    except Exception as e:
        print(f"⚠️ 일일 요약 조회 중 오류 발생: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e)) 