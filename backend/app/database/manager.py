import os
import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "metadata.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high concurrency & 10x write speed
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def init_metadata_db():
    """Initializes metadata tables for files and database connections."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create uploaded files table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id TEXT PRIMARY KEY,
        alias TEXT NOT NULL UNIQUE,
        original_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        row_count INTEGER,
        schema_json TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create DB connections table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sources (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL, -- sqlite, postgresql, mysql, mssql
        display_name TEXT NOT NULL,
        connection_details TEXT, -- JSON string
        schema_cache TEXT, -- JSON string
        last_schema_update TIMESTAMP,
        labels_json TEXT,
        is_active INTEGER
    )
    """)

    cursor.execute("PRAGMA table_info(sources)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if "labels_json" not in existing_cols:
        cursor.execute("ALTER TABLE sources ADD COLUMN labels_json TEXT DEFAULT '[]'")
    if "is_active" not in existing_cols:
        cursor.execute("ALTER TABLE sources ADD COLUMN is_active INTEGER DEFAULT 1")
    cursor.execute("UPDATE sources SET labels_json = '[]' WHERE labels_json IS NULL")
    cursor.execute("UPDATE sources SET is_active = 1 WHERE is_active IS NULL")
    
    # Create chat sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        active_source_id TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Session table migration for multi-source joins persistence
    cursor.execute("PRAGMA table_info(sessions)")
    existing_session_cols = {row[1] for row in cursor.fetchall()}
    if "selected_sources" not in existing_session_cols:
        cursor.execute("ALTER TABLE sessions ADD COLUMN selected_sources TEXT")
    if "relationships" not in existing_session_cols:
        cursor.execute("ALTER TABLE sessions ADD COLUMN relationships TEXT")
    
    # Create chat messages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL, -- 'user' | 'agent'
        text TEXT,
        status_history TEXT, -- JSON string list of thinking steps
        code TEXT,
        code_language TEXT,
        data_json TEXT, -- JSON string Dict/list of data frames
        visualization_json TEXT, -- JSON string Plotly Dict
        auto_corrections_json TEXT,
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    )
    """)

    # Ensure legacy DBs have the auto_corrections_json column
    cursor.execute("PRAGMA table_info(messages)")
    existing_msg_cols = {row[1] for row in cursor.fetchall()}
    if "auto_corrections_json" not in existing_msg_cols:
        try:
            cursor.execute("ALTER TABLE messages ADD COLUMN auto_corrections_json TEXT")
        except Exception:
            pass
    
    # Create semantic mappings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS semantic_mappings (
        source_id TEXT PRIMARY KEY,
        mapping_json TEXT NOT NULL
    )
    """)

    # Create RAG memory table for secure vector & few-shot query cache
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rag_memory (
        question TEXT PRIMARY KEY,
        intent TEXT NOT NULL,
        code TEXT NOT NULL,
        source_id TEXT NOT NULL,
        feedback TEXT DEFAULT 'neutral',
        execution_success INTEGER DEFAULT 1,
        schema_snapshot TEXT, -- JSON string
        embedding_json TEXT   -- Vector array JSON string
    )
    """)

    # Create semantic cache table for caching LLM responses
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS semantic_cache (
        question TEXT PRIMARY KEY,
        intent TEXT NOT NULL,
        code TEXT NOT NULL,
        source_id TEXT NOT NULL,
        embedding_json TEXT,  -- Vector array JSON string
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Create settings table for calculation engine / LLM configuration
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    # Insert default settings
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('deepseek_key', '')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('deepseek_url', 'https://api.deepseek.com/v1')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('deepseek_model', 'deepseek-coder')")
    
    conn.commit()
    conn.close()


# Operations for File Uploads
def add_uploaded_file(file_id: str, alias: str, original_name: str, file_path: str, row_count: int, schema: Dict[str, str]) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    schema_json = json.dumps(schema)
    try:
        cursor.execute("""
        INSERT INTO files (id, alias, original_name, file_path, row_count, schema_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (file_id, alias, original_name, file_path, row_count, schema_json))
        conn.commit()
        return {
            "id": file_id,
            "alias": alias,
            "original_name": original_name,
            "file_path": file_path,
            "row_count": row_count,
            "schema": schema
        }
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Bu takma ada ({alias}) sahip bir dosya zaten mevcut: {str(e)}")
    finally:
        conn.close()

def get_uploaded_files() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files ORDER BY uploaded_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    files = []
    for r in rows:
        files.append({
            "id": r["id"],
            "alias": r["alias"],
            "original_name": r["original_name"],
            "file_path": r["file_path"],
            "row_count": r["row_count"],
            "schema": json.loads(r["schema_json"]) if r["schema_json"] else {},
            "uploaded_at": r["uploaded_at"]
        })
    return files

