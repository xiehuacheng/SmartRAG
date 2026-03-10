from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_query_normal(monkeypatch):
    def fake_retrieve(query: str, team_id: str, top_k: int, retrieval_mode: str):
        return [
            {
                "document_id": "doc_1",
                "chunk_id": "doc_1_0",
                "content": "SmartRAG 是一个用于企业知识库问答的系统。",
                "source": "unit_test",
                "distance": 0.25,
                "score": 0.8,
            },
            {
                "document_id": "doc_2",
                "chunk_id": "doc_2_0",
                "content": "系统支持 chunks 和 confidence。",
                "source": "unit_test",
                "distance": 0.5,
                "score": 0.66,
            },
        ]

    monkeypatch.setattr("app.services.query_service.retrieve", fake_retrieve)

    payload = {
        "query": "测试文档内容",
        "team_id": "team_test",
        "top_k": 3
    }
    response = client.post("/v1/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["answer"] is None
    assert "chunks" in data
    assert "confidence" in data
    assert len(data["chunks"]) == 2
    assert data["chunks"][0]["chunk_id"] == "doc_1_0"
    assert 0.0 <= data["confidence"] <= 1.0


def test_query_no_docs(monkeypatch):
    def fake_retrieve(query: str, team_id: str, top_k: int, retrieval_mode: str):
        return []

    monkeypatch.setattr("app.services.query_service.retrieve", fake_retrieve)

    payload = {
        "query": "不存在的问题",
        "team_id": "team_empty",
        "top_k": 3
    }
    response = client.post("/v1/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] is None
    assert data["chunks"] == []
    assert data["confidence"] == 0.0


def test_query_chunks_from_retrieval(monkeypatch):
    def fake_retrieve(query: str, team_id: str, top_k: int, retrieval_mode: str):
        return [
            {
                "document_id": "doc_3",
                "chunk_id": "doc_3_0",
                "content": "这是用于测试中文括号引用提取的证据。",
                "source": "unit_test",
                "distance": 0.2,
                "score": 0.83,
            }
        ]

    monkeypatch.setattr("app.services.query_service.retrieve", fake_retrieve)

    payload = {
        "query": "测试 chunks 是否来自检索结果",
        "team_id": "team_test",
        "top_k": 3,
    }
    response = client.post("/v1/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["chunks"]) == 1
    assert data["chunks"][0]["chunk_id"] == "doc_3_0"


def test_query_invalid_team():
    payload = {
        "query": "测试",
        "team_id": "",
        "top_k": 3
    }
    response = client.post("/v1/query", json=payload)
    assert response.status_code == 422  # Pydantic 验证失败


def test_query_mode_forward(monkeypatch):
        captured = {}

        def fake_retrieve(query: str, team_id: str, top_k: int, retrieval_mode: str):
            captured["mode"] = retrieval_mode
            return [{
                "document_id": "doc_1",
                "chunk_id": "doc_1_0",
                "content": "mode forward test",
                "source": "unit_test",
                "distance": 0.2,
                "score": 0.83,
            }]

        monkeypatch.setattr("app.services.query_service.retrieve", fake_retrieve)

        payload = {"query": "测试", "team_id": "team_test", "top_k": 3, "retrieval_mode": "hybrid"}
        resp = client.post("/v1/query", json=payload)
        assert resp.status_code == 200
        assert captured["mode"] == "hybrid"


def test_query_invalid_retrieval_mode():
    payload = {"query": "测试", "team_id": "team_test", "top_k": 3, "retrieval_mode": "bad_mode"}
    resp = client.post("/v1/query", json=payload)
    assert resp.status_code == 422
