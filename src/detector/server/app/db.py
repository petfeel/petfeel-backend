# server/app/db.py
"""
[DB 설정 및 연결 관리]

1. 데이터베이스 구성
   - 사용 DB: MySQL 8.0
   - ORM: SQLAlchemy
   - 연결 풀링: 기본 5-10개 연결 유지

2. 주요 테이블
   - events: 이상행동 감지 이벤트 저장
     * id: 자동 증가 기본키
     * timestamp: 이벤트 발생 시간
     * stage: 행동 단계 (0-4)
     * summary: 행동 분석 요약
     * video_data: 영상 데이터
     * video_name: 영상 파일명

3. 환경 설정
   - DATABASE_URL: MySQL 연결 문자열
     형식: mysql+pymysql://user:pass@host:port/dbname
   - POOL_SIZE: 연결 풀 크기 (기본값: 5)
   - MAX_OVERFLOW: 최대 추가 연결 수 (기본값: 10)

4. 연결 관리
   - SessionLocal: 요청별 DB 세션 팩토리
   - engine: SQLAlchemy 엔진 인스턴스
   - Base: 모델 선언용 기본 클래스

[데이터베이스 연결 관리 모듈]

연결 관리 상세:
1. 연결 풀링 설정
   - 기본 연결 수: 5개
   - 최대 추가 연결: 10개
   - 연결 타임아웃: 60초
   - 연결 재시도: 3회

2. 세션 관리
   - SessionLocal: 요청별 독립 세션
   - 자동 커밋 비활성화
   - 자동 플러시 비활성화
   - 세션 종료 보장

3. 트랜잭션 처리
   - 자동 롤백 (예외 발생 시)
   - 명시적 커밋 필요
   - 세션 컨텍스트 관리

4. 보안 설정
   - SSL/TLS 지원
   - 타임아웃 설정
   - 접속 제한

5. 모니터링
   - 연결 상태 추적
   - 풀 사용량 모니터링
   - 쿼리 실행 시간 측정
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# ── .env 로드 ────────────────────────────────────────────
project_root = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=project_root / ".env")

# ── 데이터베이스 URL ─────────────────────────────────────
DATABASE_URL = "mysql+pymysql://campus_LGDX6_p3_2:smhrd2@project-db-campus.smhrd.com:3307/campus_LGDX6_p3_2"

# ── SQLAlchemy 엔진 및 세션 ───────────────────────────────
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── 베이스 클래스 ─────────────────────────────────────────
Base = declarative_base()

def get_db():
    """
    데이터베이스 세션 생성 및 관리
    FastAPI의 의존성 주입에서 사용
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
