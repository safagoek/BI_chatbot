"""
app/routers/mcp_router.py
MCP sunucu bağlantı yapılandırmasını (.agents/mcp_config.json) okuyup yazan
admin endpoint'leri. Dosya valid JSON olmak zorundadır; mcpServers yapısı korunur.
"""
import json
import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.audit import audit
from app.core.auth import require_admin
from app.core.logger import logger

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

_MCP_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".agents",
    "mcp_config.json",
)


class MCPConfigRequest(BaseModel):
    config: Dict[str, Any]


def _read_config() -> Dict[str, Any]:
    try:
        with open(_MCP_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"mcpServers": {}}
    except Exception as e:
        logger.error("MCP config okunamadı: %s", e)
        raise HTTPException(status_code=500, detail=f"MCP_CONFIG_READ_FAILED: {e}")


@router.get("/config")
def get_mcp_config(admin: dict = Depends(require_admin)):
    return JSONResponse(content=_read_config())


@router.put("/config")
def update_mcp_config(req: MCPConfigRequest, admin: dict = Depends(require_admin)):
    config = req.config
    if not isinstance(config, dict) or "mcpServers" not in config or not isinstance(config["mcpServers"], dict):
        raise HTTPException(status_code=400, detail="INVALID_CONFIG: 'mcpServers' objesi zorunlu.")
    for name, server in config["mcpServers"].items():
        if not isinstance(server, dict) or not server.get("command"):
            raise HTTPException(
                status_code=400,
                detail=f"INVALID_CONFIG: '{name}' sunucusunda 'command' zorunlu.",
            )
    try:
        os.makedirs(os.path.dirname(_MCP_CONFIG_PATH), exist_ok=True)
        with open(_MCP_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("MCP config yazılamadı: %s", e)
        raise HTTPException(status_code=500, detail=f"MCP_CONFIG_WRITE_FAILED: {e}")
    logger.info("MCP config güncellendi — güncelleyen: %s", admin["username"])
    audit("mcp.config_update", user=admin)
    return {"success": True}
