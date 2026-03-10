from chromadb import HttpClient, PersistentClient, Client
from app.core.config import settings

def get_client() -> Client:
    """
    返回 Chroma 客户端，支持三种模式：
    - persistent: 本地数据库文件
    - http: 远程 Chroma 服务
    - auto: 优先 http，如果失败 fallback 到 persistent
    """
    mode = settings.CHROMA_MODE.lower()
    
    if mode == "persistent":
        return PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    
    elif mode == "http":
        return HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
    
    elif mode == "auto":
        try:
            # 尝试连接 http
            client = HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
            client.heartbeat()  # 测试是否可用
            return client
        except Exception:
            # fallback 到本地 persistent
            return PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    
    else:
        raise ValueError(f"Unsupported CHROMA_MODE: {settings.CHROMA_MODE}")