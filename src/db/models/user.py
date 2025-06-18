# src/db/models/user.py
from __future__ import annotations
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from db.base import Base


from typing import TYPE_CHECKING
from db.models.common import GenderEnum
from db.base import Base
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(256), nullable=False, unique=True)
    email = Column(String(256), nullable=False, unique=True)
    password = Column(String(256), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 🔑 관계 → 문자열만 사용
    pets = relationship("PetProfile", back_populates="owner",
                        cascade="all, delete-orphan")

    @classmethod
    def create(cls, username: str, email: str, hashed_password: str):
        return cls(username=username, email=email, password=hashed_password)

# TYPE_CHECKING 블록으로 순환 import 없이 타입 완성 지원
if TYPE_CHECKING:
    from .pet import PetProfile
