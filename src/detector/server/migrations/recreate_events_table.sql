-- 기존 테이블들 삭제
DROP TABLE IF EXISTS daily_summaries;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS dogs;

-- 강아지 정보 테이블 생성
CREATE TABLE dogs (
    pet_name VARCHAR(50) PRIMARY KEY,
    created_at DATETIME NOT NULL
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 이상행동 이벤트 테이블 생성
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    pet_name VARCHAR(50) NOT NULL,
    timestamp DATETIME NOT NULL,
    stage INTEGER NOT NULL,
    summary TEXT NOT NULL,
    video_data LONGBLOB,
    video_name VARCHAR(255),
    INDEX idx_timestamp (timestamp),
    INDEX idx_stage (stage),
    FOREIGN KEY (pet_name) REFERENCES dogs(pet_name) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 일일 요약 테이블 생성
CREATE TABLE daily_summaries (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    pet_name VARCHAR(50) NOT NULL,
    date DATE NOT NULL,
    normal_summary TEXT,
    abnormal_summary TEXT,
    INDEX idx_date (date),
    FOREIGN KEY (pet_name) REFERENCES dogs(pet_name) ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; 