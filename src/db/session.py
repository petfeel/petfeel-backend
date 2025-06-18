# src/db/session.py
"""
SQLAlchemy Engine ‧ SessionLocal ‧ get_db (FastAPI Depends)
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# DB 연결 정보 직접 설정
DATABASE_URL = "mysql+pymysql://campus_LGDX6_p3_2:smhrd2@project-db-campus.smhrd.com:3307/campus_LGDX6_p3_2"

# ① Engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,      # True 로 바꾸면 SQL 로그 출력
    future=True,
)

# ② Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)

# ③ FastAPI 의존성
def get_db() -> Generator[Session, None, None]:   # ✔ Session 을 제너릭에 명시
    db: Session = SessionLocal()                  # ✔ 타입 힌트도 Session
    try:
        yield db
    finally:
        db.close()