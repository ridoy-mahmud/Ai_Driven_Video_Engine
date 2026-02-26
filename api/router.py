import asyncio
import os
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from api import crud
from api.database import get_session
from api.models import TaskStatus
from api.schemas import TaskCreate, TaskResponse
from api.service import TaskService
from utils.config import api_config as settings

tasks_router = APIRouter()


@tasks_router.post("/", response_model=TaskResponse)
async def create_task(task: TaskCreate, session: AsyncSession = Depends(get_session)):
    db_task = await crud.create_task(session, task)

    background_task = asyncio.create_task(TaskService.process_task(db_task.id, task))
    TaskService._background_tasks[db_task.id] = background_task

    return db_task


@tasks_router.post("/upload", response_model=TaskResponse)
async def upload_video_task(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Upload a video file for AI remix/analysis.
    
    The video will be analyzed by LLM, a social-media-ready script will be generated,
    and a new video with voiceover and subtitles will be created.
    """
    # Save uploaded file
    upload_dir = "./uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ".mp4"
    unique_name = f"{uuid.uuid4().hex}{file_ext}"
    upload_path = os.path.join(upload_dir, unique_name)
    
    with open(upload_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Create task with upload path
    task = TaskCreate(
        name=f"Video Remix: {file.filename or 'uploaded_video'}",
        video_upload_path=upload_path,
        prompt_source="auto",
    )
    
    db_task = await crud.create_task(session, task)
    background_task = asyncio.create_task(TaskService.process_task(db_task.id, task))
    TaskService._background_tasks[db_task.id] = background_task
    
    return db_task


@tasks_router.post("/{task_id}/cancel")
async def cancel_task(task_id: int, session: AsyncSession = Depends(get_session)):
    task = await crud.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Only running tasks can be cancelled")

    background_task = TaskService._background_tasks.get(task_id)
    if background_task and not background_task.done():
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            pass

    return {"message": "Task was cancelled"}


@tasks_router.get("/{task_id}", response_model=TaskResponse)
async def get_task_status(task_id: int, session: AsyncSession = Depends(get_session)):
    task = await crud.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@tasks_router.get("/queue/status/{task_date}")
async def get_queue_status(task_date: str, session: AsyncSession = Depends(get_session)):
    status_counts = await crud.get_status(session, task_date)
    return {
        "max_concurrent_tasks": settings.max_concurrent_tasks,
        "running_tasks": status_counts.get(TaskStatus.RUNNING, 0),
        "pending_tasks": status_counts.get(TaskStatus.PENDING, 0),
        "completed_tasks": status_counts.get(TaskStatus.COMPLETED, 0),
        "failed_tasks": status_counts.get(TaskStatus.FAILED, 0),
        "timeout_tasks": status_counts.get(TaskStatus.TIMEOUT, 0),
        "available_slots": settings.max_concurrent_tasks - TaskService._running_tasks,
    }


@tasks_router.get("/list/{task_date}", response_model=List[TaskResponse])
async def get_task_list(task_date: str, session: AsyncSession = Depends(get_session)):
    return await crud.get_task_list(session, task_date)
