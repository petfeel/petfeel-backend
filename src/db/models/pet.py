# src/db/models/pet.py
from typing import TYPE_CHECKING
from db.models.common import GenderEnum
from db.base import Base
from sqlalchemy import (Column, Integer, String, Float, Date, DateTime,
                        ForeignKey, Boolean, Enum as SQLEnum,
                        UniqueConstraint, func)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime
 
 
class PetProfile(Base):
    __tablename__ = "pet_profile"
 
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"))
    pet_name = Column(String(100), nullable=False)
    pet_species = Column(String(100), nullable=False)
    age = Column(Integer)
    birth_date = Column(Date)
 
    gender = Column(SQLEnum(GenderEnum))
    weight = Column(Float)
    image_path = Column(String(512))
 
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
 
    # 🔑 관계 → 문자열만 사용
    owner = relationship("User", back_populates="pets")
 
if TYPE_CHECKING:
    from .user import User
   
   
class PetPreference(Base):
    """펫별 일상 목표치(기본값)"""
    __tablename__ = "pet_preferences"
 
    pet_id = Column(Integer,
                    ForeignKey("pet_profile.id", ondelete="CASCADE"),
                    primary_key=True)
    meals_target = Column(Integer, default=2)   # 기본 2회
    walks_target = Column(Integer, default=1)   # 기본 1회
    updated_at   = Column(DateTime,
                          server_default=func.now(),
                          onupdate=func.now())
 
class PetRoutine(Base):
    """날짜별 체크리스트"""
    __tablename__ = "pet_routines"
 
    id   = Column(Integer, primary_key=True)
    pet_id = Column(Integer,
                    ForeignKey("pet_profile.id", ondelete="CASCADE"),
                    index=True)
    date = Column(Date, nullable=False)
 
    vitamin_taken     = Column(Boolean, default=False)
    health_check_done = Column(Boolean, default=False)
 
    meal_count  = Column(Integer, default=0)
    meal_target = Column(Integer, default=2)
    walk_count  = Column(Integer, default=0)
    walk_target = Column(Integer, default=1)
 
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(),
                        onupdate=func.now())
 
    __table_args__ = (
        UniqueConstraint("pet_id", "date", name="uq_pet_date"),
    )
 
    # 하루 목표 달성 여부 — 프론트 배지용
    @hybrid_property
    def meal_done(self):  return self.meal_count >= self.meal_target
    @hybrid_property
    def walk_done(self):  return self.walk_count >= self.walk_target
 