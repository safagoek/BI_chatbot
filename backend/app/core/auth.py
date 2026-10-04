"""
app/core/auth.py

SaaS kimlik doğrulama çekirdeği:
- bcrypt ile şifre hash'leme
- python-jose ile HS256 JWT üretimi/doğrulaması
- FastAPI dependency'leri: get_current_user, require_admin

İki kimlik doğrulama yolu:
1. JWT (Authorization: Bearer <token>) — kullanıcı oturumları
2. X-API-Token == settings.app_token — makine/bootstrap erişimi (admin yetkisiyle)
"""
from typing import Any, Dict, List, Optional

import bcrypt
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt

from app.core.config import settings
from app.database.manager import get_user_by_id, get_user_permissions

_JWT_ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    # bcrypt 72 bayt sınırı — uyumluluk için manuel kırpma
    data = plain.encode("utf-8")[:72]
    return bcrypt.hashpw(data, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        data = plain.encode("utf-8")[:72]
        return bcrypt.checkpw(data, hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, username: str, role: str) -> str:
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_JWT_ALGORITHM)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[_JWT_ALGORITHM])
    except JWTError:
        return None


def _extract_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):]
    return request.headers.get("X-API-Token", "")


def get_current_user(request: Request) -> Dict[str, Any]:
    """JWT veya APP_TOKEN ile kimliklenen kullanıcı döndürür; başarısızsa 401."""
    token = _extract_token(request)

    # 1. Makine/bootstrap erişimi: APP_TOKEN doğruysa sanal admin
    if settings.app_token and token == settings.app_token:
        return {"id": "machine", "username": "machine", "role": "admin", "is_active": 1}

    # 2. JWT oturumu
    if token:
        payload = decode_token(token)
        if payload:
            user = get_user_by_id(payload.get("sub", ""))
            if user and user.get("is_active"):
                return user

    raise HTTPException(status_code=401, detail="UNAUTHORIZED")


def require_admin(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="ADMIN_REQUIRED")
    return user


def get_allowed_source_ids(user: Dict[str, Any]) -> Optional[List[str]]:
    """Kullanıcının erişebileceği kaynak id'leri. Admin → None (tümü)."""
    if user.get("role") == "admin":
        return None
    return get_user_permissions(user["id"])
