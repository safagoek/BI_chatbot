"""
app/routers/sources.py
Veri kaynağı CRUD endpoint'leri.
"""
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, File, UploadFile
from pydantic import BaseModel

from app.database.manager import (
    get_data_sources, get_data_source_by_id, add_data_source,
    update_data_source, update_source_schema, update_source_status,
    update_source_labels, get_semantic_mapping, save_semantic_mapping,
)
from app.database.connectors import test_connection, discover_schema
from app.core.logger import logger

router = APIRouter(prefix="/api/sources", tags=["sources"])


class DBTestRequest(BaseModel):
    type: str
    connection_details: Dict[str, Any]


class DBSourceCreate(BaseModel):
    type: str
    display_name: str
    connection_details: Dict[str, Any]
    labels: Optional[List[str]] = None
    is_active: Optional[bool] = True


class DBSourceUpdate(BaseModel):
    display_name: Optional[str] = None
    connection_details: Optional[Dict[str, Any]] = None
    labels: Optional[List[str]] = None
    is_active: Optional[bool] = None


class DBSourceStatusUpdate(BaseModel):
    is_active: bool


class DBSourceLabelsUpdate(BaseModel):
    labels: List[str]


class DBSourceCloneRequest(BaseModel):
    display_name: Optional[str] = None


@router.get("")
def list_sources():
    try:
        return get_data_sources()
    except Exception as e:
        logger.error(f"list_sources error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/local-sqlite-files")
def list_local_sqlite_files():
    """Lists all local SQLite files (.db, .sqlite, .sqlite3) in the backend directory and uploads."""
    import glob
    import os
    
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # Search for .db, .sqlite, .sqlite3 files in backend_dir and uploads
    patterns = ["*.db", "*.sqlite", "*.sqlite3", "uploads/*.db", "uploads/*.sqlite", "uploads/*.sqlite3"]
    
    found_files = []
    for pattern in patterns:
        full_pattern = os.path.join(backend_dir, pattern)
        for filepath in glob.glob(full_pattern):
            rel_path = os.path.relpath(filepath, backend_dir)
            if os.path.basename(filepath) == "metadata.db":
                continue
            found_files.append(rel_path)
        
    return sorted(list(set(found_files)))


@router.post("/upload-sqlite")
async def upload_sqlite_file(file: UploadFile = File(...)):
    """Uploads a SQLite database file and saves it in the uploads directory."""
    import os
    import shutil
    
    filename = file.filename
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in [".db", ".sqlite", ".sqlite3"]:
        raise HTTPException(status_code=400, detail="UNSUPPORTED_SQLITE_FORMAT")
        
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    uploads_dir = os.path.join(backend_dir, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    
    save_path = os.path.join(uploads_dir, filename)
    
    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FILE_WRITE_FAILED: {str(e)}")
        
    rel_path = os.path.relpath(save_path, backend_dir)
    return {"success": True, "database_path": rel_path, "filename": filename}


@router.get("/{source_id}")
def get_source(source_id: str):
    source = get_data_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="SOURCE_NOT_FOUND")
    return source


@router.post("/test-connection")
def test_source_connection(req: DBTestRequest):
    success, message = test_connection(req.type, req.connection_details)
    return {"success": success, "message": message}


