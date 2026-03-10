from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_document_stats_api_returns_counts():
    team_id = "team_test_stats"
    response = client.get(f"/v1/documents/stats/{team_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["team_id"] == team_id
    assert isinstance(data["document_count"], int)
    assert data["document_count"] >= 0
    assert isinstance(data["chunk_count"], int)
    assert data["chunk_count"] >= 0
    assert data["collection_name"] == f"team_{team_id}"

