from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health():
    """
    健康检查接口
    """
    return {"status": "ok"}