import pytest
from fastapi.testclient import TestClient

from app.main import app
from scripts.remove_test_data import remove_test_data

client = TestClient(app)
TEST_TEAM_ID = "team_integration_test"

def test_ingest_minimal():
    remove_test_data()
    # 准备测试 payload
    payload = {
        "file_path": "tests/integration/sample.txt",  # 先放一个小文件
        "metadata": {
            "team_id": TEST_TEAM_ID,
            "source": "unit_test",
            "tags": ["test"],
            "security_level": "public"
        }
    }

    response = client.post("/v1/documents/ingest", json=payload)
    assert response.status_code == 200
    data = response.json()
    # 断言返回结构中包含必要字段
    assert "document_id" in data
    assert "chunks_created" in data
    assert "index_status" in data
    remove_test_data()
