from db import SessionLocal, Base
from models import Dog

def check_dogs():
    """데이터베이스에 등록된 강아지 정보 확인"""
    db = SessionLocal()
    try:
        dogs = db.query(Dog).all()
        print("\n등록된 강아지 목록:")
        for dog in dogs:
            print(f"- 이름: {dog.name}")
            print(f"  등록일: {dog.created_at}")
    finally:
        db.close()

if __name__ == "__main__":
    check_dogs() 