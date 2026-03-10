import logging
import os
from datetime import datetime

from langchain_community.document_loaders import TextLoader, UnstructuredMarkdownLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.retrieval.embedding.embedding_factory import get_embeddings
from app.retrieval.vector_store.chroma_client import get_client
from app.schemas.documents import IngestResponse
from app.utils.fingerprint_store import exists, insert
from app.utils.hashing import sha256_text

logger = logging.getLogger("uvicorn.error")


class IngestionService:
    @staticmethod
    def _has_indexed_chunks(collection, doc_hash: str) -> bool:
        """
        判断当前 collection 中是否已存在该 doc_hash 的 chunk。
        用于识别“指纹存在但向量库丢失”的脏状态。
        """
        try:
            rows = collection.get(
                where={"document_id": doc_hash},
                limit=1,
                include=["metadatas"],
            )
            ids = rows.get("ids", []) or []
            return len(ids) > 0
        except Exception:
            return False

    def _ingest_full_text(self, full_text: str, metadata) -> IngestResponse:
        doc_hash = sha256_text(full_text)

        client = get_client()
        collection_name = f"team_{metadata.team_id}"
        collection = client.get_or_create_collection(name=collection_name)

        if exists(doc_hash, metadata.team_id):
            if self._has_indexed_chunks(collection, doc_hash):
                return IngestResponse(
                    document_id=doc_hash,
                    doc_hash=doc_hash,
                    chunks_created=0,
                    embedding_model=None,
                    index_status="duplicate",
                    ingestion_time=datetime.now(),
                )

            logger.warning(
                "[INGEST_STALE_FINGERPRINT] team_id=%s doc_hash=%s 指纹存在但未找到已索引 chunk，将执行重建。",
                metadata.team_id,
                doc_hash,
            )

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150,
        )
        chunks = splitter.split_text(full_text)

        embedding_model = get_embeddings()
        vectors = embedding_model.embed_documents(chunks)

        chunk_ids = [f"{doc_hash}_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "team_id": metadata.team_id,
                "source": metadata.source,
                "document_id": doc_hash,
                "chunk_id": chunk_ids[i],
                "tags": metadata.tags,
                "security_level": metadata.security_level,
                "chunk_index": i,
                "embedding_model": settings.EMBEDDING_MODEL,
            }
            for i in range(len(chunks))
        ]

        collection.add(
            ids=chunk_ids,
            documents=chunks,
            metadatas=metadatas,
            embeddings=vectors,
        )

        # 已存在时会被 OR IGNORE，保持幂等。
        insert(
            doc_hash=doc_hash,
            team_id=metadata.team_id,
            source=metadata.source,
        )

        return IngestResponse(
            document_id=doc_hash,
            doc_hash=doc_hash,
            chunks_created=len(chunks),
            embedding_model=settings.EMBEDDING_MODEL,
            index_status="completed",
            ingestion_time=datetime.now(),
        )

    def ingest(self, file_path: str, metadata) -> IngestResponse:
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".txt":
            loader = TextLoader(file_path, encoding="utf-8")
        elif ext == ".md":
            loader = UnstructuredMarkdownLoader(file_path)
        elif ext == ".pdf":
            loader = PyPDFLoader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        documents = loader.load()
        full_text = "\n".join([doc.page_content for doc in documents])
        return self._ingest_full_text(full_text, metadata)

    def ingest_text(self, text: str, metadata) -> IngestResponse:
        full_text = text.strip()
        if not full_text:
            raise ValueError("text is empty")
        return self._ingest_full_text(full_text, metadata)


ingestion_service = IngestionService()