def get_file_by_id(file_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    r = cursor.fetchone()
    conn.close()
    if r:
        return {
            "id": r["id"],
            "alias": r["alias"],
            "original_name": r["original_name"],
            "file_path": r["file_path"],
            "row_count": r["row_count"],
            "schema": json.loads(r["schema_json"]) if r["schema_json"] else {},
            "uploaded_at": r["uploaded_at"]
        }
    return None

def delete_uploaded_file(file_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM files WHERE id = ?", (file_id,))
    r = cursor.fetchone()
    if not r:
        conn.close()
        return False
        
    file_path = r["file_path"]
    cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()
    
    # Try deleting file on disk
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass
    return True

def _encrypt_source_details(details: Dict[str, Any]) -> Dict[str, Any]:
    """Şifre alanlarını şifreler, şifrelenmiş kopyayı döndürür."""
    try:
        from app.core.crypto import encrypt_password
        enc = dict(details)
        for key in ("password", "passwd", "pwd", "secret", "private_key"):
            if enc.get(key):
                enc[key] = encrypt_password(enc[key])
        return enc
    except Exception as _e:
        logger.warning(f"Şifre şifrelenemedi, düz metin saklanıyor: {_e}")
        return details


def _decrypt_source_details(details: Dict[str, Any]) -> Dict[str, Any]:
    """Şifrelenmiş alanları çözer, geriye dönük uyumlu."""
    try:
        from app.core.crypto import decrypt_password
        dec = dict(details)
        for key in ("password", "passwd", "pwd", "secret", "private_key"):
            if dec.get(key):
                dec[key] = decrypt_password(dec[key])
        return dec
    except Exception as _e:
        logger.warning(f"Şifre çözülemedi: {_e}")
        return details


# Operations for Data Sources
def add_data_source(
    source_id: str,
    stype: str,
    display_name: str,
    connection_details: Dict[str, Any],
    schema: Dict[str, Any],
    labels: Optional[List[str]] = None,
    is_active: bool = True
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    encrypted_details = _encrypt_source_details(connection_details)
    details_str = json.dumps(encrypted_details)
    schema_str = json.dumps(schema)
    labels_str = json.dumps(labels or [])
    try:
        cursor.execute("""
        INSERT INTO sources (id, type, display_name, connection_details, schema_cache, last_schema_update, labels_json, is_active)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)
        """, (source_id, stype, display_name, details_str, schema_str, labels_str, 1 if is_active else 0))
        conn.commit()
        return {
            "id": source_id,
            "type": stype,
            "display_name": display_name,
            "connection_details": connection_details,  # Çözülmüş (plain) olarak döndür
            "schema": schema,
            "labels": labels or [],
            "is_active": is_active
        }
    finally:
        conn.close()

def get_data_sources() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sources")
    rows = cursor.fetchall()
    conn.close()
    
    sources = []
    for r in rows:
        raw_details = json.loads(r["connection_details"]) if r["connection_details"] else {}
        sources.append({
            "id": r["id"],
            "type": r["type"],
            "display_name": r["display_name"],
            "connection_details": _decrypt_source_details(raw_details),
            "schema": json.loads(r["schema_cache"]) if r["schema_cache"] else {},
            "last_schema_update": r["last_schema_update"],
            "labels": json.loads(r["labels_json"]) if r["labels_json"] else [],
            "is_active": bool(r["is_active"]) if r["is_active"] is not None else True
        })
    return sources

def get_data_source_by_id(source_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sources WHERE id = ?", (source_id,))
    r = cursor.fetchone()
    conn.close()
    if not r:
        return None
    raw_details = json.loads(r["connection_details"]) if r["connection_details"] else {}
    return {
        "id": r["id"],
        "type": r["type"],
        "display_name": r["display_name"],
        "connection_details": _decrypt_source_details(raw_details),
        "schema": json.loads(r["schema_cache"]) if r["schema_cache"] else {},
        "last_schema_update": r["last_schema_update"],
        "labels": json.loads(r["labels_json"]) if r["labels_json"] else [],
        "is_active": bool(r["is_active"]) if r["is_active"] is not None else True
    }

def update_source_schema(source_id: str, schema: Dict[str, Any]) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    schema_str = json.dumps(schema)
    cursor.execute("""
    UPDATE sources 
    SET schema_cache = ?, last_schema_update = CURRENT_TIMESTAMP
    WHERE id = ?
    """, (schema_str, source_id))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0


def update_data_source(
    source_id: str,
    display_name: str,
    connection_details: Dict[str, Any],
    schema: Dict[str, Any],
    labels: Optional[List[str]] = None
) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    encrypted_details = _encrypt_source_details(connection_details)
    details_str = json.dumps(encrypted_details)
    schema_str = json.dumps(schema)
    labels_str = json.dumps(labels or [])
    try:
        cursor.execute("""
        UPDATE sources
        SET display_name = ?, connection_details = ?, schema_cache = ?, last_schema_update = CURRENT_TIMESTAMP, labels_json = ?
        WHERE id = ?
        """, (display_name, details_str, schema_str, labels_str, source_id))
        affected = cursor.rowcount
        conn.commit()
        return affected > 0
    finally:
        conn.close()

def update_source_status(source_id: str, is_active: bool) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sources SET is_active = ? WHERE id = ?", (1 if is_active else 0, source_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def update_source_labels(source_id: str, labels: List[str]) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    labels_str = json.dumps(labels)
    cursor.execute("UPDATE sources SET labels_json = ? WHERE id = ?", (labels_str, source_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


# Operations for Sessions & Messages
def create_session(session_id: str, title: str, active_source_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO sessions (id, title, active_source_id)
        VALUES (?, ?, ?)
        """, (session_id, title, active_source_id))
        conn.commit()
        return {
            "id": session_id,
            "title": title,
            "active_source_id": active_source_id
        }
    finally:
        conn.close()

def get_sessions() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    
    sessions = []
    for r in rows:
        sessions.append({
            "id": r["id"],
            "title": r["title"],
            "active_source_id": r["active_source_id"],
            "created_at": r["created_at"],
            "selected_sources": r["selected_sources"] if "selected_sources" in r.keys() else None,
            "relationships": r["relationships"] if "relationships" in r.keys() else None
        })
    return sessions

def get_session_by_id(session_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    r = cursor.fetchone()
    conn.close()
    if r:
        return {
            "id": r["id"],
            "title": r["title"],
            "active_source_id": r["active_source_id"],
            "created_at": r["created_at"],
            "selected_sources": r["selected_sources"] if "selected_sources" in r.keys() else None,
            "relationships": r["relationships"] if "relationships" in r.keys() else None
        }
    return None

def update_session(
    session_id: str, 
    title: Optional[str] = None, 
    active_source_id: Optional[str] = None,
    selected_sources: Optional[str] = None,
    relationships: Optional[str] = None
) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    fields = []
    params = []
    
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
        conn.close()
        return False
        
    params.append(session_id)
    sql = f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?"
    
    try:
        cursor.execute(sql, tuple(params))
        affected = cursor.rowcount
        conn.commit()
        return affected > 0
    finally:
        conn.close()

def delete_session(session_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        affected = cursor.rowcount
        conn.commit()
        return affected > 0
    finally:
        conn.close()

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
    auto_corrections: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    status_history_str = json.dumps(status_history) if status_history is not None else None
    data_str = json.dumps(data) if data is not None else None
    visualization_str = json.dumps(visualization) if visualization is not None else None
    auto_corr_str = json.dumps(auto_corrections) if auto_corrections is not None else None
    
    try:
        cursor.execute("""
        INSERT INTO messages (id, session_id, role, text, status_history, code, code_language, data_json, visualization_json, auto_corrections_json, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (message_id, session_id, role, text, status_history_str, code, code_language, data_str, visualization_str, auto_corr_str, error))
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
            "auto_corrections": auto_corrections
        }
    finally:
        conn.close()

def get_session_messages(session_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
    rows = cursor.fetchall()
    conn.close()
    
    messages = []
    for r in rows:
        messages.append({
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
            "auto_corrections": json.loads(r["auto_corrections_json"]) if r["auto_corrections_json"] else None
        })
    return messages

def clear_session_chat(session_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        affected = cursor.rowcount
        conn.commit()
        return affected > 0
    finally:
        conn.close()

def get_semantic_mapping(source_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT mapping_json FROM semantic_mappings WHERE source_id = ?", (source_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row["mapping_json"])
        except Exception:
            return {}
    return {}

def save_semantic_mapping(source_id: str, mapping: Dict[str, Any]) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO semantic_mappings (source_id, mapping_json) VALUES (?, ?)",
            (source_id, json.dumps(mapping))
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_llm_config() -> Dict[str, str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT key, value FROM settings WHERE key IN ('deepseek_key', 'deepseek_url', 'deepseek_model')")
        rows = cursor.fetchall()
        config = {
            "apiKey": "",
            "baseUrl": "https://api.deepseek.com/v1",
            "model": "deepseek-coder"
        }
        for r in rows:
            if r["key"] == "deepseek_key":
                config["apiKey"] = r["value"]
            elif r["key"] == "deepseek_url":
                config["baseUrl"] = r["value"]
            elif r["key"] == "deepseek_model":
                config["model"] = r["value"]
        return config
    except Exception:
        return {
            "apiKey": "",
            "baseUrl": "https://api.deepseek.com/v1",
            "model": "deepseek-coder"
        }
    finally:
        conn.close()

def update_llm_config(api_key: str, base_url: str, model: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('deepseek_key', ?)", (api_key,))
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('deepseek_url', ?)", (base_url,))
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('deepseek_model', ?)", (model,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

