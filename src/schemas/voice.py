from pydantic import BaseModel
from datetime import datetime
 
class VoiceRecordingResponse(BaseModel):
    """음성 녹음 응답 스키마"""
    id: int
    pet_name: str
    filename: str
    recorded_at: datetime
 
    class Config:
        from_attributes = True  # SQLAlchemy 모델 → Pydantic 변환 지원