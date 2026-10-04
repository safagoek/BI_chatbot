"""
app/routers/saves_router.py
Kayıtlı analizler: kullanıcının soru+ kaynak kombinasyonunu saklayıp tek tıkla tekrar çalıştırması.
"""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.database.manager import (
    create_saved_analysis, delete_saved_analysis, list_saved_analyses,
)

router = APIRouter(prefix="/api/saves", tags=["saves"])


class SaveCreate(BaseModel):
    title: str
    question: str
    source_ids: List[str] = []
    relationships: Optional[List[dict]] = None


@router.get("")
def list_saves(user: dict = Depends(get_current_user)):
    rows = list_saved_analyses(user["id"])
    for r in rows:
        r["source_ids"] = json.loads(r.pop("source_ids_json") or "[]")
        r["relationships"] = json.loads(r.pop("relationships_json") or "[]")
    return rows


@router.post("")
def create_save(req: SaveCreate, user: dict = Depends(get_current_user)):
    if not req.title.strip() or not req.question.strip():
        raise HTTPException(status_code=400, detail="TITLE_AND_QUESTION_REQUIRED")
    row = create_saved_analysis(
        user["id"], req.title.strip()[:120], req.question.strip(),
        json.dumps(req.source_ids), json.dumps(req.relationships or []),
    )
    row["source_ids"] = json.loads(row.pop("source_ids_json") or "[]")
    row["relationships"] = json.loads(row.pop("relationships_json") or "[]")
    return row


@router.delete("/{save_id}")
def delete_save(save_id: str, user: dict = Depends(get_current_user)):
    if not delete_saved_analysis(user["id"], save_id):
        raise HTTPException(status_code=404, detail="SAVE_NOT_FOUND")
    return {"success": True}
