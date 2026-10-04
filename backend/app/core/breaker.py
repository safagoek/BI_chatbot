"""
app/core/breaker.py

Kaynak bazlı basit circuit breaker: aynı dış veritabanına art arda gelen
başarısız bağlantı denemeleri kısa bir "açılmış" penceresiyle kesilir —
böylece ağdaki yavaş/ölü bir DB her chat isteğini bekletmez.
"""
import threading
import time
from collections import deque
from typing import Deque, Dict, Tuple

# Eşik: son _WINDOW saniyede _THRESHOLD hata → _COOLDOWN saniye açık
_THRESHOLD = 3
_WINDOW = 60.0
_COOLDOWN = 60.0

_lock = threading.Lock()
_failures: Dict[str, Deque[float]] = {}
_open_until: Dict[str, float] = {}


def _key(db_type: str, connection_details: Dict) -> str:
    host = str(connection_details.get("host") or connection_details.get("database_path") or "local")
    return f"{db_type.lower()}:{host}"


def is_open(db_type: str, connection_details: Dict) -> Tuple[bool, int]:
    """(açılmış mı, kalan saniye) döndürür."""
    key = _key(db_type, connection_details)
    with _lock:
        until = _open_until.get(key, 0.0)
        now = time.monotonic()
        if until > now:
            return True, int(until - now) + 1
        if key in _open_until:
            # Cooldown doldu — yarım açık duruma geç, sayaçları tut
            del _open_until[key]
    return False, 0


def record_failure(db_type: str, connection_details: Dict) -> None:
    key = _key(db_type, connection_details)
    now = time.monotonic()
    with _lock:
        dq = _failures.setdefault(key, deque())
        dq.append(now)
        while dq and now - dq[0] > _WINDOW:
            dq.popleft()
        if len(dq) >= _THRESHOLD:
            _open_until[key] = now + _COOLDOWN
            dq.clear()


def record_success(db_type: str, connection_details: Dict) -> None:
    key = _key(db_type, connection_details)
    with _lock:
        _failures.pop(key, None)
        _open_until.pop(key, None)


def reset() -> None:
    """Test yardımcısı."""
    with _lock:
        _failures.clear()
        _open_until.clear()
