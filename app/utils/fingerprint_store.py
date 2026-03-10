import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/fingerprints.db")


def _create_documents_table(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_hash TEXT NOT NULL,
            team_id TEXT NOT NULL,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(team_id, doc_hash)
        )
        """
    )


def _migrate_legacy_schema(cursor) -> None:
    cursor.execute("PRAGMA table_info(documents)")
    cols = cursor.fetchall()
    if not cols:
        _create_documents_table(cursor)
        return

    col_names = {row[1] for row in cols}
    has_id = "id" in col_names
    if has_id:
        return

    backup_name = f"documents_legacy_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    cursor.execute(f"ALTER TABLE documents RENAME TO {backup_name}")
    _create_documents_table(cursor)
    cursor.execute(
        f"""
        INSERT OR IGNORE INTO documents (doc_hash, team_id, source, created_at)
        SELECT
            doc_hash,
            COALESCE(NULLIF(team_id, ''), '__unknown__') AS team_id,
            source,
            COALESCE(created_at, CURRENT_TIMESTAMP) AS created_at
        FROM {backup_name}
        """
    )
    cursor.execute(f"DROP TABLE {backup_name}")


def init_db():
    if not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    _create_documents_table(cursor)
    _migrate_legacy_schema(cursor)
    conn.commit()
    conn.close()


def exists(doc_hash: str, team_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM documents WHERE doc_hash=? AND team_id=?",
        (doc_hash, team_id),
    )
    result = cursor.fetchone()
    conn.close()
    return result is not None


def insert(doc_hash: str, team_id: str, source: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO documents (doc_hash, team_id, source) VALUES (?, ?, ?)",
        (doc_hash, team_id, source)
    )
    conn.commit()
    conn.close()
    

def delete(doc_hash: str, team_id: str | None = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if team_id:
        cursor.execute("DELETE FROM documents WHERE doc_hash=? AND team_id=?", (doc_hash, team_id))
    else:
        cursor.execute("DELETE FROM documents WHERE doc_hash=?", (doc_hash,))
    conn.commit()
    conn.close()


def count_by_team(team_id: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM documents WHERE team_id=?", (team_id,))
    row = cursor.fetchone()
    conn.close()
    return int(row[0] or 0) if row else 0
