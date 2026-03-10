from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    # ===== LLM / Embedding =====
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None
    
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str ="text-embedding-3-small"
    LLM_MODEL: str = "gpt-4o-mini"

    # ===== Chroma =====
    CHROMA_MODE: str = "persistent" # persistent / http / auto
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000

    # ===== SQLite =====
    FINGERPRINT_DB: str = "data/fingerprints.sqlite"
    
    # ===== Retrieval =====
    RETRIEVAL_MODE_DEFAULT: str = "vector"  # vector / hybrid / hybrid_rerank
    HYBRID_TOP_K: int = 20
    RERANK_TOP_N: int = 8
    RERANK_ENABLED: bool = True
    RERANK_BACKEND: str = "sentence_transformers"  # sentence_transformers / rule / bge(兼容别名)
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANK_DEVICE: str = "auto"  # auto / cpu / cuda
    BGE_RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"  # 兼容旧配置
    BGE_RERANK_USE_FP16: bool = False  # 兼容旧配置（当前实现不使用）
    RERANK_BLEND_ALPHA: float = 0.85  # final = alpha * bge_norm + (1-alpha) * fused_score
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
        
settings = Settings()
