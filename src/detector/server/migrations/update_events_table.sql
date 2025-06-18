-- 기존 테이블 백업
CREATE TABLE events_backup AS SELECT * FROM events;

-- 기존 테이블 삭제
DROP TABLE events;

-- 새로운 테이블 생성
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    timestamp DATETIME NOT NULL,
    stage INTEGER NOT NULL,
    summary TEXT NOT NULL,
    video_data LONGBLOB,
    video_name VARCHAR(255),
    INDEX idx_timestamp (timestamp),
    INDEX idx_stage (stage)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 기존 데이터 복원 (video_data와 video_name은 NULL로 설정)
INSERT INTO events (id, timestamp, stage, summary)
SELECT id, timestamp, stage, summary FROM events_backup;

-- 백업 테이블 삭제
DROP TABLE events_backup; 