"""
app/routers/sessions.py
Chat oturumu CRUD endpoint'leri.
"""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database.manager import (
    create_session, get_sessions, get_session_by_id,
    update_session, delete_session, add_chat_message,
    get_session_messages, clear_session_chat,
)
from app.core.logger import logger

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    active_source_id: Optional[str] = ""
    selected_sources: Optional[List[str]] = None
    relationships: Optional[List[Dict[str, Any]]] = None


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    active_source_id: Optional[str] = None
    selected_sources: Optional[List[str]] = None
    relationships: Optional[List[Dict[str, Any]]] = None


@router.get("")
def list_sessions():
    try:
        return get_sessions()
    except Exception as e:
        logger.error(f"list_sessions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
def search_sessions(q: str = ""):
    """Oturum başlıkları ve mesaj içeriklerinde arama yapar."""
    try:
        import sqlite3
        from app.database.manager import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = f"%{q}%"
        cursor.execute(
            """
            SELECT DISTINCT s.id, s.title, s.active_source_id, s.created_at
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            WHERE s.title LIKE ? OR m.text LIKE ?
            ORDER BY s.created_at DESC
            LIMIT 50
            """,
            (query, query),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"search_sessions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}")
def get_session(session_id: str):
    try:
        session = get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
def create_new_session(req: SessionCreate):
    try:
        import time
        s_id = req.id or f"session-{int(time.time() * 1000)}"
        title = req.title or "Yeni Sohbet"
        active_source = req.active_source_id or ""

        result = create_session(s_id, title, active_source)

        if req.selected_sources is not None or req.relationships is not None:
            sel_str = json.dumps(req.selected_sources) if req.selected_sources is not None else None
            rel_str = json.dumps(req.relationships) if req.relationships is not None else None
            update_session(s_id, selected_sources=sel_str, relationships=rel_str)

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{session_id}")
def update_session_endpoint(session_id: str, req: SessionUpdate):
    try:
        sel_str = json.dumps(req.selected_sources) if req.selected_sources is not None else None
        rel_str = json.dumps(req.relationships) if req.relationships is not None else None

        success = update_session(session_id, req.title, req.active_source_id, sel_str, rel_str)
        if not success:
            raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
def delete_session_endpoint(session_id: str):
    try:
        success = delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/messages")
def get_session_chat_messages(session_id: str):
    try:
        return get_session_messages(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/clear")
def clear_session_chat_endpoint(session_id: str):
    try:
        clear_session_chat(session_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
