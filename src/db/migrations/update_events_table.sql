-- 기존 테이블 백업
CREATE TABLE events_backup AS SELECT * FROM events;

-- 기존 테이블 삭제
DROP TABLE events;

-- 새로운 테이블 생성
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    pet_id INTEGER NOT NULL,
    stage INTEGER NOT NULL DEFAULT 0,
    summary TEXT,
    video_name VARCHAR(512),
    video_data LONGBLOB,  -- 영상 데이터 저장용 컬럼
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pet_id) REFERENCES pet_profile(id) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 기존 데이터 복원 (timestamp를 created_at으로 변환)
INSERT INTO events (id, pet_id, stage, summary, video_name, created_at)
SELECT id, pet_id, stage, summary, video_name, created_at FROM events_backup;

-- 백업 테이블 삭제
DROP TABLE events_backup; 