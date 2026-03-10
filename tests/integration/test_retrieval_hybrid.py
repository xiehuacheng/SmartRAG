import pytest

from app.services import retrieval_service as rs


class DummyCollection:
    pass


class FakeClient:
    def __init__(self):
        self.created_names: list[str] = []

    def get_or_create_collection(self, name: str):
        self.created_names.append(name)
        return DummyCollection()


def _mk_chunk(cid: str, score: float = 0.8) -> dict:
    return {
        "document_id": "doc_1",
        "chunk_id": cid,
        "content": f"content-{cid}",
        "source": "unit_test",
        "distance": 0.25,
        "score": score,
    }


def test_retrieve_vector_mode(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr(rs, "get_client", lambda: fake_client)
    monkeypatch.setattr(rs, "_vector_retrieve", lambda collection, query, top_k: [_mk_chunk("c1", 0.9)])

    out = rs.retrieve("q", "team_a", top_k=2, retrieval_mode="vector")
    assert len(out) == 1
    assert out[0]["chunk_id"] == "c1"
    assert fake_client.created_names == ["team_team_a"]


def test_retrieve_hybrid_mode(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr(rs, "get_client", lambda: fake_client)
    monkeypatch.setattr(rs, "_vector_retrieve", lambda collection, query, top_k: [_mk_chunk("v1", 0.9), _mk_chunk("v2", 0.7)])
    monkeypatch.setattr(rs, "_bm25_candidates_paged", lambda collection, page_size=200, max_items=5000: [_mk_chunk("b1", 0.0)])
    monkeypatch.setattr(rs, "bm25_retrieve", lambda query, chunks, top_k: [{"chunk_id": "b1", "document_id": "doc_1", "content": "bm25", "source": "unit_test", "bm25_norm_score": 1.0}])
    monkeypatch.setattr(
        rs,
        "rrf_fuse",
        lambda vector_hits, bm25_hits, top_k: [
            {"document_id": "doc_1", "chunk_id": "f1", "content": "fused-1", "source": "unit_test", "fused_score": 0.8},
            {"document_id": "doc_1", "chunk_id": "f2", "content": "fused-2", "source": "unit_test", "fused_score": 0.5},
        ],
    )

    out = rs.retrieve("q", "team_a", top_k=2, retrieval_mode="hybrid")
    assert [x["chunk_id"] for x in out] == ["f1", "f2"]
    assert out[0]["score"] == pytest.approx(0.8)
    assert fake_client.created_names == ["team_team_a"]


def test_retrieve_hybrid_rerank_mode(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr(rs, "get_client", lambda: fake_client)
    monkeypatch.setattr(rs, "_vector_retrieve", lambda collection, query, top_k: [_mk_chunk("v1", 0.9)])
    monkeypatch.setattr(rs, "_bm25_candidates_paged", lambda collection, page_size=200, max_items=5000: [_mk_chunk("b1", 0.0)])
    monkeypatch.setattr(rs, "bm25_retrieve", lambda query, chunks, top_k: [{"chunk_id": "b1", "document_id": "doc_1", "content": "bm25", "source": "unit_test", "bm25_norm_score": 1.0}])
    monkeypatch.setattr(
        rs,
        "rrf_fuse",
        lambda vector_hits, bm25_hits, top_k: [
            {"document_id": "doc_1", "chunk_id": "f1", "content": "fused-1", "source": "unit_test", "fused_score": 0.3},
            {"document_id": "doc_1", "chunk_id": "f2", "content": "fused-2", "source": "unit_test", "fused_score": 0.2},
        ],
    )
    monkeypatch.setattr(
        rs,
        "rerank",
        lambda query, candidates, top_n: [
            {"document_id": "doc_1", "chunk_id": "f2", "content": "fused-2", "source": "unit_test", "rerank_score": 0.9},
            {"document_id": "doc_1", "chunk_id": "f1", "content": "fused-1", "source": "unit_test", "rerank_score": 0.4},
        ],
    )

    out = rs.retrieve("q", "team_a", top_k=2, retrieval_mode="hybrid_rerank")
    assert [x["chunk_id"] for x in out] == ["f2", "f1"]
    assert out[0]["score"] == pytest.approx(0.9)
    assert fake_client.created_names == ["team_team_a"]


def test_retrieve_invalid_mode(monkeypatch):
    fake_client = FakeClient()
    monkeypatch.setattr(rs, "get_client", lambda: fake_client)

    with pytest.raises(ValueError):
        rs.retrieve("q", "team_a", top_k=2, retrieval_mode="unknown_mode")


@pytest.mark.parametrize("mode", ["vector", "hybrid", "hybrid_rerank"])
def test_team_isolation_in_all_modes(monkeypatch, mode):
    fake_client = FakeClient()
    monkeypatch.setattr(rs, "get_client", lambda: fake_client)
    monkeypatch.setattr(rs, "_vector_retrieve", lambda collection, query, top_k: [_mk_chunk("x1", 0.9)])
    monkeypatch.setattr(rs, "_bm25_candidates_paged", lambda collection, page_size=200, max_items=5000: [_mk_chunk("x2", 0.0)])
    monkeypatch.setattr(rs, "bm25_retrieve", lambda query, chunks, top_k: [{"chunk_id": "x2", "document_id": "doc_1", "content": "bm25", "source": "unit_test", "bm25_norm_score": 1.0}])
    monkeypatch.setattr(rs, "rrf_fuse", lambda vector_hits, bm25_hits, top_k: [{"document_id": "doc_1", "chunk_id": "x3", "content": "fused", "source": "unit_test", "fused_score": 0.7}])
    monkeypatch.setattr(rs, "rerank", lambda query, candidates, top_n: [{"document_id": "doc_1", "chunk_id": "x4", "content": "reranked", "source": "unit_test", "rerank_score": 0.8}])

    rs.retrieve("q1", "team_alpha", top_k=1, retrieval_mode=mode)
    rs.retrieve("q2", "team_beta", top_k=1, retrieval_mode=mode)

    assert "team_team_alpha" in fake_client.created_names
    assert "team_team_beta" in fake_client.created_names