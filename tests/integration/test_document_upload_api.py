import base64
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_upload_endpoint_accepts_multiple_files(monkeypatch):
    class FakeResp:
        document_id = "doc_x"
        doc_hash = "doc_x"
        chunks_created = 2
        embedding_model = "test-model"
        index_status = "completed"

    def fake_ingest(file_path: str, metadata):
        assert metadata.team_id == "team_upload"
        return FakeResp()

    monkeypatch.setattr("app.api.v1.endpoints.documents.ingestion_service.ingest", fake_ingest)

    payload = {
        "team_id": "team_upload",
        "source": "test_upload",
        "tags": ["a", "b"],
        "security_level": "internal",
        "files": [
            {
                "filename": "a.txt",
                "content_base64": base64.b64encode(b"hello a").decode("utf-8"),
                "content_type": "text/plain",
            },
            {
                "filename": "b.md",
                "content_base64": base64.b64encode(b"# hello b").decode("utf-8"),
                "content_type": "text/markdown",
            },
        ],
    }
    response = client.post("/v1/documents/upload", json=payload)
    assert response.status_code == 200
    payload = response.json()
    assert payload["completed"] == 2
    assert payload["failed"] == 0
    assert len(payload["items"]) == 2


def test_text_endpoint_ingests_text(monkeypatch):
    class FakeResp:
        document_id = "doc_t"
        doc_hash = "doc_t"
        chunks_created = 1
        embedding_model = "test-model"
        index_status = "completed"
        ingestion_time = datetime(2026, 3, 10, 0, 0, 0)

    def fake_ingest_text(text: str, metadata):
        assert text == "hello text"
        assert metadata.team_id == "team_text"
        return FakeResp()

    monkeypatch.setattr("app.api.v1.endpoints.documents.ingestion_service.ingest_text", fake_ingest_text)

    response = client.post(
        "/v1/documents/text",
        json={
            "text": "hello text",
            "title": "sample",
            "metadata": {
                "team_id": "team_text",
                "source": "text_source",
                "tags": ["x"],
                "security_level": "internal",
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == "doc_t"
    assert payload["chunks_created"] == 1
    assert payload["index_status"] == "completed"
