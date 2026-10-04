"""
app/routers/settings_router.py
LLM yapılandırma ayarları endpoint'leri.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database.manager import get_llm_config, update_llm_config, get_stored_api_key
from app.core.audit import audit
from app.core.auth import require_admin
from app.core.logger import logger

router = APIRouter(prefix="/api/settings", tags=["settings"])

_MASK = "••••"


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return _MASK
    return f"{_MASK}{key[-4:]}"


class LLMConfigRequest(BaseModel):
    apiKey: str
    baseUrl: str
    model: str


@router.get("")
def get_settings_endpoint(admin: dict = Depends(require_admin)):
    try:
        config = get_llm_config()
        # API anahtarı istemciye asla düz metin döndürülmez.
        config["apiKey"] = _mask_key(config.get("apiKey", ""))
        config["apiKeyMasked"] = True
        return config
    except Exception as e:
        logger.error(f"get_settings error: {e}")
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")


@router.put("")
def update_settings_endpoint(req: LLMConfigRequest, admin: dict = Depends(require_admin)):
    try:
        api_key = req.apiKey
        if _MASK in api_key or not api_key.strip():
            # Maskelenmiş/boş anahtar geri gelirse mevcut saklanan anahtarı koru.
            existing = get_stored_api_key()
            if existing:
                api_key = existing
            elif not api_key.strip():
                raise HTTPException(status_code=400, detail="API_KEY_REQUIRED")
        success = update_llm_config(api_key, req.baseUrl, req.model)
        audit("settings.llm_update", detail={"model": req.model, "baseUrl": req.baseUrl}, user=admin)
        if not success:
            raise HTTPException(status_code=500, detail="SETTINGS_SAVE_FAILED")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("500 - %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")
