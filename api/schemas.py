from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TaskCreate(BaseModel):
    name: str
    prompt_source: Optional[str] = None
    tts_source: Optional[str] = None
    material_source: Optional[str] = None
    llm_source: Optional[str] = None
    tts_voices: Optional[list] = None
    tts_speed: Optional[float] = None
    video_type: Optional[str] = None
    video_speed: Optional[float] = None
    video_upload_path: Optional[str] = None  # Path to uploaded video for remix mode
    youtube_title: Optional[str] = None  # Auto-generated YouTube-ready title


class TaskResponse(BaseModel):
    id: int
    name: str
    status: str
    create_time: datetime
    update_time: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    result: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True
