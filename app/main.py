from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.v1.router import v1_router
from app.utils.fingerprint_store import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="SmartRAG", lifespan=lifespan)

# 挂载 v1 路由
app.include_router(v1_router)
