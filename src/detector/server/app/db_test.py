import pymysql
from pathlib import Path
from datetime import datetime

# DB 연결
conn = pymysql.connect(
    host='project-db-campus.smhrd.com',
    port=3307,
    user='campus_LGDX6_p3_2',
    password='smhrd2',
    db='campus_LGDX6_p3_2',
    charset='utf8mb4'
)

def save_video_from_db():
    """DB에서 영상 데이터를 가져와서 파일로 저장"""
    
    # 저장할 디렉토리 생성
    output_dir = Path("video_test")
    output_dir.mkdir(exist_ok=True)
    
    try:
        with conn.cursor() as cursor:
            # 최근 영상 데이터 조회
            sql = """
                SELECT id, timestamp, stage, summary, video_data, video_name 
                FROM events 
                WHERE video_data IS NOT NULL 
                ORDER BY timestamp DESC
            """
            cursor.execute(sql)
            events = cursor.fetchall()
            
            print(f"Found {len(events)} events with video data")
            
            for event in events:
                event_id, timestamp, stage, summary, video_data, video_name = event
                if video_data and video_name:
                    # 파일명 생성
                    video_path = output_dir / f"test_{video_name}"
                    
                    # 영상 데이터 저장
                    with open(video_path, "wb") as f:
                        f.write(video_data)
                    
                    print(f"✅ Saved video: {video_path}")
                    print(f"   - Event ID: {event_id}")
                    print(f"   - Timestamp: {timestamp}")
                    print(f"   - Stage: {stage}")
                    print(f"   - Summary: {summary}")
                    print(f"   - File size: {len(video_data) / 1024:.1f} KB")
                    print()
    
    finally:
        conn.close()

if __name__ == "__main__":
    save_video_from_db() 