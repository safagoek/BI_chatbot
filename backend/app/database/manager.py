"""
app/database/manager.py

SQLite metadata veritabanı yönetim katmanı.
- Context manager pattern ile bağlantı sızıntısı önlenir.
- WAL modu ile yüksek eş zamanlılık desteklenir.
- Şifre alanları crypto modülü üzerinden şifrelenir.
"""
import os
import sqlite3
import json
import logging
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Testler DEEPBI_METADATA_DB ile izole bir DB'ye yönlendirir (gerçek DB korunur)
DB_PATH = os.environ.get(
    "DEEPBI_METADATA_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "metadata.db"),
)


def _configure_connection(conn: sqlite3.Connection) -> None:
    """Bağlantı optimizasyon ayarlarını uygular."""
    conn.row_factory = sqlite3.Row
    # WAL modu → eş zamanlı okuma/yazma & 10x write hızı
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    # Foreign key desteğini etkinleştir
    conn.execute("PRAGMA foreign_keys=ON;")


def get_db_connection() -> sqlite3.Connection:
    """Ham bağlantı döndürür. Kapatma sorumluluğu çağırana aittir."""
    conn = sqlite3.connect(DB_PATH)
    _configure_connection(conn)
    return conn


@contextmanager
def db_connection():
    """
    Güvenli context manager — bağlantı her durumda kapatılır.

    Kullanım:
        with db_connection() as conn:
            conn.execute(...)
    """
    conn = sqlite3.connect(DB_PATH)
    _configure_connection(conn)
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_metadata_db() -> None:
    """Metadata tablolarını oluşturur / varsa migrate eder."""
    with db_connection() as conn:
        cursor = conn.cursor()

        # ── files ───────────────────────────────────────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id            TEXT PRIMARY KEY,
            alias         TEXT NOT NULL UNIQUE,
            original_name TEXT NOT NULL,
            file_path     TEXT NOT NULL,
            row_count     INTEGER,
            schema_json   TEXT,
            uploaded_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ── sources ─────────────────────────────────────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id                  TEXT PRIMARY KEY,
            type                TEXT NOT NULL,
            display_name        TEXT NOT NULL,
            connection_details  TEXT,
            schema_cache        TEXT,
            last_schema_update  TIMESTAMP,
            labels_json         TEXT DEFAULT '[]',
            is_active           INTEGER DEFAULT 1
        )
        """)

        # Migration: eksik kolonları ekle
        cursor.execute("PRAGMA table_info(sources)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "labels_json" not in existing_cols:
            cursor.execute("ALTER TABLE sources ADD COLUMN labels_json TEXT DEFAULT '[]'")
        if "is_active" not in existing_cols:
            cursor.execute("ALTER TABLE sources ADD COLUMN is_active INTEGER DEFAULT 1")
        cursor.execute("UPDATE sources SET labels_json = '[]' WHERE labels_json IS NULL")
        cursor.execute("UPDATE sources SET is_active = 1 WHERE is_active IS NULL")

        # ── sessions ─────────────────────────────────────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id               TEXT PRIMARY KEY,
            title            TEXT NOT NULL,
            active_source_id TEXT NOT NULL,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Migration: multi-source join kolonları
        cursor.execute("PRAGMA table_info(sessions)")
        existing_session_cols = {row[1] for row in cursor.fetchall()}
        if "selected_sources" not in existing_session_cols:
            cursor.execute("ALTER TABLE sessions ADD COLUMN selected_sources TEXT")
        if "relationships" not in existing_session_cols:
            cursor.execute("ALTER TABLE sessions ADD COLUMN relationships TEXT")

        # ── messages ─────────────────────────────────────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id                    TEXT PRIMARY KEY,
            session_id            TEXT NOT NULL,
            role                  TEXT NOT NULL,
            text                  TEXT,
            status_history        TEXT,
            code                  TEXT,
            code_language         TEXT,
            data_json             TEXT,
            visualization_json    TEXT,
            auto_corrections_json TEXT,
            error                 TEXT,
            created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
        """)

        # Migration: auto_corrections_json kolonu
        cursor.execute("PRAGMA table_info(messages)")
        existing_msg_cols = {row[1] for row in cursor.fetchall()}
        if "auto_corrections_json" not in existing_msg_cols:
            try:
                cursor.execute("ALTER TABLE messages ADD COLUMN auto_corrections_json TEXT")
            except sqlite3.OperationalError:
                pass  # Paralel başlatma durumunda güvenli

        # ── semantic_mappings ────────────────────────────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS semantic_mappings (
            source_id    TEXT PRIMARY KEY,
            mapping_json TEXT NOT NULL
        )
        """)

        # ── rag_memory ───────────────────────────────────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS rag_memory (
            question          TEXT PRIMARY KEY,
            intent            TEXT NOT NULL,
            code              TEXT NOT NULL,
            source_id         TEXT NOT NULL,
            feedback          TEXT DEFAULT 'neutral',
            execution_success INTEGER DEFAULT 1,
            schema_snapshot   TEXT,
            embedding_json    TEXT
        )
        """)

        # ── semantic_cache ───────────────────────────────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS semantic_cache (
            question       TEXT PRIMARY KEY,
            intent         TEXT NOT NULL,
            code           TEXT NOT NULL,
            source_id      TEXT NOT NULL,
            embedding_json TEXT,
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ── settings ─────────────────────────────────────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('deepseek_key', '')")
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('deepseek_url', 'https://api.deepseek.com/v1')"
        )
        cursor.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('deepseek_model', 'deepseek-coder')"
        )

        # ── users (SaaS çok kullanıcılı oturum) ─────────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id                   TEXT PRIMARY KEY,
            username             TEXT NOT NULL UNIQUE,
            password_hash        TEXT NOT NULL,
            display_name         TEXT DEFAULT '',
            role                 TEXT NOT NULL DEFAULT 'user',
            is_active            INTEGER DEFAULT 1,
            must_change_password INTEGER DEFAULT 0,
            created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ── user_source_permissions (kullanıcı bazlı veri kaynağı yetkileri) ─
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_source_permissions (
            user_id   TEXT NOT NULL,
            source_id TEXT NOT NULL,
            PRIMARY KEY (user_id, source_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        # ── audit_log (denetim kayıtları) ──────────────────────────────────
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id      TEXT,
            username     TEXT,
            action       TEXT NOT NULL,
            target       TEXT,
            detail_json  TEXT,
            request_id   TEXT,
            ip           TEXT
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC)")

        # Migration: sessions tablosuna kullanıcı sahipliği
        cursor.execute("PRAGMA table_info(sessions)")
        if "user_id" not in {row[1] for row in cursor.fetchall()}:
            cursor.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")

        conn.commit()
        logger.info("Metadata DB başarıyla başlatıldı: %s", DB_PATH)


# ─────────────────────────────────────────────────────────────────────────────
# Şifreleme Yardımcıları
# ─────────────────────────────────────────────────────────────────────────────

_SENSITIVE_KEYS = ("password", "passwd", "pwd", "secret", "private_key")


def _encrypt_source_details(details: Dict[str, Any]) -> Dict[str, Any]:
    """Şifre alanlarını şifreler; crypto modülü yoksa düz metin saklanır."""
    try:
        from app.core.crypto import encrypt_password
        enc = dict(details)
        for key in _SENSITIVE_KEYS:
            if enc.get(key):
                enc[key] = encrypt_password(enc[key])
        return enc
    except Exception as e:
        logger.warning("Şifre şifrelenemedi, düz metin saklanıyor: %s", e)
        return details


def _decrypt_source_details(details: Dict[str, Any]) -> Dict[str, Any]:
    """Şifrelenmiş alanları çözer; geriye dönük uyumlu (plain text)."""
    try:
        from app.core.crypto import decrypt_password
        dec = dict(details)
        for key in _SENSITIVE_KEYS:
            if dec.get(key):
                dec[key] = decrypt_password(dec[key])
        return dec
    except Exception as e:
        logger.warning("Şifre çözülemedi: %s", e)
        return details


# ─────────────────────────────────────────────────────────────────────────────
# File Uploads
# ─────────────────────────────────────────────────────────────────────────────

def add_uploaded_file(
    file_id: str,
    alias: str,
    original_name: str,
    file_path: str,
    row_count: int,
    schema: Dict[str, str],
) -> Dict[str, Any]:
    schema_json = json.dumps(schema)
    try:
        with db_connection() as conn:
            conn.execute(
                """
                INSERT INTO files (id, alias, original_name, file_path, row_count, schema_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (file_id, alias, original_name, file_path, row_count, schema_json),
            )
            conn.commit()
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Bu takma ada ({alias}) sahip bir dosya zaten mevcut: {e}") from e
    return {
        "id": file_id,
        "alias": alias,
        "original_name": original_name,
        "file_path": file_path,
        "row_count": row_count,
        "schema": schema,
    }


def get_uploaded_files() -> List[Dict[str, Any]]:
    with db_connection() as conn:
        rows = conn.execute("SELECT * FROM files ORDER BY uploaded_at DESC").fetchall()
    return [
        {
            "id": r["id"],
            "alias": r["alias"],
            "original_name": r["original_name"],
            "file_path": r["file_path"],
            "row_count": r["row_count"],
            "schema": json.loads(r["schema_json"]) if r["schema_json"] else {},
            "uploaded_at": r["uploaded_at"],
        }
        for r in rows
    ]


def get_file_by_id(file_id: str) -> Optional[Dict[str, Any]]:
    with db_connection() as conn:
        r = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
    if not r:
        return None
    return {
        "id": r["id"],
        "alias": r["alias"],
        "original_name": r["original_name"],
        "file_path": r["file_path"],
        "row_count": r["row_count"],
        "schema": json.loads(r["schema_json"]) if r["schema_json"] else {},
        "uploaded_at": r["uploaded_at"],
    }


def delete_uploaded_file(file_id: str) -> bool:
    with db_connection() as conn:
        r = conn.execute("SELECT file_path FROM files WHERE id = ?", (file_id,)).fetchone()
        if not r:
            return False
        file_path = r["file_path"]
        conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        conn.commit()

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            logger.warning("Dosya silinemedi (%s): %s", file_path, e)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Data Sources
# ─────────────────────────────────────────────────────────────────────────────

def _row_to_source(r: sqlite3.Row) -> Dict[str, Any]:
    raw_details = json.loads(r["connection_details"]) if r["connection_details"] else {}
    return {
        "id": r["id"],
        "type": r["type"],
        "display_name": r["display_name"],
        "connection_details": _decrypt_source_details(raw_details),
        "schema": json.loads(r["schema_cache"]) if r["schema_cache"] else {},
        "last_schema_update": r["last_schema_update"],
        "labels": json.loads(r["labels_json"]) if r["labels_json"] else [],
        "is_active": bool(r["is_active"]) if r["is_active"] is not None else True,
    }


def add_data_source(
    source_id: str,
    stype: str,
    display_name: str,
    connection_details: Dict[str, Any],
    schema: Dict[str, Any],
    labels: Optional[List[str]] = None,
    is_active: bool = True,
) -> Dict[str, Any]:
    encrypted = _encrypt_source_details(connection_details)
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO sources
                (id, type, display_name, connection_details, schema_cache,
                 last_schema_update, labels_json, is_active)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
            """,
            (
                source_id,
                stype,
                display_name,
                json.dumps(encrypted),
                json.dumps(schema),
                json.dumps(labels or []),
                1 if is_active else 0,
            ),
        )
        conn.commit()
    return {
        "id": source_id,
        "type": stype,
        "display_name": display_name,
        "connection_details": connection_details,
        "schema": schema,
        "labels": labels or [],
        "is_active": is_active,
    }


def get_data_sources() -> List[Dict[str, Any]]:
    with db_connection() as conn:
        rows = conn.execute("SELECT * FROM sources").fetchall()
    return [_row_to_source(r) for r in rows]


def get_data_source_by_id(source_id: str) -> Optional[Dict[str, Any]]:
    with db_connection() as conn:
        r = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
    return _row_to_source(r) if r else None


def update_source_schema(source_id: str, schema: Dict[str, Any]) -> bool:
    with db_connection() as conn:
        cur = conn.execute(
            """
            UPDATE sources
            SET schema_cache = ?, last_schema_update = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(schema), source_id),
        )
        conn.commit()
    return cur.rowcount > 0


def update_data_source(
    source_id: str,
    display_name: str,
    connection_details: Dict[str, Any],
    schema: Dict[str, Any],
    labels: Optional[List[str]] = None,
) -> bool:
    encrypted = _encrypt_source_details(connection_details)
    with db_connection() as conn:
        cur = conn.execute(
            """
            UPDATE sources
            SET display_name = ?,
                connection_details = ?,
                schema_cache = ?,
                last_schema_update = CURRENT_TIMESTAMP,
                labels_json = ?
            WHERE id = ?
            """,
            (
                display_name,
                json.dumps(encrypted),
                json.dumps(schema),
                json.dumps(labels or []),
                source_id,
            ),
        )
        conn.commit()
    return cur.rowcount > 0


def update_source_status(source_id: str, is_active: bool) -> bool:
    with db_connection() as conn:
        cur = conn.execute(
            "UPDATE sources SET is_active = ? WHERE id = ?",
            (1 if is_active else 0, source_id),
        )
        conn.commit()
    return cur.rowcount > 0


def update_source_labels(source_id: str, labels: List[str]) -> bool:
    with db_connection() as conn:
        cur = conn.execute(
            "UPDATE sources SET labels_json = ? WHERE id = ?",
            (json.dumps(labels), source_id),
        )
        conn.commit()
    return cur.rowcount > 0


def delete_data_source(source_id: str) -> bool:
    """Kaynak ve ilişkili tüm verileri siler."""
    with db_connection() as conn:
        cur = conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        conn.commit()
    return cur.rowcount > 0


# ─────────────────────────────────────────────────────────────────────────────
# Sessions & Messages
# ─────────────────────────────────────────────────────────────────────────────

def _row_to_session(r: sqlite3.Row) -> Dict[str, Any]:
    keys = r.keys()
    return {
        "id": r["id"],
        "title": r["title"],
        "active_source_id": r["active_source_id"],
        "created_at": r["created_at"],
        "user_id": r["user_id"] if "user_id" in keys else None,
        "selected_sources": r["selected_sources"] if "selected_sources" in keys else None,
        "relationships": r["relationships"] if "relationships" in keys else None,
    }


def create_session(session_id: str, title: str, active_source_id: str, user_id: str = "") -> Dict[str, Any]:
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO sessions (id, title, active_source_id, user_id) VALUES (?, ?, ?, ?)",
            (session_id, title, active_source_id, user_id),
        )
        conn.commit()
    return {"id": session_id, "title": title, "active_source_id": active_source_id, "user_id": user_id}


def get_sessions(
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    with db_connection() as conn:
        if user_id is not None:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
    return [_row_to_session(r) for r in rows]


def get_session_by_id(session_id: str) -> Optional[Dict[str, Any]]:
    with db_connection() as conn:
        r = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return _row_to_session(r) if r else None


def update_session(
    session_id: str,
    title: Optional[str] = None,
    active_source_id: Optional[str] = None,
    selected_sources: Optional[str] = None,
    relationships: Optional[str] = None,
) -> bool:
    fields: List[str] = []
    params: List[Any] = []

    if title is not None:
        fields.append("title = ?")
        params.append(title)
    if active_source_id is not None:
        fields.append("active_source_id = ?")
        params.append(active_source_id)
    if selected_sources is not None:
        fields.append("selected_sources = ?")
        params.append(selected_sources)
    if relationships is not None:
        fields.append("relationships = ?")
        params.append(relationships)

    if not fields:
        return False

    params.append(session_id)
    sql = f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?"

    with db_connection() as conn:
        cur = conn.execute(sql, tuple(params))
        conn.commit()
    return cur.rowcount > 0


def delete_session(session_id: str) -> bool:
    with db_connection() as conn:
        cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
    return cur.rowcount > 0


def add_chat_message(
    session_id: str,
    message_id: str,
    role: str,
    text: Optional[str] = None,
    status_history: Optional[List[str]] = None,
    code: Optional[str] = None,
    code_language: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    visualization: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    auto_corrections: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    with db_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages
                (id, session_id, role, text, status_history, code, code_language,
                 data_json, visualization_json, auto_corrections_json, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                session_id,
                role,
                text,
                json.dumps(status_history) if status_history is not None else None,
                code,
                code_language,
                json.dumps(data) if data is not None else None,
                json.dumps(visualization) if visualization is not None else None,
                json.dumps(auto_corrections) if auto_corrections is not None else None,
                error,
            ),
        )
        conn.commit()
    return {
        "id": message_id,
        "session_id": session_id,
        "role": role,
        "text": text,
        "status_history": status_history or [],
        "code": code,
        "code_language": code_language,
        "data": data,
        "visualization": visualization,
        "error": error,
        "auto_corrections": auto_corrections,
    }


def get_session_messages(session_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit), 2000))
    with db_connection() as conn:
        # Son `limit` mesaj, kronolojik sırayla döner
        rows = conn.execute(
            "SELECT * FROM (SELECT * FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT ?) ORDER BY created_at ASC",
            (session_id, limit),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "session_id": r["session_id"],
            "role": r["role"],
            "text": r["text"],
            "statusHistory": json.loads(r["status_history"]) if r["status_history"] else [],
            "code": r["code"],
            "codeLanguage": r["code_language"],
            "data": json.loads(r["data_json"]) if r["data_json"] else None,
            "visualization": json.loads(r["visualization_json"]) if r["visualization_json"] else None,
            "error": r["error"],
            "auto_corrections": (
                json.loads(r["auto_corrections_json"]) if r["auto_corrections_json"] else None
            ),
        }
        for r in rows
    ]


def clear_session_chat(session_id: str) -> bool:
    with db_connection() as conn:
        cur = conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()
    return cur.rowcount > 0


# ─────────────────────────────────────────────────────────────────────────────
# Semantic Mappings
# ─────────────────────────────────────────────────────────────────────────────

def get_semantic_mapping(source_id: str) -> Dict[str, Any]:
    with db_connection() as conn:
        row = conn.execute(
            "SELECT mapping_json FROM semantic_mappings WHERE source_id = ?", (source_id,)
        ).fetchone()
    if row:
        try:
            return json.loads(row["mapping_json"])
        except (json.JSONDecodeError, KeyError):
            return {}
    return {}


def save_semantic_mapping(source_id: str, mapping: Dict[str, Any]) -> bool:
    try:
        with db_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO semantic_mappings (source_id, mapping_json) VALUES (?, ?)",
                (source_id, json.dumps(mapping)),
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error("Semantic mapping kaydedilemedi: %s", e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# LLM / Settings
# ─────────────────────────────────────────────────────────────────────────────

_LLM_DEFAULTS: Dict[str, str] = {
    "apiKey": "",
    "baseUrl": "https://api.deepseek.com/v1",
    "model": "deepseek-coder",
}
_LLM_KEY_MAP = {
    "deepseek_key": "apiKey",
    "deepseek_url": "baseUrl",
    "deepseek_model": "model",
}


def get_llm_config() -> Dict[str, str]:
    try:
        with db_connection() as conn:
            rows = conn.execute(
                "SELECT key, value FROM settings WHERE key IN ('deepseek_key', 'deepseek_url', 'deepseek_model')"
            ).fetchall()
        config = dict(_LLM_DEFAULTS)
        for r in rows:
            field = _LLM_KEY_MAP.get(r["key"])
            if field:
                config[field] = r["value"] or config[field]
        return config
    except Exception as e:
        logger.error("LLM config okunamadı: %s", e)
        return dict(_LLM_DEFAULTS)


def get_stored_api_key() -> str:
    """Sadece sunucu içi kullanım için saklanan LLM anahtarını döndürür."""
    try:
        with db_connection() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = 'deepseek_key'"
            ).fetchone()
        return (row["value"] or "") if row else ""
    except Exception as e:
        logger.error("Stored API key okunamadı: %s", e)
        return ""


def update_llm_config(api_key: str, base_url: str, model: str) -> bool:
    try:
        with db_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('deepseek_key', ?)", (api_key,)
            )
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('deepseek_url', ?)", (base_url,)
            )
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('deepseek_model', ?)", (model,)
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error("LLM config güncellenemedi: %s", e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Users & Permissions (SaaS çok kullanıcılı katman)
# ─────────────────────────────────────────────────────────────────────────────

def seed_main_admin() -> Optional[Dict[str, Any]]:
    """Kullanıcı yoksa main admin oluşturur. İlk şifre env ADMIN_INITIAL_PASSWORD
    ile verilebilir; aksi halde 'admin123' atanır ve şifre değiştirme zorunlu tutulur."""
    with db_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        if row[0] > 0:
            return None
        import uuid
        import os as _os
        initial_password = _os.getenv("ADMIN_INITIAL_PASSWORD", "admin123")
        from app.core.auth import hash_password
        admin = {
            "id": f"user-{uuid.uuid4().hex[:12]}",
            "username": "admin",
            "password_hash": hash_password(initial_password),
            "display_name": "Main Admin",
            "role": "admin",
            "is_active": 1,
            "must_change_password": 0 if initial_password != "admin123" else 1,
        }
        conn.execute(
            """INSERT INTO users (id, username, password_hash, display_name, role, is_active, must_change_password)
               VALUES (:id, :username, :password_hash, :display_name, :role, :is_active, :must_change_password)""",
            admin,
        )
        conn.commit()
        logger.warning(
            "Main admin oluşturuldu: kullanici='admin', ilk sifre='%s' — ilk girişte değiştirilmeli.",
            initial_password,
        )
        return admin


def create_user(username: str, password_hash: str, display_name: str = "", role: str = "user") -> Dict[str, Any]:
    import uuid
    user_id = f"user-{uuid.uuid4().hex[:12]}"
    with db_connection() as conn:
        conn.execute(
            """INSERT INTO users (id, username, password_hash, display_name, role, is_active, must_change_password)
               VALUES (?, ?, ?, ?, ?, 1, 1)""",
            (user_id, username, password_hash, display_name, role),
        )
        conn.commit()
    return get_user_by_id(user_id)


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        r = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(r) if r else None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        r = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(r) if r else None


def list_users() -> List[Dict[str, Any]]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, username, display_name, role, is_active, must_change_password, created_at FROM users ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def update_user(
    user_id: str,
    password_hash: Optional[str] = None,
    display_name: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    must_change_password: Optional[bool] = None,
) -> bool:
    fields: List[str] = []
    params: List[Any] = []
    if password_hash is not None:
        fields.append("password_hash = ?")
        params.append(password_hash)
        fields.append("must_change_password = 0")
    if display_name is not None:
        fields.append("display_name = ?")
        params.append(display_name)
    if role is not None:
        fields.append("role = ?")
        params.append(role)
    if is_active is not None:
        fields.append("is_active = ?")
        params.append(1 if is_active else 0)
    if must_change_password is not None:
        fields.append("must_change_password = ?")
        params.append(1 if must_change_password else 0)
    if not fields:
        return False
    params.append(user_id)
    with db_connection() as conn:
        cur = conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
    return cur.rowcount > 0


def delete_user(user_id: str) -> bool:
    with db_connection() as conn:
        cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    return cur.rowcount > 0


def count_active_admins() -> int:
    with db_connection() as conn:
        row = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1").fetchone()
    return row[0]


def replace_user_permissions(user_id: str, source_ids: List[str]) -> None:
    with db_connection() as conn:
        conn.execute("DELETE FROM user_source_permissions WHERE user_id = ?", (user_id,))
        for sid in source_ids:
            conn.execute(
                "INSERT OR IGNORE INTO user_source_permissions (user_id, source_id) VALUES (?, ?)",
                (user_id, sid),
            )
        conn.commit()


def get_user_permissions(user_id: str) -> List[str]:
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT source_id FROM user_source_permissions WHERE user_id = ?", (user_id,)
        ).fetchall()
    return [r[0] for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# Saved Analyses & Scheduled Reports
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_feature_tables() -> None:
    """Kayıtlı analizler ve zamanlanmış raporlar tabloları (idempotent)."""
    with db_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS saved_analyses (
            id                 TEXT PRIMARY KEY,
            user_id            TEXT NOT NULL,
            title              TEXT NOT NULL,
            question           TEXT NOT NULL,
            source_ids_json    TEXT,
            relationships_json TEXT,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_reports (
            id                 TEXT PRIMARY KEY,
            user_id            TEXT NOT NULL,
            title              TEXT NOT NULL,
            question           TEXT NOT NULL,
            source_ids_json    TEXT,
            relationships_json TEXT,
            frequency          TEXT NOT NULL DEFAULT 'daily',
            hour               INTEGER NOT NULL DEFAULT 9,
            day_of_week        INTEGER NOT NULL DEFAULT 1,
            email              TEXT DEFAULT '',
            active             INTEGER DEFAULT 1,
            last_run_at        TIMESTAMP,
            last_status        TEXT,
            created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()


def list_saved_analyses(user_id: str) -> List[Dict[str, Any]]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM saved_analyses WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def create_saved_analysis(user_id: str, title: str, question: str,
                          source_ids_json: Optional[str], relationships_json: Optional[str]) -> Dict[str, Any]:
    import uuid
    row_id = f"save-{uuid.uuid4().hex[:10]}"
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO saved_analyses (id, user_id, title, question, source_ids_json, relationships_json) VALUES (?, ?, ?, ?, ?, ?)",
            (row_id, user_id, title, question, source_ids_json, relationships_json),
        )
        conn.commit()
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        r = conn.execute("SELECT * FROM saved_analyses WHERE id = ?", (row_id,)).fetchone()
    return dict(r) if r else {}


def delete_saved_analysis(user_id: str, analysis_id: str) -> bool:
    with db_connection() as conn:
        cur = conn.execute("DELETE FROM saved_analyses WHERE id = ? AND user_id = ?", (analysis_id, user_id))
        conn.commit()
    return cur.rowcount > 0


def list_scheduled_reports(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        if user_id is not None:
            rows = conn.execute(
                "SELECT * FROM scheduled_reports WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM scheduled_reports ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_scheduled_report(report_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    with db_connection() as conn:
        conn.row_factory = sqlite3.Row
        r = conn.execute(
            "SELECT * FROM scheduled_reports WHERE id = ? AND user_id = ?", (report_id, user_id)
        ).fetchone()
    return dict(r) if r else {}


def create_scheduled_report(user_id: str, title: str, question: str, source_ids_json: Optional[str],
                            relationships_json: Optional[str], frequency: str = "daily",
                            hour: int = 9, day_of_week: int = 1, email: str = "") -> Dict[str, Any]:
    import uuid
    row_id = f"sched-{uuid.uuid4().hex[:10]}"
    with db_connection() as conn:
        conn.execute(
            """INSERT INTO scheduled_reports
               (id, user_id, title, question, source_ids_json, relationships_json, frequency, hour, day_of_week, email)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (row_id, user_id, title, question, source_ids_json, relationships_json,
             frequency, hour, day_of_week, email),
        )
        conn.commit()
    return get_scheduled_report(row_id, user_id)


def update_scheduled_report(user_id: str, report_id: str, **fields) -> bool:
    allowed = {"title", "question", "source_ids_json", "relationships_json", "frequency",
               "hour", "day_of_week", "email", "active"}
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed and v is not None:
            sets.append(f"{k} = ?")
            params.append(int(v) if isinstance(v, bool) else v)
    if not sets:
        return False
    params += [report_id, user_id]
    with db_connection() as conn:
        cur = conn.execute(f"UPDATE scheduled_reports SET {', '.join(sets)} WHERE id = ? AND user_id = ?", params)
        conn.commit()
    return cur.rowcount > 0


def delete_scheduled_report(user_id: str, report_id: str) -> bool:
    with db_connection() as conn:
        cur = conn.execute("DELETE FROM scheduled_reports WHERE id = ? AND user_id = ?", (report_id, user_id))
        conn.commit()
    return cur.rowcount > 0


def get_due_scheduled_reports(now_hour: int, now_weekday: int, today: str) -> List[Dict[str, Any]]:
    """active + saat/uç günü eşleşen + bugün henüz koşmamış raporlar."""
    rows = list_scheduled_reports(user_id=None)
    due = []
    for r in rows:
        if not r.get("active"):
            continue
        if r["frequency"] not in ("daily", "weekly"):
            continue
        if int(r["hour"]) != now_hour:
            continue
        if r["frequency"] == "weekly" and int(r["day_of_week"]) != now_weekday:
            continue
        if (r.get("last_run_at") or "")[:10] >= today:
            continue
        due.append(r)
    return due


def mark_scheduled_run(report_id: str, status: str) -> None:
    from datetime import datetime as _dt
    with db_connection() as conn:
        conn.execute(
            "UPDATE scheduled_reports SET last_run_at = ?, last_status = ? WHERE id = ?",
            (_dt.now().isoformat(timespec="seconds"), status[:64], report_id),
        )
        conn.commit()