@router.post("/discover-schema")
def discover_source_schema(req: DBTestRequest):
    try:
        schema = discover_schema(req.type, req.connection_details)
        return {"success": True, "schema": schema, "table_count": len(schema)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("")
def create_source(source: DBSourceCreate):
    source_id = f"db_{uuid.uuid4().hex[:8]}"
    try:
        schema = discover_schema(source.type, source.connection_details)
    except Exception as _e:
        logger.warning(f"Schema discovery failed on source creation: {_e}")
        schema = {}

    try:
        result = add_data_source(
            source_id, source.type, source.display_name,
            source.connection_details, schema, source.labels,
            source.is_active if source.is_active is not None else True,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{source_id}")
def update_source(source_id: str, source: DBSourceUpdate):
    sources = get_data_sources()
    target = next((s for s in sources if s["id"] == source_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="SOURCE_NOT_FOUND")

    try:
        schema = discover_schema(target["type"], source.connection_details)
    except Exception as _e:
        logger.warning(f"Schema refresh failed on update: {_e}")
        schema = target["schema"]

    labels = source.labels if source.labels is not None else target.get("labels", [])
    try:
        success = update_data_source(
            source_id, source.display_name,
            source.connection_details, schema, labels,
        )
        if not success:
            raise HTTPException(status_code=400, detail="UPDATE_FAILED")
        return {
            "id": source_id,
            "type": target["type"],
            "display_name": source.display_name,
            "connection_details": source.connection_details,
            "schema": schema,
            "labels": labels,
            "is_active": target.get("is_active", True),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{source_id}/status")
def update_source_status_endpoint(source_id: str, payload: DBSourceStatusUpdate):
    success = update_source_status(source_id, payload.is_active)
    if not success:
        raise HTTPException(status_code=404, detail="SOURCE_NOT_FOUND")
    return {"success": True, "is_active": payload.is_active}


@router.put("/{source_id}/labels")
def update_source_labels_endpoint(source_id: str, payload: DBSourceLabelsUpdate):
    success = update_source_labels(source_id, payload.labels)
    if not success:
        raise HTTPException(status_code=404, detail="SOURCE_NOT_FOUND")
    return {"success": True, "labels": payload.labels}


@router.post("/{source_id}/clone")
def clone_source(source_id: str, payload: DBSourceCloneRequest):
    source = get_data_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="SOURCE_NOT_FOUND")

    new_id = f"db_{uuid.uuid4().hex[:8]}"
    new_display = payload.display_name or f"{source['display_name']} (Kopya)"
    result = add_data_source(
        new_id, source["type"], new_display,
        source["connection_details"], source.get("schema", {}),
        source.get("labels", []), source.get("is_active", True),
    )
    return result


@router.post("/{source_id}/snapshot")
def take_source_snapshot(source_id: str):
    from app.database.snapshots import create_database_snapshot
    try:
        result = create_database_snapshot(source_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SNAPSHOT_FAILED: {str(e)}")


@router.get("/{source_id}/snapshot/stream")
def stream_source_snapshot(source_id: str, tables: Optional[str] = None):
    from app.database.snapshots import yield_database_snapshot_progress
    from fastapi.responses import StreamingResponse
    import json

    selected_tables = None
    if tables:
        selected_tables = [t.strip() for t in tables.split(",") if t.strip()]

    def event_generator():
        for event in yield_database_snapshot_progress(source_id, selected_tables):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.put("/{source_id}/refresh-schema")
def refresh_schema(source_id: str):
    sources = get_data_sources()
    target = next((s for s in sources if s["id"] == source_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="SOURCE_NOT_FOUND")
    try:
        schema = discover_schema(target["type"], target["connection_details"])
        update_source_schema(source_id, schema)
        return {"success": True, "schema": schema, "table_count": len(schema)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{source_id}")
def delete_source(source_id: str):
    import sqlite3 as sq
    from app.database.manager import DB_PATH
    conn = sq.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    if affected == 0:
        raise HTTPException(status_code=404, detail="SOURCE_NOT_FOUND")
    return {"success": True}


@router.get("/{source_id}/semantic")
def get_source_semantic(source_id: str):
    try:
        return get_semantic_mapping(source_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{source_id}/semantic")
def update_source_semantic(source_id: str, mapping: Dict[str, Any]):
    try:
        success = save_semantic_mapping(source_id, mapping)
        if not success:
            raise HTTPException(status_code=400, detail="SEMANTIC_SAVE_FAILED")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connectors/status")
def get_connector_status():
    """Kurumsal DB connector'larının kurulum durumunu döndürür."""
    status = {}
    connectors = {
        "snowflake": "snowflake.connector",
        "mssql": "pymssql",
        "bigquery": "google.cloud.bigquery",
    }
    for name, module in connectors.items():
        try:
            __import__(module)
            status[name] = {"installed": True}
        except ImportError:
            status[name] = {
                "installed": False,
                "install_cmd": f"pip install {_INSTALL_CMDS.get(name, name)}",
            }
    return status


_INSTALL_CMDS = {
    "snowflake": "snowflake-connector-python>=3.0.0",
    "mssql": "pymssql>=2.2.0",
    "bigquery": "google-cloud-bigquery>=3.0.0 google-auth>=2.0.0",
}
