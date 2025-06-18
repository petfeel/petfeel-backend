"""
[데이터베이스 모델 상세 설명]

1. Dog 모델 (dogs 테이블)
   관계:
   - events: 1:N (한 강아지가 여러 이벤트 가짐)
   - daily_summaries: 1:N (한 강아지가 여러 일일 요약 가짐)
   
   인덱스:
   - pet_name (PK): 강아지 이름으로 빠른 조회
   - created_at: 등록일 기준 정렬

2. Event 모델 (events 테이블)
   성능 최적화:
   - timestamp 인덱스: 시간 범위 쿼리 최적화
   - stage 인덱스: 행동 단계별 필터링 최적화
   
   저장 용량:
   - video_data (LONGBLOB): ~500MB까지 저장 가능
   - summary: 최대 1000자 제한
   
   조회 패턴:
   - 최근 이벤트 우선 조회
   - 단계별 필터링 자주 사용
   - 날짜 범위 쿼리 빈번

3. DailySummary 모델 (daily_summaries 테이블)
   집계 데이터:
   - 일별 정상 행동 요약
   - 일별 이상 행동 요약
   
   성능 고려사항:
   - date 인덱스: 날짜별 조회 최적화
   - pet_name + date 복합 인덱스
   
   데이터 보존:
   - 기본 3개월 보관
   - 자동 아카이빙 지원

4. 공통 고려사항
   - Soft Delete 지원
   - 타임스탬프 자동 갱신
   - 외래 키 제약 조건
   - CASCADE 설정
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import relationship
from .db import Base

class Dog(Base):
    """강아지 정보 모델"""
    __tablename__ = "dogs"

    pet_name = Column(String(50), primary_key=True)  # 이름을 기본키로 사용
    created_at = Column(DateTime, nullable=False)

    # 관계 설정
    events = relationship("Event", back_populates="dog")
    daily_summaries = relationship("DailySummary", back_populates="dog")

class Event(Base):
    """이상행동 감지 이벤트 모델"""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    pet_name = Column(String(50), ForeignKey("dogs.pet_name"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    stage = Column(Integer, nullable=False)  # 0: 일반행동, 1-4: 이상행동 단계
    summary = Column(String(1000), nullable=False)
    video_data = Column(LONGBLOB, nullable=True)  # 이상행동일 때만 영상 저장
    video_name = Column(String(255), nullable=True)  # 원본 영상 파일명

    # 관계 설정
    dog = relationship("Dog", back_populates="events")

class DailySummary(Base):
    """일일 행동 요약 모델"""
    __tablename__ = "daily_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    pet_name = Column(String(50), ForeignKey("dogs.pet_name"), nullable=False)
    date = Column(Date, nullable=False)
    normal_summary = Column(String(1000))  # 0단계(정상) 행동 요약
    abnormal_summary = Column(String(1000))  # 이상행동 요약
    
    # 관계 설정
    dog = relationship("Dog", back_populates="daily_summaries")

    # 사용 예시:
    # 1. 이벤트 생성
    #   event = Event(
    #       timestamp=datetime.now(),
    #       stage=2,
    #       summary="반복적인 꼬리 물기 행동 감지",
    #       video_data=video_binary,
    #       video_name="event_123.mp4"
    #   )
    #   
    # 2. 이벤트 조회
    #   # 특정 날짜의 모든 이벤트
    #   day_events = db.query(Event).filter(
    #       Event.timestamp.between(start_date, end_date)
    #   ).all()
    #   
    #   # 심각한 이벤트만 조회 (stage >= 3)
    #   serious = db.query(Event).filter(Event.stage >= 3).all() 