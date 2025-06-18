# server/app/crud.py
from sqlalchemy.orm import Session
from datetime import datetime
from . import models

def create_event(
    db: Session,
    timestamp: datetime,
    stage: int,
    summary: str,
    video_data: bytes = None,
    video_name: str = None
) -> models.Event:
    db_event = models.Event(
        timestamp=timestamp,
        stage=stage,
        summary=summary,
        video_data=video_data,
        video_name=video_name
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event
