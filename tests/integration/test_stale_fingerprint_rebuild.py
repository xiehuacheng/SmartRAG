from __future__ import annotations

from fastapi.testclient import TestClient
from chromadb.errors import NotFoundError

from app.main import app
from app.retrieval.vector_store.chroma_client import get_client
from app.utils.fingerprint_store import delete, insert
from app.utils.hashing import sha256_text

client = TestClient(app)


def test_rebuild_when_fingerprint_exists_but_chunks_missing(monkeypatch):
    team_id = "team_stale_fix"
    text = "stale fingerprint rebuild test text"
    doc_hash = sha256_text(text)
    collection_name = f"team_{team_id}"

    # 构造脏状态：有指纹、无 collection/chunks
    insert(doc_hash=doc_hash, team_id=team_id, source="test")
    chroma_client = get_client()
    try:
        chroma_client.delete_collection(name=collection_name)
    except NotFoundError:
        pass

    class FakeEmbeddings:
        def embed_documents(self, docs: list[str]) -> list[list[float]]:
            return [[0.1, 0.2, 0.3] for _ in docs]

    monkeypatch.setattr("app.services.ingestion_service.get_embeddings", lambda: FakeEmbeddings())

    response = client.post(
        "/v1/documents/text",
        json={
            "text": text,
            "metadata": {
                "team_id": team_id,
                "source": "ui_upload",
                "tags": ["test"],
                "security_level": "internal",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["index_status"] == "completed"
    assert data["chunks_created"] > 0

    stats_resp = client.get(f"/v1/documents/stats/{team_id}")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["chunk_count"] > 0

    # cleanup
    delete(doc_hash=doc_hash, team_id=team_id)
    chroma_client = get_client()
    try:
        chroma_client.delete_collection(name=collection_name)
    except NotFoundError:
        pass
