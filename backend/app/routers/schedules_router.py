"""
app/routers/schedules_router.py
Zamanlanmış raporlar: kullanıcının kendi schedule CRUD'u (koşturma scheduler'da).
"""
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.core.audit import audit
from app.core.auth import get_current_user
from app.database.manager import (
    create_scheduled_report, delete_scheduled_report,
    get_scheduled_report, list_scheduled_reports, update_scheduled_report,
)

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


class ScheduleCreate(BaseModel):
    title: str
    question: str
    source_ids: List[str] = []
    relationships: Optional[List[dict]] = None
    frequency: str = "daily"        # daily | weekly
    hour: int = 9                   # 0-23
    day_of_week: int = 1            # 0=Pzt ... 6=Paz (weekly için)
    email: str = ""


class ScheduleUpdate(BaseModel):
    title: Optional[str] = None
    question: Optional[str] = None
    frequency: Optional[str] = None
    hour: Optional[int] = None
    day_of_week: Optional[int] = None
    email: Optional[str] = None
    active: Optional[bool] = None


def _serialize(r: dict) -> dict:
    r["source_ids"] = json.loads(r.pop("source_ids_json") or "[]")
    r["relationships"] = json.loads(r.pop("relationships_json") or "[]")
    r["active"] = bool(r.get("active", 1))
    return r


@router.get("")
def list_my_schedules(user: dict = Depends(get_current_user)):
    return [_serialize(r) for r in list_scheduled_reports(user["id"])]


@router.post("")
def create_schedule(req: ScheduleCreate, user: dict = Depends(get_current_user)):
    if not req.title.strip() or not req.question.strip():
        raise HTTPException(status_code=400, detail="TITLE_AND_QUESTION_REQUIRED")
    if req.frequency not in ("daily", "weekly"):
        raise HTTPException(status_code=400, detail="INVALID_FREQUENCY")
    if not 0 <= req.hour <= 23:
        raise HTTPException(status_code=400, detail="INVALID_HOUR")
    row = create_scheduled_report(
        user["id"], req.title.strip()[:120], req.question.strip(),
        json.dumps(req.source_ids), json.dumps(req.relationships or []),
        req.frequency, req.hour, req.day_of_week, req.email.strip(),
    )
    audit("schedule.create", target=row["id"], detail={"title": row["title"], "frequency": row["frequency"]}, user=user)
    return _serialize(row)


@router.put("/{schedule_id}")
def update_schedule(schedule_id: str, req: ScheduleUpdate, user: dict = Depends(get_current_user)):
    if not get_scheduled_report(schedule_id, user["id"]):
        raise HTTPException(status_code=404, detail="SCHEDULE_NOT_FOUND")
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    update_scheduled_report(user["id"], schedule_id, **fields)
    audit("schedule.update", target=schedule_id, user=user)
    return _serialize(get_scheduled_report(schedule_id, user["id"]))


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: str, user: dict = Depends(get_current_user)):
    if not delete_scheduled_report(user["id"], schedule_id):
        raise HTTPException(status_code=404, detail="SCHEDULE_NOT_FOUND")
    audit("schedule.delete", target=schedule_id, user=user)
    return {"success": True}
