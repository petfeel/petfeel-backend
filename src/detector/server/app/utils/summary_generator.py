import os
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv
import traceback

# 환경변수 로드
load_dotenv()

# API 키와 모델명 상수 정의
GOOGLE_API_KEY = "AIzaSyAodNAwhpYmQkLWPA3dv-giw0WppjLhjMY"
MODEL_NAME = "models/gemini-2.5-flash-preview-05-20"

def generate_normal_summary(events):
    """일반 행동(stage 0) 요약 생성"""
    try:
        print("\n🔍 일반 행동 요약 생성 시작")
        print(f"- 입력된 이벤트 수: {len(events)}")
        
        if not events:
            print("- 이벤트가 없음")
            return "오늘은 기록된 일반 행동이 없습니다."
            
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

위 내용을 바탕으로 강아지의 하루 일상을 일기 형식으로 3문장으로 요약해주세요."""
        
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
            summaries.append(e.summary)
        
        # 프롬프트 생성
        prompt = f"""오늘 강아지의 이상 행동:
{chr(10).join(summaries)}

위 내용을 바탕으로 강아지의 이상 행동을 일기 형식으로 3문장으로 요약해주세요."""
        
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