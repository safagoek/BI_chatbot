"""
app/core/audit.py

Ürün çapında denetim kaydı (audit log): "kim, ne zaman, ne yaptı, hangi kaynakta".

- `audit()` fire-and-forget'tır: hata olsa bile iş akışını ASLA bozmaz.
- Hassas alanlar (password, api_key, token...) detaydan otomatik maskelenir.
- Kayıtlar `audit_log` tablosuna yazılır; `GET /api/admin/audit` ile okunur.
"""
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Bu anahtarlara sahip değerler detaydan tamamen çıkarılır
_SENSITIVE_KEYS = {"password", "new_password", "current_password", "apikey", "api_key",
                   "token", "secret", "authorization", "connection_details"}

_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "90") or 90)


def _sanitize(detail: Any) -> Any:
    if isinstance(detail, dict):
        clean = {}
        for k, v in detail.items():
            if str(k).lower() in _SENSITIVE_KEYS:
                clean[str(k)] = "***"
            else:
                clean[str(k)] = _sanitize(v)
        return clean
    if isinstance(detail, (list, tuple)):
        return [_sanitize(v) for v in detail]
    return detail


def audit(
    action: str,
    target: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    user: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    ip: Optional[str] = None,
) -> None:
    """
    Denetim kaydı yazar. Hiçbir durumda exception fırlatmaz.

    action: nokta notasyonu — örn. "auth.login", "source.delete", "chat.query"
    target: etkilenen kaynağın id/adı — örn. oturum id, kaynak id, kullanıcı adı
    detail: küçük, JSON-uyumlu ek bilgi (hassas alanlar maskelenir)
    user:   get_current_user'dan dönen kullanıcı dict'i (yoksa anonim)
    """
    try:
        from app.core.logger import current_request_id
        from app.database.manager import db_connection

        rid = request_id or current_request_id()
        clean_detail = _sanitize(detail or {})
        user_id = (user or {}).get("id")
        username = (user or {}).get("username")

        with db_connection() as conn:
            conn.execute(
                """INSERT INTO audit_log (user_id, username, action, target, detail_json, request_id, ip)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    username,
                    action,
                    (target or "")[:256],
                    json.dumps(clean_detail, ensure_ascii=False) if clean_detail else None,
                    (rid or "")[:64],
                    (ip or "")[:64],
                ),
            )
            conn.commit()
    except Exception as e:  # audit asla iş akışını bozmaz
        logger.warning("Audit yazılamadı (%s): %s", action, e)


def prune_old_entries() -> None:
    """Saklama süresini aşan kayıtları siler (uygulama başlangıcında çağrılır)."""
    try:
        from app.database.manager import db_connection

        cutoff = (datetime.utcnow() - timedelta(days=_RETENTION_DAYS)).isoformat()
        with db_connection() as conn:
            cur = conn.execute("DELETE FROM audit_log WHERE created_at < ?", (cutoff,))
            conn.commit()
        if cur.rowcount:
            logger.info("Audit: %d eski kayıt silindi (retention=%d gün)", cur.rowcount, _RETENTION_DAYS)
    except Exception as e:
        logger.warning("Audit prune başarısız: %s", e)
