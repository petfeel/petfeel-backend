# services/voice_service.py

from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session


class VoiceService:
    """
    음성 녹음 관련 비즈니스 로직 모듈
    """

    # ────────────────────────────────────────────────────────────
    # Row → dict 유틸
    # ────────────────────────────────────────────────────────────
    @staticmethod
    def _row_as_dict(row) -> Dict[str, Any]:
        """
        SQLAlchemy 1.4 / 2.x 호환 Row → dict 변환
        """
        if isinstance(row, dict):
            return row
        if hasattr(row, "_mapping"):
            return dict(row._mapping)
        return dict(row)

    # ────────────────────────────────────────────────────────────
    # 반려동물 정보 조회
    # ────────────────────────────────────────────────────────────
    async def get_pet_info_by_name(self, db: Session, pet_name: str) -> dict:
        """반려동물 이름으로 ID·owner 조회"""
        row = db.execute(
            text("""
                SELECT p.id       AS pet_id,
                       p.owner_id AS owner_id,
                       p.pet_name AS pet_name
                  FROM pet_profile p
                 WHERE p.pet_name = :pet_name
            """),
            {"pet_name": pet_name},
        ).fetchone()

        if not row:
            raise HTTPException(404, f"반려동물을 찾을 수 없습니다: {pet_name}")

        return {"pet_id": row.pet_id, "owner_id": row.owner_id, "pet_name": row.pet_name}

    # ────────────────────────────────────────────────────────────
    # 녹음 파일 저장
    # ────────────────────────────────────────────────────────────
    async def save_voice_recording(
        self,
        db: Session,
        pet_name: str,
        voice_data: bytes,
        filename: str,
    ) -> dict:
        """음성 녹음을 DB에 저장하고 메타데이터 반환"""
        try:
            pet_info = await self.get_pet_info_by_name(db, pet_name)

            db.execute(
                text("""
                    INSERT INTO user_voice (
                        owner_id,
                        pet_id,
                        pet_name,
                        voice_data,
                        voice_filename
                    )
                    VALUES (
                        :owner_id,
                        :pet_id,
                        :pet_name,
                        :voice_data,
                        :voice_filename
                    )
                """),
                {
                    "owner_id": pet_info["owner_id"],
                    "pet_id": pet_info["pet_id"],
                    "pet_name": pet_name,
                    "voice_data": voice_data,
                    "voice_filename": filename,
                },
            )
            db.commit()

            row = db.execute(
                text("""
                    SELECT id,
                           pet_name,
                           voice_filename,
                           recorded_at
                      FROM user_voice
                     WHERE pet_name = :pet_name
                  ORDER BY id DESC
                     LIMIT 1
                """),
                {"pet_name": pet_name},
            ).fetchone()

            return {
                "id": row.id,
                "pet_name": row.pet_name,
                "filename": row.voice_filename,
                "recorded_at": row.recorded_at.isoformat(),
            }
        except Exception as e:
            db.rollback()
            raise HTTPException(500, f"음성 파일 저장 실패: {e}")

    # ────────────────────────────────────────────────────────────
    # 모든 녹음 메타데이터 조회
    # ────────────────────────────────────────────────────────────
    async def get_all_recordings(self, db: Session) -> List[dict]:
        """모든 녹음 메타데이터(리스트용)"""
        try:
            rows = (
                db.execute(
                    text("""
                        SELECT id,
                               pet_name,
                               voice_filename AS filename,
                               recorded_at,
                               '00:00'        AS duration
                          FROM user_voice
                      ORDER BY recorded_at DESC
                    """)
                )
                .mappings()
                .all()
            )
            return rows
        except Exception as e:
            raise HTTPException(500, f"녹음 목록 조회 실패: {e}")

    # ────────────────────────────────────────────────────────────
    # 반려동물별 파일 이름 목록 조회
    # ────────────────────────────────────────────────────────────
    async def get_voice_filenames(self, db: Session, pet_name: str) -> List[str]:
        """반려동물별 파일 이름 목록"""
        try:
            rows = db.execute(
                text("""
                    SELECT DISTINCT voice_filename
                      FROM user_voice
                     WHERE pet_name = :pet_name
                  ORDER BY voice_filename
                """),
                {"pet_name": pet_name},
            )
            return [r.voice_filename for r in rows.fetchall()]
        except Exception as e:
            raise HTTPException(500, f"음성 목록 조회 실패: {e}")

    # ────────────────────────────────────────────────────────────
    # pet_name+filename 으로 음성 데이터 조회
    # ────────────────────────────────────────────────────────────
    async def get_voice_by_filename(
        self, db: Session, pet_name: str, filename: str
    ) -> Optional[dict]:
        """pet_name+filename 으로 음성 데이터 조회"""
        try:
            row = db.execute(
                text("""
                    SELECT voice_data
                      FROM user_voice
                     WHERE pet_name = :pet_name
                       AND voice_filename = :filename
                     LIMIT 1
                """),
                {"pet_name": pet_name, "filename": filename},
            ).fetchone()

            if not row:
                return None
            return {"voice_data": row.voice_data}
        except Exception as e:
            raise HTTPException(500, f"음성 파일 조회 실패: {e}")

    # ────────────────────────────────────────────────────────────
    # 특정 반려동물의 녹음 메타데이터 조회
    # ────────────────────────────────────────────────────────────
    async def get_recordings_by_pet_name(
        self, db: Session, pet_name: str
    ) -> List[dict]:
        """특정 반려동물의 녹음 메타데이터"""
        try:
            rows = (
                db.execute(
                    text("""
                        SELECT id,
                               pet_name,
                               voice_filename AS filename,
                               recorded_at
                          FROM user_voice
                         WHERE pet_name = :pet_name
                      ORDER BY recorded_at DESC
                    """),
                    {"pet_name": pet_name},
                )
                .mappings()
                .all()
            )
            return [
                {
                    **r,
                    "recorded_at": r["recorded_at"].isoformat() if r["recorded_at"] else None,
                }
                for r in rows
            ]
        except Exception as e:
            raise HTTPException(500, f"녹음 목록 조회 실패: {e}")

    # ────────────────────────────────────────────────────────────
    # 녹음 파일 이름/부제목 변경
    # ────────────────────────────────────────────────────────────
    async def rename_recording(
        self,
        db: Session,
        recording_id: int,
        new_filename: str,
        new_subtitle: Optional[str] = None,
    ) -> Dict[str, Any]:
        """녹음 제목(voice_filename) 및 부제(pet_name) 업데이트 후, 전체 레코드 반환"""
        # 1) extension 체크
        if not new_filename.lower().endswith(".aac"):
            new_filename += ".aac"

        try:
            # 2) update
            db.execute(
                text("""
                    UPDATE user_voice
                       SET voice_filename = :filename
                         , pet_name       = COALESCE(:subtitle, pet_name)
                     WHERE id = :id
                """),
                {
                    "id": recording_id,
                    "filename": new_filename,
                    "subtitle": new_subtitle,
                },
            )
            db.commit()

            # 3) 갱신된 행 조회
            row = db.execute(
                text("""
                    SELECT id,
                           pet_name,
                           voice_filename AS filename,
                           recorded_at
                      FROM user_voice
                     WHERE id = :id
                """),
                {"id": recording_id},
            ).fetchone()

            if not row:
                raise HTTPException(404, "녹음 기록을 찾을 수 없습니다")

            return {
                "id": row.id,
                "pet_name": row.pet_name,
                "filename": row.filename,
                "recorded_at": row.recorded_at.isoformat(),
            }

        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(500, f"이름 변경 실패: {e}")

    # ────────────────────────────────────────────────────────────
    # 녹음 레코드 삭제
    # ────────────────────────────────────────────────────────────
    async def delete_recording(self, db: Session, recording_id: int) -> None:
        """녹음 레코드 삭제"""
        try:
            db.execute(
                text("DELETE FROM user_voice WHERE id = :id"),
                {"id": recording_id},
            )
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(500, f"녹음 삭제 실패: {e}")

    # ────────────────────────────────────────────────────────────
    # ID 기반 음성 데이터 조회 (스트리밍/다운로드용)
    # ────────────────────────────────────────────────────────────
    async def get_voice_file(
        self,
        recording_id: int,
        db: Session
    ) -> Optional[Dict[str, Any]]:
        """
        ID 기반으로 음성 데이터와 원본 파일명을 조회
        """
        try:
            row = db.execute(
                text("""
                    SELECT voice_data,
                           voice_filename AS filename
                      FROM user_voice
                     WHERE id = :id
                     LIMIT 1
                """),
                {"id": recording_id},
            ).fetchone()

            if not row:
                return None

            return {
                "voice_data": row.voice_data,
                "filename": row.filename,
            }
        except Exception as e:
            raise HTTPException(500, f"음성 파일 조회 실패: {e}")

    # ────────────────────────────────────────────────────────────
    # 서버에서 음성 파일 재생
    # ────────────────────────────────────────────────────────────
    async def play_voice_on_server(
        self,
        recording_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        서버 컴퓨터에서 음성 파일 재생
        """
        import os
        import tempfile
        from pathlib import Path
        import traceback
        import subprocess
        
        # 음성 파일 폴더 생성 (존재하지 않는 경우)
        voice_folder = Path("./voice_cache")
        voice_folder.mkdir(exist_ok=True)
        
        try:
            # 1. DB에서 음성 파일 데이터 조회
            voice_data = await self.get_voice_file(recording_id, db)
            if not voice_data:
                raise HTTPException(404, "음성 파일을 찾을 수 없습니다")
            
            # 디버깅용 로그
            print(f"음성 파일 정보: ID={recording_id}, 파일명={voice_data['filename']}")
            
            # 파일 이름 및 경로 설정
            filename = voice_data["filename"]
            # 파일 확장자 확인 및 수정 (AAC 포맷 가정)
            if not filename.lower().endswith(('.aac', '.mp3', '.wav')):
                filename += '.aac'  # 기본 확장자 추가
                
            local_path = voice_folder / f"{recording_id}_{filename}"
            abs_path = local_path.absolute()
            
            # 바이너리 데이터 크기 로깅
            binary_data = voice_data["voice_data"]
            print(f"바이너리 데이터 크기: {len(binary_data)} 바이트")
            
            # 2. 로컬 파일 존재 여부 확인
            if not local_path.exists():
                # 파일이 없으면 저장
                try:
                    print(f"음성 파일 저장 시작: {local_path}")
                    with open(local_path, "wb") as f:
                        f.write(binary_data)
                    print(f"음성 파일 저장 완료: {local_path}, 크기: {os.path.getsize(local_path)} 바이트")
                except Exception as e:
                    print(f"파일 저장 오류: {e}")
                    print(traceback.format_exc())
                    raise HTTPException(500, f"파일 저장 오류: {e}")
            else:
                print(f"기존 파일 사용: {local_path}, 크기: {os.path.getsize(local_path)} 바이트")
                
            # 3. 직접 시스템 명령어로 재생 (간단하고 효과적인 방법)
            try:
                print("시스템 명령어로 직접 재생 시도...")
                
                # Windows 환경
                if os.name == 'nt':
                    # cmd.exe를 이용한 미디어 플레이어 명령 (새 창에서 실행)
                    cmd = f'start "" "{abs_path}"'  # Windows 기본 플레이어로 열기
                    print(f"실행 명령어: {cmd}")
                    subprocess.Popen(cmd, shell=True)
                    return {
                        "success": True,
                        "message": f"Windows 기본 플레이어로 재생 중: {filename}",
                        "path": str(local_path)
                    }
                else:
                    # Unix/Linux 환경
                    cmd = f'xdg-open "{abs_path}"'  # Linux 기본 플레이어로 열기
                    subprocess.Popen(cmd, shell=True)
                    return {
                        "success": True,
                        "message": f"Linux 기본 플레이어로 재생 중: {filename}",
                        "path": str(local_path)
                    }
            except Exception as e:
                print(f"시스템 명령어 재생 실패: {e}")
                print(traceback.format_exc())
            
            # 4. 여러 재생 방법 시도
            success = False
            error_messages = []
            
            # 방법 1: 사운드 플레이 방법 (windows)
            if os.name == 'nt':
                try:
                    print("Windows 기본 사운드 재생 명령 시도...")
                    powershell_cmd = f'powershell -c "Add-Type -AssemblyName System.Speech; $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; $speak.Speak(\\"음성 파일 재생\\")"'
                    subprocess.Popen(powershell_cmd, shell=True)
                    
                    # 기본 미디어 플레이어로 파일 열기
                    os.startfile(abs_path)
                    success = True
                    return {
                        "success": True,
                        "message": f"Windows 시스템 재생 중: {filename}",
                        "path": str(local_path)
                    }
                except Exception as e:
                    error_msg = f"Windows 기본 재생 실패: {e}"
                    print(error_msg)
                    error_messages.append(error_msg)
            
            # 방법 2: pygame 사용 시도
            try:
                print("pygame 재생 시도...")
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.load(str(abs_path))
                pygame.mixer.music.play()
                success = True
                return {
                    "success": True,
                    "message": f"pygame으로 재생 중: {filename}",
                    "path": str(local_path)
                }
            except Exception as e:
                error_msg = f"pygame 재생 실패: {e}"
                print(error_msg)
                error_messages.append(error_msg)
            
            # 방법 3: 명시적으로 Windows Media Player 실행
            if os.name == 'nt':
                try:
                    print("Windows Media Player 명시적 실행 시도...")
                    wmp_cmd = f'start wmplayer "{abs_path}"'
                    os.system(wmp_cmd)
                    success = True
                    return {
                        "success": True,
                        "message": f"Windows Media Player로 재생 중: {filename}",
                        "path": str(local_path)
                    }
                except Exception as e:
                    error_msg = f"WMP 실행 실패: {e}"
                    print(error_msg)
                    error_messages.append(error_msg)
            
            # 모든 방법 실패 시
            if not success:
                error_summary = "; ".join(error_messages)
                print(f"모든 재생 방법 실패: {error_summary}")
                return {
                    "success": True,  # 파일 저장은 성공
                    "message": f"파일은 저장됨, 재생 실패: {error_summary[:100]}...",
                    "path": str(local_path)
                }
                
        except HTTPException:
            raise
        except Exception as e:
            print(f"서버 재생 처리 오류: {e}")
            print(traceback.format_exc())
            raise HTTPException(500, f"서버 재생 오류: {e}")
