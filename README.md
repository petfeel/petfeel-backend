# 404NotFound-Project

# LG 전자 펫 가전의 경험을 확장하는 AI 기반 반려동물 케어 솔루션
“혼자 남겨진 반려동물, 보호자의 불안을 해결하는 AI 펫캠”

## 1. 목표와 기능

### 1. 반려동물 맞춤형 케어 공간
- AI를 통한 이상행동 탐지 기술
- 반려동물의 상태를 분석하고, 실시간 모니터링
- 보호자 부재 시에도 반려동물의 안전과 정서적 유대 강화
  
### 2. 반려동물의 일살을 함께하는 감성 케어 공간
- 반려동물의 루틴/이상행동 기록 및 리포트화
- 보호자 퇴근 후 하루 요약 보고서 및 행동 분석 설명 코멘트 제공
- LG 스마트홈 연계로 반려동물 행동 기반 자동화

## 2. 시스템 아키텍처 및 배포 URL
### 2.1 시스템 아키텍처
![Image](https://github.com/user-attachments/assets/1498d369-21d8-49c9-bfcf-cc590bba9811)

### 2.2 배포 APK
**Android**
[APK 직접 다운로드](https://블라블라.apk)
- 테스트용 계정
```
이메일 아이디 : seoyeon@gmail.com
비밀번호 : 1234
유저네임 : 이서연
```

## 3. 서비스 흐름도와 유스케이스
### 3.1 서비스 흐름도
![Image](https://github.com/user-attachments/assets/f912ac41-d8ea-4c15-ab08-f686e223893a)
![Image](https://github.com/user-attachments/assets/f59709a7-e05b-4d56-9dc9-287156e97631)

### 3.2 유스케이스
![Image](https://github.com/user-attachments/assets/752166e3-f426-4585-b547-2928e1ff328b)

## 4. 프로젝트 구조
```
PetFeelApp/
├── frontend/      # 프론트엔드 앱 (Flutter 기반, Figma)
├── backend/       # 백엔드 서버 (FastAPI)
├── ai-model/      # AI 모델 학습/분류 코드 (YOLOv11, OpenCV, Gemini 2.5 Flash 기반)
├── raspberry/     # 라즈베리파이용 실행 코드 및 카메라 모듈 연동
├── docs/          # 발표자료
└── README.md
```

## 5. 역할 분담
- 팀장 : 주후상
- FrontEnd : 김도은, 박원지, 박준호
- BackEnd & AI-Model : 나유진, 심수지, 이민우, 주후상

## 6. UI
### 6.1 대표 화면설계
![Image](https://github.com/user-attachments/assets/62a15581-bdcd-4096-8aa8-b68cbf4649fd)
![Image](https://github.com/user-attachments/assets/a7f91d36-b3c8-43b7-a925-0c4357843229)
![Image](https://github.com/user-attachments/assets/a220e30b-eccc-470a-b1e5-b62397c7d3b9)

## 7. 데이터베이스 모델링(ERD)
![Image](https://github.com/user-attachments/assets/6c97eb53-05e1-4baa-8ac9-ca5aa39f92b6)

## 8. Key Value
- Anxiety-Free : 실시간 이상행동 감지 -> 즉시 알림으로 '혹시 모를 사고' 불안 해소
- Actionable Insight : 단계(0-3)별 심각도 + 요약 리포트로 빠른 대응 방향 제시
- Effortless Tracking : 캘린더,영상,일기 자동 저장 -> 데이터 기반 건강 & 루틴 관리
- LG Ecosystem Synergy : LG의 로봇청소기,공기청청기 등과 연동해 공간까지 케어

