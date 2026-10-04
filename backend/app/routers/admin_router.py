"""
app/routers/admin_router.py
Main admin: kullanıcı oluşturma, yetkilendirme, şifre sıfırlama.
"""
import json
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.audit import audit
from app.core.auth import hash_password, require_admin
from app.core.logger import logger
from app.database.manager import (
    count_active_admins,
    create_user,
    delete_user,
    get_user_by_id,
    get_user_by_username,
    get_user_permissions,
    list_users,
    replace_user_permissions,
    update_user,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")


class UserOut(BaseModel):
    id: str
    username: str
    display_name: Optional[str] = ""
    role: str
    is_active: bool
    must_change_password: bool
    created_at: Optional[str] = None
    source_ids: List[str] = []


class CreateUserRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""
    role: str = "user"


class UpdateUserRequest(BaseModel):
    password: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class PermissionsRequest(BaseModel):
    source_ids: List[str]


def _ensure_exists(user_id: str) -> dict:
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="USER_NOT_FOUND")
    return user


@router.get("/audit")
def list_audit_logs(
    limit: int = 100,
    offset: int = 0,
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    admin: dict = Depends(require_admin),
):
    """Denetim kayıtları — en yeniden eskiye. limit max 500."""
    import sqlite3
    from app.database.manager import DB_PATH

    limit = max(1, min(int(limit), 500))
    offset = max(0, int(offset))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        where, params = [], []
        if action:
            where.append("action LIKE ?")
            params.append(f"{action}%")
        if user_id:
            where.append("user_id = ?")
            params.append(user_id)
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        total = conn.execute(f"SELECT COUNT(*) FROM audit_log {where_sql}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM audit_log {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        items = []
        for r in rows:
            d = dict(r)
            if d.get("detail_json"):
                try:
                    d["detail"] = json.loads(d["detail_json"])
                except Exception:
                    d["detail"] = None
                del d["detail_json"]
            items.append(d)
        return {"items": items, "total": total, "limit": limit, "offset": offset}
    finally:
        conn.close()


@router.get("/users", response_model=List[UserOut])
def list_all_users(admin: dict = Depends(require_admin)):
    users = list_users()
    return [{**u, "source_ids": get_user_permissions(u["id"])} for u in users]


@router.post("/users")
def create_new_user(req: CreateUserRequest, admin: dict = Depends(require_admin)):
    username = req.username.strip().lower()
    if not _USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="INVALID_USERNAME (3-32; harf, rakam, . _ -)")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="PASSWORD_TOO_SHORT (min 8)")
    if req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="INVALID_ROLE")
    if get_user_by_username(username):
        raise HTTPException(status_code=409, detail="USERNAME_TAKEN")

    user = create_user(username, hash_password(req.password), req.display_name.strip(), req.role)
    logger.info("Yeni kullanıcı oluşturuldu: %s (%s) — oluşturan: %s", username, req.role, admin["username"])
    audit("admin.user_create", target=username, detail={"role": req.role}, user=admin)
    return {"id": user["id"], "username": user["username"], "role": user["role"]}


@router.put("/users/{user_id}")
def update_existing_user(user_id: str, req: UpdateUserRequest, admin: dict = Depends(require_admin)):
    _ensure_exists(user_id)
    if req.role is not None and req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="INVALID_ROLE")
    # Son aktif adminin yetkisi/alakası kaldırılamaz
    target = get_user_by_id(user_id)
    if target["role"] == "admin" and (req.role == "user" or req.is_active is False):
        if count_active_admins() <= 1:
            raise HTTPException(status_code=400, detail="LAST_ADMIN")
    if req.password is not None and len(req.password) < 8:
        raise HTTPException(status_code=400, detail="PASSWORD_TOO_SHORT (min 8)")

    audit("admin.user_update", target=user_id, user=admin,
          detail={k: v for k, v in {"display_name": req.display_name, "role": req.role, "is_active": req.is_active}.items() if v is not None})
    update_user(
        user_id,
        password_hash=hash_password(req.password) if req.password else None,
        display_name=req.display_name,
        role=req.role,
        is_active=req.is_active,
        must_change_password=True if req.password else None,
    )
    return {"success": True}


@router.delete("/users/{user_id}")
def delete_existing_user(user_id: str, admin: dict = Depends(require_admin)):
    target = _ensure_exists(user_id)
    if target["id"] == admin["id"]:
        raise HTTPException(status_code=400, detail="CANNOT_DELETE_SELF")
    if target["role"] == "admin" and count_active_admins() <= 1:
        raise HTTPException(status_code=400, detail="LAST_ADMIN")
    delete_user(user_id)
    audit("admin.user_delete", target=target["username"], user=admin)
    return {"success": True}


@router.put("/users/{user_id}/permissions")
def set_user_source_permissions(user_id: str, req: PermissionsRequest, admin: dict = Depends(require_admin)):
    _ensure_exists(user_id)
    replace_user_permissions(user_id, req.source_ids)
    audit("admin.permissions_update", target=user_id, detail={"source_ids": req.source_ids}, user=admin)
    return {"success": True, "source_ids": req.source_ids}


@router.get("/users/{user_id}/permissions")
def get_user_source_permissions(user_id: str, admin: dict = Depends(require_admin)):
    _ensure_exists(user_id)
    return {"source_ids": get_user_permissions(user_id)}
