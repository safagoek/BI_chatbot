"""
app/routers/rag_router.py
RAG bellek yönetim endpoint'leri.
"""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.logger import logger

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.get("/memory")
def get_rag_memory(source_id: Optional[str] = None):
    """RAG hafızasındaki tüm sorgu girişlerini listeler (opsiyonel source_id filtresi)."""
    try:
        import sqlite3
        from app.database.manager import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if source_id:
            cursor.execute(
                "SELECT question, intent, source_id, feedback, execution_success FROM rag_memory WHERE source_id = ? ORDER BY feedback DESC",
                (source_id,),
            )
        else:
            cursor.execute(
                "SELECT question, intent, source_id, feedback, execution_success FROM rag_memory ORDER BY feedback DESC"
            )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "question": r["question"],
                "intent": r["intent"],
                "source_id": r["source_id"],
                "feedback": r["feedback"],
                "execution_success": bool(r["execution_success"]),
            }
            for r in rows
        ]
    except Exception as e:
        logger.error(f"get_rag_memory error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class RAGFeedbackUpdate(BaseModel):
    feedback: str  # "positive" | "negative" | "neutral"


@router.put("/memory/{question_b64}/feedback")
def update_rag_feedback(question_b64: str, payload: RAGFeedbackUpdate):
    """Belirli bir sorgu için feedback günceller."""
    try:
        import base64
        question = base64.urlsafe_b64decode(question_b64.encode()).decode("utf-8")
        from app.agent.rag import update_feedback
        update_feedback(question, payload.feedback)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memory/{question_b64}")
def delete_rag_entry(question_b64: str):
    """Belirli bir sorgu girişini RAG hafızasından siler."""
    try:
        import base64
        import sqlite3
        from app.database.manager import DB_PATH
        from app.agent import rag as _rag

        question = base64.urlsafe_b64decode(question_b64.encode()).decode("utf-8")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM rag_memory WHERE question = ?", (question,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        # In-memory cache'i temizle
        _rag._memory_cache = None

        if affected == 0:
            raise HTTPException(status_code=404, detail="RAG_ENTRY_NOT_FOUND")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memory")
def clear_rag_memory(source_id: Optional[str] = None):
    """Tüm RAG hafızasını veya belirli bir kaynağa ait girişleri temizler."""
    try:
        import sqlite3
        from app.database.manager import DB_PATH
        from app.agent import rag as _rag

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if source_id:
            cursor.execute("DELETE FROM rag_memory WHERE source_id = ?", (source_id,))
        else:
            cursor.execute("DELETE FROM rag_memory")

        affected = cursor.rowcount
        conn.commit()
        conn.close()

        # In-memory cache'i sıfırla
        _rag._memory_cache = None

        return {"success": True, "deleted_count": affected}
    except Exception as e:
        logger.error(f"clear_rag_memory error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
