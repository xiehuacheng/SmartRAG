from fastapi import APIRouter
from app.api.v1.endpoints import documents, health, query

v1_router = APIRouter(prefix="/v1")

# 文档相关接口
v1_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["documents"]
)

# 健康检查接口
v1_router.include_router(
    health.router,
    tags=["health"]
)

# 查询接口
v1_router.include_router(
    query.router,
    tags=["query"]
)
