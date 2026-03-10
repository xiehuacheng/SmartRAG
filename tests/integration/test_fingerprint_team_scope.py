import sqlite3
from pathlib import Path

from app.utils import fingerprint_store as fs


def test_team_scoped_dedup_and_legacy_migration(monkeypatch, tmp_path):
    db_path = tmp_path / "fingerprints.db"
    monkeypatch.setattr(fs, "DB_PATH", db_path)

    # 构造旧版 schema（doc_hash 全局主键）
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE documents (
            doc_hash TEXT PRIMARY KEY,
            team_id TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        "INSERT INTO documents (doc_hash, team_id, source) VALUES (?, ?, ?)",
        ("hash_same", "team_a", "official_docs"),
    )
    conn.commit()
    conn.close()

    # 触发迁移到新 schema（UNIQUE(team_id, doc_hash)）
    fs.init_db()

    assert fs.exists("hash_same", "team_a") is True
    assert fs.exists("hash_same", "team_b") is False

    # 同一 doc_hash 可在不同 team 共存
    fs.insert("hash_same", "team_b", "official_docs")
    assert fs.exists("hash_same", "team_b") is True
    assert fs.count_by_team("team_a") == 1
    assert fs.count_by_team("team_b") == 1

