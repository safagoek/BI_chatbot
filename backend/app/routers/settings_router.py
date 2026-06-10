"""
app/routers/settings_router.py
LLM yapılandırma ayarları endpoint'leri.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database.manager import get_llm_config, update_llm_config
from app.core.logger import logger

router = APIRouter(prefix="/api/settings", tags=["settings"])


class LLMConfigRequest(BaseModel):
    apiKey: str
    baseUrl: str
    model: str


@router.get("")
def get_settings_endpoint():
    try:
        return get_llm_config()
    except Exception as e:
        logger.error(f"get_settings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("")
def update_settings_endpoint(req: LLMConfigRequest):
    try:
        success = update_llm_config(req.apiKey, req.baseUrl, req.model)
        if not success:
            raise HTTPException(status_code=500, detail="SETTINGS_SAVE_FAILED")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
