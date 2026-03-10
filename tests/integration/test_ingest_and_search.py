import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.retrieval.vector_store.chroma_client import get_client
from app.retrieval.embedding.embedding_factory import get_embeddings 
from scripts.remove_test_data import remove_test_data

client = TestClient(app)
TEST_TEAM_ID = "team_integration_test"

def test_ingest_and_search():
    remove_test_data()
    # -----------------------------
    # 第一次入库
    # -----------------------------
    payload = {
        "file_path": "tests/integration/sample.txt",
        "metadata": {
            "team_id": TEST_TEAM_ID,
            "source": "integration_test",
            "tags": ["test"],
            "security_level": "public"
        }
    }
    response = client.post("/v1/documents/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    document_id = data["document_id"]
    chunks_created = data["chunks_created"]
    assert data["index_status"] == "completed"
    assert chunks_created > 0

    # -----------------------------
    # 检索 Chroma
    # -----------------------------
    chroma_client = get_client()
    collection_name = f"team_{TEST_TEAM_ID}"
    collection = chroma_client.get_or_create_collection(name=collection_name)

    embedding_model = get_embeddings()

    query = "测试文档"
    query_vector = embedding_model.embed_query(query)

    results = collection.query(
        query_texts=None,
        query_embeddings=[query_vector],
        n_results=1
    )
    
    # 确认检索结果包含文档内容
    assert len(results["documents"][0]) > 0
    found = any(query in doc for doc in results["documents"][0])
    assert found

    # -----------------------------
    # 重复入库 → chunks_created=0
    # -----------------------------
    response2 = client.post("/v1/documents/ingest", json=payload)
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["chunks_created"] == 0
    assert data2["index_status"] == "duplicate"
    
    # 清除对应数据库记录，保证可以重复测试
    remove_test_data()
