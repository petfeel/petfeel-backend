from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Text, LargeBinary, UniqueConstraint
from sqlalchemy.sql import func
from db.base import Base

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    pet_id = Column(Integer, ForeignKey("pet_profile.id", ondelete="CASCADE"))
    stage = Column(Integer, default=0)  # 0: 정상, 1~3: 이상 행동 단계
    summary = Column(Text)
    video_name = Column(String(512))
    video_data = Column(LargeBinary)  # 영상 데이터 저장용
    created_at = Column(DateTime, server_default=func.now())

class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id = Column(Integer, primary_key=True, index=True)
    pet_id = Column(Integer, ForeignKey("pet_profile.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    normal_summary = Column(Text)
    abnormal_summary = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # 복합 유니크 제약 조건 추가 (같은 날짜에 같은 pet_id의 요약이 중복되지 않도록)
    __table_args__ = (UniqueConstraint('pet_id', 'date', name='uix_pet_date'),) 