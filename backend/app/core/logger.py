"""
app/core/logger.py

Merkezi loglama:
- Tüm modüller `logging.getLogger(__name__)` ile log üretir; handler'lar ROOT
  logger'a bir kez kurulur (böylece output tutarlıdır).
- Her kayıt, o isteğin correlation (request) ID'sini taşır — contextvars
  üzerinden token_auth_middleware tarafından set edilir.
- LOG_FORMAT=json ile makine-okur yapılandırılmış log üretir.
"""
import contextvars
import json
import logging
import os
import sys
from typing import Optional

from app.core.config import settings

# İstek yaşam döngüsü boyunca geçerli correlation ID
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def current_request_id() -> str:
    return request_id_var.get()


def _resolve_log_path(path: str) -> str:
    """Göreli log yolunu backend köküne sabitler (CWD'ye değil) — aksi halde
    farklı dizinlerden başlatınca birden çok deepbi.log oluşuyor."""
    if os.path.isabs(path):
        return path
    return os.path.join(_BACKEND_ROOT, path)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "loc": f"{record.filename}:{record.lineno}",
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_TEXT_FMT = "%(asctime)s - %(name)s - %(levelname)s - [req:%(request_id)s] - [%(filename)s:%(lineno)d] - %(message)s"
_JSON_FMT = JsonFormatter()


def _configure_root() -> None:
    root = logging.getLogger()
    if getattr(root, "_deepbi_configured", False):
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root.setLevel(level)

    formatter: logging.Formatter
    if settings.log_format.lower() == "json":
        formatter = _JSON_FMT
    else:
        formatter = logging.Formatter(fmt=_TEXT_FMT, datefmt="%Y-%m-%d %H:%M:%S")

    rid_filter = RequestIdFilter()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(rid_filter)
    root.addHandler(console)

    if settings.log_file:
        try:
            log_path = _resolve_log_path(settings.log_file)
            log_dir = os.path.dirname(log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            file_handler = logging.FileHandler(log_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            file_handler.addFilter(rid_filter)
            root.addHandler(file_handler)
        except Exception as e:
            root.warning("Log dosyası yapılandırılamadı (%s): %s", settings.log_file, e)

    # uvicorn'un kendi handler'larıyla çift log üretmemesi için
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).propagate = False

    root._deepbi_configured = True


def setup_logger(name: str = "app") -> logging.Logger:
    """Geriye dönük uyumluluk: handler'lar root'ta; alt logger'lar propagate eder."""
    _configure_root()
    logger = logging.getLogger(name)
    logger.propagate = True
    return logger


logger = setup_logger("app")
