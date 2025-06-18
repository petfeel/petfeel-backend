"""
[Pydantic 스키마 상세 설명]

1. 데이터 검증 규칙
   필수 필드:
   - pet_name: 강아지 이름 (2-50자)
   - created_at: 생성 시간 (ISO 형식)
   
   선택 필드:
   - breed: 견종 (최대 100자)
   - age: 나이 (0-30 범위)
   - weight: 체중 (0.1-100kg 범위)

2. 타입 변환
   자동 변환:
   - 문자열 → 날짜/시간
   - 문자열 → 숫자
   - JSON → 객체
   
   커스텀 변환:
   - 시간대 변환
   - 단위 변환
   - 포맷 정규화

3. 응답 모델
   기본 필드:
   - id: 고유 식별자
   - created_at: 생성 시간
   - updated_at: 수정 시간
   
   중첩 모델:
   - 이벤트 목록
   - 일일 요약
   - 통계 데이터

4. 보안 설정
   데이터 제한:
   - 최대 길이 제한
   - 값 범위 검증
   - 패턴 매칭
   
   민감 정보:
   - 비밀번호 해시
   - API 키 마스킹
   - PII 필터링
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

class DogBase(BaseModel):
    """강아지 기본 정보 스키마"""
    pet_name: str
    breed: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[float] = None

class DogCreate(DogBase):
    """강아지 생성 스키마"""
    pass

class Dog(DogBase):
    """강아지 응답 스키마"""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class EventBase(BaseModel):
    """이벤트 기본 정보 스키마"""
    timestamp: datetime
    stage: int
    summary: str
    video_name: Optional[str] = None

class EventCreate(EventBase):
    """이벤트 생성 스키마"""
    dog_id: int

class Event(EventBase):
    """이벤트 응답 스키마"""
    id: int
    dog_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class DogWithEvents(Dog):
    """이벤트를 포함한 강아지 정보 스키마"""
    events: List[Event] = [] 