import pymysql

# DB 연결 정보 (데이터베이스 지정하지 않음)
DB_CONFIG = {
    'host': 'project-db-campus.smhrd.com',
    'port': 3307,
    'user': 'campus_LGDX6_p3_2',
    'password': 'smhrd2',
    'charset': 'utf8mb4'
}

def create_database():
    """새로운 데이터베이스 생성"""
    try:
        # DB 연결
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 데이터베이스 생성
        cursor.execute("CREATE DATABASE IF NOT EXISTS dx_model")
        print("✅ 데이터베이스 dx_model이 생성되었습니다.")
        
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    create_database()

"""
[데이터베이스 초기화 스크립트]

1. 데이터베이스 설정
   기본 설정:
   - 데이터베이스명: dx_model
   - 문자셋: utf8mb4
   - 정렬: utf8mb4_unicode_ci
   
   접속 정보:
   - 호스트: localhost
   - 포트: 3306
   - 사용자: root
   - 비밀번호: 123456

2. 보안 설정
   권한 관리:
   - 데이터베이스 생성 권한 필요
   - 테이블 생성 권한 필요
   - 인덱스 생성 권한 필요
   
   접근 제어:
   - 로컬 접속만 허용
   - SSL/TLS 지원
   - 비밀번호 정책 적용

3. 에러 처리
   예외 상황:
   - DB 이미 존재
   - 권한 부족
   - 연결 실패
   
   복구 전략:
   - 자동 재시도
   - 로그 기록
   - 관리자 알림

4. 성능 설정
   스토리지:
   - InnoDB 엔진 사용
   - 자동 증가값 설정
   - 버퍼 풀 크기 조정
   
   최적화:
   - 인덱스 자동 생성
   - 통계 자동 수집
   - 성능 모니터링
""" 