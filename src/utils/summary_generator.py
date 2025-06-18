import os
import sys
from datetime import datetime, date
import google.generativeai as genai
from dotenv import load_dotenv
import traceback

# 상대 경로 import를 위한 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
    print(f"Added to path: {parent_dir}")

from db.session import engine, SessionLocal, get_db
from db.models.event import DailySummary, Event
from sqlalchemy import and_

# 환경변수 로드
load_dotenv()

# API 키와 모델명 상수 정의
GOOGLE_API_KEY = "AIzaSyAodNAwhpYmQkLWPA3dv-giw0WppjLhjMY"
MODEL_NAME = "models/gemini-2.5-flash-preview-05-20"

def get_events_by_stage(db, pet_id: int, target_date: date, is_normal: bool = True):
    """특정 날짜의 정상/이상 행동 이벤트 조회"""
    try:
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        
        # stage 0은 정상, 1-3은 이상 행동
        stage_filter = Event.stage == 0 if is_normal else Event.stage > 0
        
        events = db.query(Event).filter(
            and_(
                Event.pet_id == pet_id,
                Event.created_at.between(start_datetime, end_datetime),
                stage_filter
            )
        ).all()
        
        print(f"\n🔍 이벤트 조회 결과 ({'정상' if is_normal else '이상'} 행동):")
        print(f"- 총 {len(events)}건")
        for e in events:
            print(f"- Stage {e.stage}: {e.summary}")
            
        return events
    except Exception as e:
        print(f"❌ 이벤트 조회 중 오류: {str(e)}")
        return []

def save_summaries_to_db(pet_id: int, normal_summary: str, abnormal_summary: str, target_date: date):
    """DB에 요약 저장"""
    db = None
    try:
        db = SessionLocal()
        print(f"\n💾 DB 저장 시도:")
        print(f"- pet_id: {pet_id}")
        print(f"- date: {target_date}")
        print(f"- normal_summary: {normal_summary[:50]}...")
        print(f"- abnormal_summary: {abnormal_summary[:50]}...")
        
        # 기존 요약이 있는지 확인
        existing = db.query(DailySummary).filter(
            and_(
                DailySummary.pet_id == pet_id,
                DailySummary.date == target_date
            )
        ).first()
        
        if existing:
            # 기존 요약 업데이트
            existing.normal_summary = normal_summary
            existing.abnormal_summary = abnormal_summary
            print(f"✅ 기존 요약 업데이트 완료 (pet_id: {pet_id}, date: {target_date})")
        else:
            # 새 요약 생성
            new_summary = DailySummary(
                pet_id=pet_id,
                date=target_date,
                normal_summary=normal_summary,
                abnormal_summary=abnormal_summary
            )
            db.add(new_summary)
            print(f"✅ 새 요약 저장 완료 (pet_id: {pet_id}, date: {target_date})")
            
        db.commit()
        return True
        
    except Exception as e:
        print(f"❌ DB 저장 중 오류 발생:")
        print(f"오류 유형: {type(e).__name__}")
        print(f"오류 내용: {str(e)}")
        print(f"상세 정보:\n{traceback.format_exc()}")
        if db:
            db.rollback()
        return False
    finally:
        if db:
            db.close()

def generate_normal_summary(events):
    """일반 행동(stage 0) 요약 생성"""
    try:
        print("\n🔍 일반 행동 요약 생성 시작")
        print(f"- 입력된 이벤트 수: {len(events)}")
        
        if not events:
            print("- 이벤트가 없음")
            return "오늘은 특별한 일반 행동이 없었습니다."
            
        # Gemini API 설정
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(model_name=MODEL_NAME)
            
        # 이벤트 요약 텍스트 추출
        print("\n📋 이벤트 목록:")
        summaries = []
        for e in events:
            print(f"- {e.summary}")
            summaries.append(e.summary)
        
        # 프롬프트 생성
        prompt = f"""오늘 강아지의 일반 행동:
{chr(10).join(summaries)}

위 내용을 바탕으로 강아지의 하루 일상을 이야기 일기 형식으로 3문장으로 요약해주세요. 보호자는 강아지가 뭘 했는지, 어떤걸 느꼈는지 보고싶어해요. 
이건 강아지가 쓰는 일기에요. 강아지는 보호자를 보호자님이라고 불러요."""
        
        print("\n📝 생성된 프롬프트:")
        print(prompt)
        
        print("\n🤖 Gemini API 호출 중...")
        # Gemini로 요약 생성
        response = model.generate_content(prompt)
        result = response.text.strip()
        
        print("\n✅ 생성된 요약:")
        print(result)
        return result
        
    except Exception as e:
        print(f"\n❌ 일반 행동 요약 생성 중 오류 발생:")
        print(f"오류 유형: {type(e).__name__}")
        print(f"오류 내용: {str(e)}")
        print(f"상세 정보:\n{traceback.format_exc()}")
        return f"요약 생성 중 오류가 발생했습니다: {type(e).__name__}"

