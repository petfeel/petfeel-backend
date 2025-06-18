import pymysql

# DB 연결
conn = pymysql.connect(
    host='project-db-campus.smhrd.com',
    port=3307,
    user='campus_LGDX6_p3_2',
    password='smhrd2',
    db='campus_LGDX6_p3_2',
)

try:
    with conn.cursor() as cursor:
        # 기존 video_path 컬럼이 있다면 제거
        try:
            cursor.execute("ALTER TABLE events DROP COLUMN video_path;")
            print("✅ video_path 컬럼이 제거되었습니다.")
        except pymysql.err.OperationalError as e:
            if e.args[0] == 1091:  # Can't DROP column
                print("ℹ️ video_path 컬럼이 이미 존재하지 않습니다.")
            else:
                raise e

        # video_data와 video_name 컬럼 추가
        try:
            cursor.execute("ALTER TABLE events ADD COLUMN video_data LONGBLOB;")
            print("✅ video_data 컬럼이 추가되었습니다.")
        except pymysql.err.OperationalError as e:
            if e.args[0] == 1060:  # Duplicate column
                print("ℹ️ video_data 컬럼이 이미 존재합니다.")
            else:
                raise e

        try:
            cursor.execute("ALTER TABLE events ADD COLUMN video_name VARCHAR(255);")
            print("✅ video_name 컬럼이 추가되었습니다.")
        except pymysql.err.OperationalError as e:
            if e.args[0] == 1060:  # Duplicate column
                print("ℹ️ video_name 컬럼이 이미 존재합니다.")
            else:
                raise e

        conn.commit()
        print("✅ 데이터베이스 스키마가 성공적으로 수정되었습니다.")

except Exception as e:
    print(f"❌ 오류 발생: {e}")
    conn.rollback()

finally:
    conn.close() 