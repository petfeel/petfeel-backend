# db/models/pet_recorded.py

from sqlalchemy import Column, Integer, LargeBinary, DateTime, ForeignKey, String
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.base import Base

class PetRecorded(Base):
    __tablename__ = "pet_recorded"

    id = Column(Integer, primary_key=True, index=True)
    pet_id = Column(
        Integer,
        ForeignKey("pet_profile.id", ondelete="CASCADE"),
        nullable=False
    )
    recorded_video = Column(LargeBinary, nullable=False)
    video_name    = Column(String(255), nullable=False)
    created_at    = Column(DateTime, server_default=func.now())

    # 여기에 relationship 추가
    pet = relationship(
        "PetProfile",
        backref="recorded_videos",
        lazy="joined"  # 리스트 조회 시 N+1 방지
    )