def generate_abnormal_summary(events):
    """이상 행동(stage 1-3) 요약 생성"""
    try:
        print("\n🔍 이상 행동 요약 생성 시작")
        print(f"- 입력된 이벤트 수: {len(events)}")
        
        if not events:
            print("- 이벤트가 없음")
            return "오늘은 특별한 이상 행동이 없었습니다."
            
        # Gemini API 설정
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel(model_name=MODEL_NAME)
            
        # 이벤트 요약 텍스트 추출
        print("\n📋 이벤트 목록:")
        summaries = []
        for e in events:
            print(f"- Stage {e.stage}: {e.summary}")
            summaries.append(f"[위험도 {e.stage}] {e.summary}")
        
        # 프롬프트 생성
        prompt = f"""오늘 강아지의 이상 행동:
{chr(10).join(summaries)}

위 내용을 바탕으로, 강아지가 하루 동안 보였던 이상한 행동들을 일기 형식으로 3문장으로 요약해주세요. 강아지는 그 행동이 위험하거나 이상하다는 걸 인식하지 못한 채 순수하게 보호자님에게 하루를 이야기하지만,  
보호자는 그 내용을 읽고 분명히 “뭔가 이상하다”, “왜 이러지?”, “불안하다”는 걱정을 느껴야 합니다. 
예를 들어 불안한 행동, 갑작스러운 짖음, 반복 행동, 혼잣말, 이유 없는 격한 움직임 등을 묘사해주세요.
- 평소와 다르게 과하게 흥분하거나 불안해함
- 이유 없이 같은 행동을 반복하거나 한곳을 계속 응시함
- 보호자 없이 혼자 뭔가에 겁을 먹거나 이상하게 반응함
- 의미 없는 행동을 기쁜 듯 묘사하지만, 보호자가 보면 불안한 행동임
강아지는 “보호자님”이라고 부르며, 혼잣말처럼 말합니다. 
보호자는 이 일기를 보고 강아지의 이상 행동을 **명확히 인식하고 걱정**해야 합니다."""
        
        print("\n📝 생성된 프롬프트:")
        print(prompt)
                                     
        print("\n🤖 Gemini API 호출 중...")
        # Gemini로 요약 생성
        response = model.generate_content(prompt)
        result = response.text.strip()
        
        print("\n✅ 생성된 요약:")
        print(result)
        return result
        
    except Exception as e:
        print(f"\n❌ 이상 행동 요약 생성 중 오류 발생:")
        print(f"오류 유형: {type(e).__name__}")
        print(f"오류 내용: {str(e)}")
        print(f"상세 정보:\n{traceback.format_exc()}")
        return f"요약 생성 중 오류가 발생했습니다: {type(e).__name__}"

def generate_and_save_summaries(pet_id: int, target_date: date):
    """요약 생성 및 DB 저장"""
    db = None
    try:
        db = SessionLocal()
        
        # 정상/이상 행동 이벤트 조회
        normal_events = get_events_by_stage(db, pet_id, target_date, is_normal=True)
        abnormal_events = get_events_by_stage(db, pet_id, target_date, is_normal=False)
        
        # 요약 생성
        normal_summary = generate_normal_summary(normal_events)
        abnormal_summary = generate_abnormal_summary(abnormal_events)
        
        # DB 저장
        if save_summaries_to_db(pet_id, normal_summary, abnormal_summary, target_date):
            print(f"\n✅ 요약 생성 및 저장 완료 (pet_id: {pet_id})")
            return normal_summary, abnormal_summary
        else:
            print(f"\n⚠️ DB 저장 실패 (pet_id: {pet_id})")
            return None, None
            
    except Exception as e:
        print(f"\n❌ 요약 생성 및 저장 중 오류 발생:")
        print(f"오류 유형: {type(e).__name__}")
        print(f"오류 내용: {str(e)}")
        print(f"상세 정보:\n{traceback.format_exc()}")
        return None, None
    finally:
        if db:
            db.close() 