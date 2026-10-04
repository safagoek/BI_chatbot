"""
app/routers/auth_router.py
Giriş, oturum bilgisi ve şifre değiştirme endpoint'leri.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.audit import audit
from app.core.auth import create_access_token, get_current_user, verify_password, hash_password
from app.core.logger import logger
from app.database.manager import get_user_by_username, get_user_permissions, update_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthUserOut(BaseModel):
    id: str
    username: str
    display_name: str
    role: str
    must_change_password: bool
    source_ids: Optional[List[str]] = None


class LoginResponse(BaseModel):
    token: str
    user: AuthUserOut


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _user_payload(user: dict) -> dict:
    from app.core.auth import get_allowed_source_ids
    allowed = get_allowed_source_ids(user)
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user.get("display_name") or "",
        "role": user["role"],
        "must_change_password": bool(user.get("must_change_password")),
        "source_ids": allowed,
    }


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    user = get_user_by_username(req.username.strip())
    if not user or not verify_password(req.password, user["password_hash"]):
        logger.warning("Başarısız giriş denemesi: %s", req.username[:32])
        audit("auth.login_failed", target=req.username.strip()[:64])
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="ACCOUNT_DISABLED")

    token = create_access_token(user["id"], user["username"], user["role"])
    audit("auth.login", target=user["username"], user=user)
    return {"token": token, "user": _user_payload(user)}


@router.get("/me", response_model=AuthUserOut)
def me(user: dict = Depends(get_current_user)):
    return _user_payload(user)


@router.post("/change-password")
def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="PASSWORD_TOO_SHORT (min 8)")
    db_user = get_user_by_username(user["username"])
    if not db_user or not verify_password(req.current_password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
    update_user(user["id"], password_hash=hash_password(req.new_password))
    audit("auth.change_password", target=user["username"], user=user)
    return {"success": True}
