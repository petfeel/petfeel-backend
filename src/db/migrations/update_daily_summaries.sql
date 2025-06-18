-- 기존 테이블 백업
CREATE TABLE daily_summaries_backup AS SELECT * FROM daily_summaries;

-- 기존 테이블 삭제
DROP TABLE daily_summaries;

-- 새로운 테이블 생성
CREATE TABLE daily_summaries (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    pet_id INTEGER NOT NULL,
    date DATE NOT NULL,
    normal_summary TEXT,
    abnormal_summary TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (pet_id) REFERENCES pet_profile(id) ON DELETE CASCADE,
    UNIQUE KEY uix_pet_date (pet_id, date)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 기존 데이터 복원
INSERT INTO daily_summaries (id, pet_id, date, normal_summary, abnormal_summary, created_at, updated_at)
SELECT id, pet_id, date, normal_summary, abnormal_summary, created_at, updated_at FROM daily_summaries_backup;

-- 백업 테이블 삭제
DROP TABLE daily_summaries_backup; 