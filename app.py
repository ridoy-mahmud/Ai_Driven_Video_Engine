from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.database import engine, init_db
from api.router import tasks_router
from api.service import TaskService
from services.llm_bridge import start_bridge_server, stop_bridge
from utils.config import api_config as settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_bridge_server()
    await init_db()
    yield
    TaskService.cancel_all_background_tasks()
    stop_bridge()
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(tasks_router, prefix="/v1/tasks", tags=["tasks"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=settings.app_port)
