import os
import re
import uuid
import json
import shutil
import pandas as pd
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Imports from app modules
from app.database.manager import (
    init_metadata_db, add_uploaded_file, get_uploaded_files, 
    get_file_by_id, delete_uploaded_file, get_data_sources, add_data_source,
    update_source_schema, update_data_source, create_session, get_sessions, get_session_by_id,
    update_session, delete_session, add_chat_message, get_session_messages,
    clear_session_chat, get_data_source_by_id, update_source_status, update_source_labels,
    get_llm_config, update_llm_config
)

from app.database.connectors import test_connection, discover_schema
from app.agent.supervisor import SupervisorAgent
from app.agent.graph_supervisor import GraphSupervisorAgent
from app.core.logger import logger

# Initialize FastAPI
app = FastAPI(title="DeepBI Analytics Studio API", version="2.0.0")
from app.core.config import settings

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register modular routers (Faz 2 refactoring)
from app.routers.sessions import router as sessions_router
from app.routers.sources import router as sources_router
from app.routers.files import router as files_router
from app.routers.settings_router import router as settings_router
from app.routers.analytics import router as analytics_router
from app.routers.rag_router import router as rag_router

app.include_router(sessions_router)
app.include_router(sources_router)
app.include_router(files_router)
app.include_router(settings_router)
app.include_router(analytics_router)
app.include_router(rag_router)

# Ensure upload directory exists (relative to backend folder)
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), settings.upload_dir))
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize metadata DB (idempotent)
try:
    init_metadata_db()
except Exception as _e:
    logger.warning(f"metadata DB init failed: {str(_e)}")
class DBSourceStatusUpdate(BaseModel):
    is_active: bool

class DBSourceLabelsUpdate(BaseModel):
    labels: List[str]

class DBSourceCloneRequest(BaseModel):
    display_name: Optional[str] = None

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


class SessionCreate(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    active_source_id: Optional[str] = ""
    selected_sources: Optional[List[str]] = None
    relationships: Optional[List[Dict[str, Any]]] = None


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    active_source_id: Optional[str] = None
    selected_sources: Optional[List[str]] = None
    relationships: Optional[List[Dict[str, Any]]] = None


class ExportRequest(BaseModel):
    format: str
    chart_image: Optional[str] = None
    selected_rows: Optional[List[List[Any]]] = None


class LLMConfigRequest(BaseModel):
    apiKey: str
    baseUrl: str
    model: str



@app.get("/api/sessions")
def list_sessions():
    try:
        return get_sessions()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    try:
        session = get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Sohbet oturumu bulunamadı.")
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def read_root():
    return {"message": "DeepBI Analytics Studio API is running. Check /api/health for status."}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)



@app.get("/api/health")
def health_check():
    try:
        return {"status": "ok", "time": int(pd.Timestamp.now().timestamp())}
    except Exception:
        return {"status": "ok"}



@app.get("/api/settings")
def get_settings_endpoint():
    try:
        return get_llm_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/settings")
def update_settings_endpoint(req: LLMConfigRequest):
    try:
        success = update_llm_config(req.apiKey, req.baseUrl, req.model)
        if not success:
            raise HTTPException(status_code=500, detail="Ayarlar kaydedilemedi.")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/sessions")
def create_new_session(req: SessionCreate):
    try:
        import time
        s_id = req.id
        if not s_id:
            s_id = f"session-{int(time.time() * 1000)}"
        
        title = req.title or "Yeni Sohbet"
        active_source = req.active_source_id or ""
        
        result = create_session(s_id, title, active_source)
        
        # Save selected_sources and relationships if they were passed
        if req.selected_sources is not None or req.relationships is not None:
            sel_str = json.dumps(req.selected_sources) if req.selected_sources is not None else None
            rel_str = json.dumps(req.relationships) if req.relationships is not None else None
            update_session(s_id, selected_sources=sel_str, relationships=rel_str)
            
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/sessions/{session_id}")
def update_session_endpoint(session_id: str, req: SessionUpdate):
    try:
        sel_str = json.dumps(req.selected_sources) if req.selected_sources is not None else None
        rel_str = json.dumps(req.relationships) if req.relationships is not None else None
        
        success = update_session(session_id, req.title, req.active_source_id, sel_str, rel_str)
        if not success:
            raise HTTPException(status_code=404, detail="Oturum bulunamadı veya güncelleme yapılamadı.")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/sessions/{session_id}")
def delete_session_endpoint(session_id: str):
    try:
        success = delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/messages")
def get_session_chat_messages(session_id: str):
    try:
        return get_session_messages(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions/{session_id}/clear")
def clear_session_chat_endpoint(session_id: str):
    try:
        clear_session_chat(session_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CodeExecuteRequest(BaseModel):
    code: str
    code_language: str
    active_source_id: str
    source_ids: Optional[List[str]] = None
    relationships: Optional[List[Dict[str, Any]]] = None


@app.post("/api/sessions/{session_id}/messages/{message_id}/execute")
async def execute_edited_code(session_id: str, message_id: str, req: CodeExecuteRequest):
    try:
        from app.database.manager import get_db_connection
        
        if os.getenv("USE_LANGGRAPH", "true").lower() == "true":
            agent = GraphSupervisorAgent()
        else:
            agent = SupervisorAgent()
        resolved = agent._resolve_sources(req.active_source_id, req.source_ids or [], bool(req.source_ids))
        source_meta = resolved.get("meta")
        if not source_meta:
            raise HTTPException(status_code=404, detail="Kaynak bulunamadı.")
            
        is_sql = (req.code_language.lower() == "sql")
        
        success = False
        exec_result = None
        
        if is_sql:
            try:
                from app.core.sql_sanitizer import sanitize_and_validate_sql
                db_type = source_meta.get("db_type") if source_meta.get("type") == "database" else None
                safe_sql = sanitize_and_validate_sql(req.code, db_type=db_type)
                is_direct_db = (source_meta["type"] == "database")
                if is_direct_db:
                    exec_result = agent._execute_local_sql(safe_sql, source_meta)
                else:
                    # Auto-correct table names in edited SQL query for mixed-source (DuckDB) compatibility
                    corrected_sql = safe_sql
                    if source_meta.get("db_sources"):
                        # Determine file-mapped table names to avoid accidentally
                        # rewriting user-selected file tables to DB-prefixed names.
                        file_table_names = set()
                        if isinstance(source_meta.get("file_mappings"), dict):
                            file_table_names.update([k.lower() for k in source_meta.get("file_mappings").keys()])
                        if source_meta.get("alias") and source_meta.get("type") == "file":
                            file_table_names.add(source_meta.get("alias").lower())

                        for db in source_meta["db_sources"]:
                            db_id = db["id"]
                            for table_name in db.get("schema", {}).keys():
                                # Skip replacement if this table name is provided by an uploaded file
                                if table_name.lower() in file_table_names:
                                    continue
                                registered_name = f"{db_id}__{table_name}"
                                if registered_name not in corrected_sql:
                                    pattern = re.compile(rf'\b{re.escape(table_name)}\b', re.IGNORECASE)
                                    corrected_sql = pattern.sub(registered_name, corrected_sql)
                                    
                    # Only use file mappings when the resolved source actually includes file(s).
                    if source_meta.get("file_mappings"):
                        file_mappings = source_meta.get("file_mappings")
                    elif source_meta.get("type") == "file" and source_meta.get("file_path"):
                        file_mappings = {source_meta["alias"]: source_meta["file_path"]}
                    else:
                        file_mappings = {}
                    temp_dir = None
                    if source_meta.get("db_sources"):
                        db_files, db_schema, temp_dir = agent._materialize_db_sources(source_meta["db_sources"], max_rows=50000)
                        file_mappings = {**file_mappings, **db_files}
                        
                    try:
                        # Validate that SQL references only selected tables
                        import re as _re
                        refs = set()
                        for m in _re.finditer(r"\bfrom\s+([\w\"\'\.]+)|\bjoin\s+([\w\"\'\.]+)", corrected_sql, _re.IGNORECASE):
                            t = m.group(1) or m.group(2)
                            if not t:
                                continue
                            t_clean = t.strip().strip('"').strip("'")
                            t_clean = t_clean.split()[:1][0]
                            if "." in t_clean:
                                t_clean = t_clean.split(".")[-1]
                            refs.add(t_clean.lower())

                        allowed_tables = set([k.lower() for k in file_mappings.keys()])
                        if source_meta.get("db_sources"):
                            for db in source_meta.get("db_sources"):
                                db_id = db.get("id")
                                for tbl in db.get("schema", {}).keys():
                                    allowed_tables.add(f"{db_id}__{tbl}".lower())

                        unknown = [r for r in refs if r and r not in allowed_tables]
                        corrections = {}
                        ambiguous = []
                        if unknown:
                            import difflib as _difflib
                            allowed_map = {t.lower(): t for t in allowed_tables}
                            for u in unknown:
                                candidates = _difflib.get_close_matches(u, list(allowed_map.keys()), n=2, cutoff=0.66)
                                if len(candidates) == 1:
                                    corrections[u] = allowed_map[candidates[0]]
                                elif len(candidates) > 1:
                                    seq = _difflib.SequenceMatcher(None, u, candidates[0])
                                    score0 = seq.ratio()
                                    seq = _difflib.SequenceMatcher(None, u, candidates[1])
                                    score1 = seq.ratio()
                                    if abs(score0 - score1) > 0.15:
                                        corrections[u] = allowed_map[candidates[0] if score0 > score1 else candidates[1]]
                                    else:
                                        ambiguous.append(u)
                                else:
                                    ambiguous.append(u)

                            corrected_sql = corrected_sql
                            if corrections:
                                for src, tgt in corrections.items():
                                    try:
                                        corrected_sql = re.sub(rf"\b{re.escape(src)}\b", tgt, corrected_sql, flags=re.IGNORECASE)
                                    except Exception:
                                        pass
                                # replace for execution
                                corrected_sql_to_run = corrected_sql
                            else:
                                corrected_sql_to_run = corrected_sql

                            if ambiguous and not corrections:
                                raise Exception(f"Seçili kaynaklarda bulunmayan tablolar sorguda referans edilmiş: {ambiguous}. Mevcut tablolar: {sorted(list(allowed_tables))}")

                        else:
                            corrected_sql_to_run = corrected_sql

                        from app.core.duckdb_engine import execute_duckdb_query
                        exec_result = execute_duckdb_query(
                            corrected_sql_to_run,
                            file_mappings,
                            is_forecast=False,
                            is_anomaly=False,
                            is_correlation=False,
                            is_listing=True
                        )
                    finally:
                        if temp_dir and os.path.exists(temp_dir):
                            import shutil
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            
                success = True
            except Exception as e:
                exec_result = str(e)
        else:
            try:
                # For Python sandbox execution, only provide file mappings if the source is file-based
                if source_meta.get("file_mappings"):
                    file_mappings = dict(source_meta.get("file_mappings"))
                elif source_meta.get("type") == "file" and source_meta.get("file_path"):
                    file_mappings = {source_meta["alias"]: source_meta["file_path"]}
                else:
                    file_mappings = {}

                # Expose 'df' as a fallback pointing to the first/primary dataframe path to prevent failure on manual 'df' usage
                if file_mappings and "df" not in file_mappings:
                    first_key = list(file_mappings.keys())[0]
                    file_mappings["df"] = file_mappings[first_key]

                sandbox_result = agent.sandbox.run_pandas_code(req.code, file_mappings)
                if "error" in sandbox_result and sandbox_result["error"]:
                    success = False
                    exec_result = sandbox_result["error"]
                else:
                    success = True
                    exec_result = sandbox_result
            except Exception as e:
                exec_result = str(e)
                
        if success:
            conn = get_db_connection()
            cursor = conn.cursor()
            # Annotate text with auto-correction note if present
            final_summary = agent._generate_agent_summary("düzenlenmiş kod", exec_result, is_sql)
            auto_corr = exec_result.get("_auto_corrections") if isinstance(exec_result, dict) else None
            if auto_corr and isinstance(auto_corr, dict) and auto_corr.get("applied"):
                applied = auto_corr.get("applied")
                note = "\n\n(Not: Yerel otomatik düzeltme uygulandı: " + ", ".join([f"{k}→{v}" for k, v in applied.items()]) + ")"
                final_summary = final_summary + note

            cursor.execute("""
            UPDATE messages
            SET code = ?, data_json = ?, visualization_json = ?, auto_corrections_json = ?, error = NULL, text = ?
            WHERE id = ? AND session_id = ?
            """, (
                req.code,
                json.dumps(exec_result.get("data")),
                json.dumps(exec_result.get("visualization")),
                json.dumps(auto_corr) if auto_corr else None,
                final_summary,
                message_id,
                session_id
            ))
            conn.commit()
            conn.close()
            
            return {
                "success": True,
                "code": req.code,
                "data": exec_result.get("data"),
                "visualization": exec_result.get("visualization"),
                "final_response": final_summary,
                "auto_corrections": auto_corr
            }
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE messages
            SET code = ?, error = ?, data_json = NULL, visualization_json = NULL, auto_corrections_json = NULL, text = ?
            WHERE id = ? AND session_id = ?
            """, (
                req.code,
                str(exec_result),
                f"⚠️ Koddaki düzenlemeniz sonrasında hata oluştu:\n```\n{str(exec_result)}\n```",
                message_id,
                session_id
            ))
            conn.commit()
            conn.close()
            
            return {
                "success": False,
                "error": str(exec_result),
                "final_response": f"⚠️ Koddaki düzenlemeniz sonrasında hata oluştu:\n```\n{str(exec_result)}\n```"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sessions/{session_id}/messages/{message_id}/export")
def export_message_report(session_id: str, message_id: str, req: ExportRequest):
    try:
        import sqlite3
        from app.database.manager import DB_PATH, get_session_by_id
        from app.core.report_builder import build_excel_report, build_pdf_report
        
        format = req.format.lower()
        chart_image = req.chart_image
        
        # 1. Fetch message from DB
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM messages WHERE id = ? AND session_id = ?", (message_id, session_id))
        msg = cursor.fetchone()
        conn.close()
        
        if not msg:
            raise HTTPException(status_code=404, detail="Mesaj bulunamadı.")
            
        # Parse data JSON
        data_json_str = msg["data_json"]
        if not data_json_str and format in ("excel", "csv"):
            raise HTTPException(status_code=400, detail="Bu mesaj dışa aktarılacak veri tablosu içermiyor.")
            
        data = json.loads(data_json_str) if data_json_str else {}
        columns = data.get("columns", [])
        rows = data.get("rows", [])
        
        # Filter to selected rows if provided by frontend custom grid
        if req.selected_rows is not None and len(req.selected_rows) > 0:
            rows = req.selected_rows
        
        # Get session title
        session = get_session_by_id(session_id)
        session_title = session["title"] if session else "DeepBI Sohbet"
        
        if format == "excel":
            buffer = build_excel_report(columns, rows, title=f"DeepBI Analiz Sonucu - {session_title}", chart_image=chart_image)
            excel_data = buffer.getvalue()
            return Response(
                content=excel_data,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=analiz_raporu_{message_id[:6]}.xlsx"}
            )
            
        elif format == "pdf":
            # Extract query details
            question_text = "Seçilen Analiz Metriği"
            try:
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT text FROM messages WHERE session_id = ? AND created_at < ? AND role = 'user' ORDER BY created_at DESC LIMIT 1",
                    (session_id, msg["created_at"])
                )
                prev_msg = cursor.fetchone()
                conn.close()
                if prev_msg:
                    question_text = prev_msg["text"]
            except Exception:
                pass
                
            buffer = build_pdf_report(
                question=question_text,
                summary_text=msg["text"] or "",
                code=msg["code"] or "",
                code_language=msg["code_language"] or "python",
                columns=columns,
                rows=rows,
                session_title=session_title,
                chart_image=chart_image
            )
            pdf_data = buffer.getvalue()
            return Response(
                content=pdf_data,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename=analiz_raporu_{message_id[:6]}.pdf"}
            )
            
        elif format == "csv":
            import io
            import csv
            
            output = io.StringIO()
            output.write('\ufeff')  # UTF-8 BOM
            writer = csv.writer(output, delimiter=';')
            writer.writerow(columns)
            for row in rows:
                writer.writerow(row)
                
            csv_data = output.getvalue().encode('utf-8')
            return Response(
                content=csv_data,
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=analiz_raporu_{message_id[:6]}.csv"}
            )
            
        else:
            raise HTTPException(status_code=400, detail="Geçersiz format. Lütfen 'pdf', 'excel' veya 'csv' seçin.")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sources")
def list_sources():
    try:
        return get_data_sources()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sources/{source_id}")
def get_source(source_id: str):
    source = get_data_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Kaynak bulunamadı.")
    return source


@app.post("/api/sources/test-connection")
def test_source_connection(req: DBTestRequest):
    """Tests a database connection without saving it."""
    success, message = test_connection(req.type, req.connection_details)
    return {"success": success, "message": message}


@app.post("/api/sources/discover-schema")
def discover_source_schema(req: DBTestRequest):
    """Automatically discovers the schema of a database."""
    try:
        schema = discover_schema(req.type, req.connection_details)
        return {"success": True, "schema": schema, "table_count": len(schema)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/sources")
def create_source(source: DBSourceCreate):
    """Adds a new data source with auto schema discovery."""
    import uuid
    source_id = f"db_{uuid.uuid4().hex[:8]}"
    try:
        # Auto-discover schema from the live connection
        schema = discover_schema(source.type, source.connection_details)
    except Exception:
        schema = {}  # gracefully continue with empty schema
    
    # Mask password in stored details for display safety
    safe_details = dict(source.connection_details)
    # Password is stored as-is in this phase (use Vault in production)
    
    try:
        result = add_data_source(
            source_id, source.type, source.display_name,
            safe_details, schema, source.labels, source.is_active if source.is_active is not None else True
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/sources/{source_id}")
def update_source(source_id: str, source: DBSourceUpdate):
    """Updates display name and connection details, and refreshes discovered schema."""
    sources = get_data_sources()
    target = next((s for s in sources if s["id"] == source_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Kaynak bulunamadı.")
    
    # Try discovering the schema with the updated details
    try:
        schema = discover_schema(target["type"], source.connection_details)
    except Exception:
        schema = target["schema"]  # gracefully fallback to current cached schema
        
    labels = source.labels if source.labels is not None else target.get("labels", [])
    try:
        success = update_data_source(
            source_id, source.display_name,
            source.connection_details, schema, labels
        )
        if not success:
            raise HTTPException(status_code=400, detail="Güncelleme başarısız oldu.")
        return {
            "id": source_id,
            "type": target["type"],
            "display_name": source.display_name,
            "connection_details": source.connection_details,
            "schema": schema,
            "labels": labels,
            "is_active": target.get("is_active", True)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/sources/{source_id}/status")
def update_source_status_endpoint(source_id: str, payload: DBSourceStatusUpdate):
    success = update_source_status(source_id, payload.is_active)
    if not success:
        raise HTTPException(status_code=404, detail="Kaynak bulunamadı.")
    return {"success": True, "is_active": payload.is_active}


@app.put("/api/sources/{source_id}/labels")
def update_source_labels_endpoint(source_id: str, payload: DBSourceLabelsUpdate):
    success = update_source_labels(source_id, payload.labels)
    if not success:
        raise HTTPException(status_code=404, detail="Kaynak bulunamadı.")
    return {"success": True, "labels": payload.labels}


@app.post("/api/sources/{source_id}/clone")
def clone_source(source_id: str, payload: DBSourceCloneRequest):
    import uuid
    source = get_data_source_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Kaynak bulunamadı.")

    new_id = f"db_{uuid.uuid4().hex[:8]}"
    new_display = payload.display_name or f"{source['display_name']} (Kopya)"
    result = add_data_source(
        new_id,
        source["type"],
        new_display,
        source["connection_details"],
        source.get("schema", {}),
        source.get("labels", []),
        source.get("is_active", True)
    )
    return result


@app.post("/api/sources/{source_id}/snapshot")
def take_source_snapshot(source_id: str):
    """Creates a local offline SQLite snapshot database from a remote source."""
    from app.database.snapshots import create_database_snapshot
    try:
        result = create_database_snapshot(source_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Snapshot oluşturulurken hata oluştu: {str(e)}")


@app.get("/api/sources/{source_id}/snapshot/stream")
def stream_source_snapshot(source_id: str, tables: Optional[str] = None):
    """Creates a local offline SQLite snapshot and streams detailed table-by-table progress."""
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


@app.put("/api/sources/{source_id}/refresh-schema")
def refresh_schema(source_id: str):
    """Refreshes schema cache for an existing data source."""
    sources = get_data_sources()
    target = next((s for s in sources if s["id"] == source_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Kaynak bulunamadı.")
    try:
        schema = discover_schema(target["type"], target["connection_details"])
        update_source_schema(source_id, schema)
        return {"success": True, "schema": schema, "table_count": len(schema)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/sources/{source_id}")
def delete_source(source_id: str):
    """Deletes a data source."""
    import sqlite3 as sq
    from app.database.manager import DB_PATH
    conn = sq.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    if affected == 0:
        raise HTTPException(status_code=404, detail="Kaynak bulunamadı.")
    return {"success": True}

@app.get("/api/files")
def list_files():
    try:
        return get_uploaded_files()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/{file_id}/preview")
def get_file_preview(file_id: str):
    """
    Returns the column schemas and the first 20 rows of an uploaded file.
    """
    try:
        file_meta = get_file_by_id(file_id)
        if not file_meta:
            raise HTTPException(status_code=404, detail="Dosya bulunamadı.")
            
        save_path = file_meta["file_path"]
        suffix = os.path.splitext(save_path)[1].lower()
        
        if not os.path.exists(save_path):
            raise HTTPException(status_code=404, detail="Dosya sunucu diskinde bulunamadı.")
            
        if suffix in [".xlsx", ".xls"]:
            df = pd.read_excel(save_path)
        else:
            sep = '\t' if suffix == '.tsv' else ','
            df = pd.read_csv(save_path, sep=sep)
            
        df_preview = df.head(20).fillna("")
        preview_data = {
            "columns": list(df_preview.columns),
            "rows": df_preview.values.tolist(),
            "row_count": len(df),
            "alias": file_meta["alias"],
            "id": file_meta["id"],
            "schema": file_meta["schema"]
        }
        return {"success": True, "preview": preview_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ön izleme oluşturulamadı: {str(e)}")

@app.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    alias: str = Form(...)
):
    """
    Handles CSV and Excel file uploads.
    Extracts the schema (column names and inferred data types)
    and returns a preview of the first 20 rows along with metadata.
    """
    # Verify file suffix
    filename = file.filename
    suffix = os.path.splitext(filename)[1].lower()
    if suffix not in [".csv", ".tsv", ".xlsx", ".xls"]:
        raise HTTPException(status_code=400, detail="Desteklenmeyen dosya formatı. Yalnızca Excel veya CSV yükleyebilirsiniz.")
        
    # Generate clean alias (alphanumeric and underscores only)
    clean_alias = re.sub(r'[^a-zA-Z0-9_]', '', alias.strip().replace(" ", "_"))
    if not clean_alias:
        clean_alias = f"file_{uuid.uuid4().hex[:6]}"
        
    # Generate unique filepath
    file_id = str(uuid.uuid4())
    save_path = os.path.join(UPLOAD_DIR, f"{file_id}{suffix}")
    
    # Save file on disk
    try:
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dosya sunucuya yazılamadı: {str(e)}")
        
    # Load with Pandas to extract metadata, row count, and column schemas
    try:
        if suffix in [".xlsx", ".xls"]:
            # Load with openpyxl
            df = pd.read_excel(save_path)
        else:
            sep = '\t' if suffix == '.tsv' else ','
            df = pd.read_csv(save_path, sep=sep)
            
        row_count = len(df)
        
        # Infer Schema
        schema = {}
        for col in df.columns:
            dtype = str(df[col].dtype)
            if "int" in dtype or "float" in dtype:
                schema[col] = "Sayı"
            elif "bool" in dtype:
                schema[col] = "Boole"
            elif "datetime" in dtype or "date" in dtype:
                schema[col] = "Tarih"
            else:
                schema[col] = "Metin"
                
        # Register in Metadata DB
        file_meta = add_uploaded_file(
            file_id=file_id,
            alias=clean_alias,
            original_name=filename,
            file_path=save_path,
            row_count=row_count,
            schema=schema
        )
        
        # Build first 20 rows preview table
        df_preview = df.head(20).fillna("") # Replace NaN with empty string
        preview_data = {
            "columns": list(df_preview.columns),
            "rows": df_preview.values.tolist(),
            "row_count": row_count
        }
        
        return {
            "success": True,
            "metadata": file_meta,
            "preview": preview_data
        }
        
    except ValueError as e:
        # Alias already exists or database constraint failed
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Generic parsing error
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=422, detail=f"Dosya ayrıştırılamadı. Geçerli bir Excel veya CSV olduğundan emin olun. Hata: {str(e)}")

@app.delete("/api/files/{file_id}")
def delete_file(file_id: str):
    success = delete_uploaded_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail="Dosya bulunamadı veya silinemedi.")
    return {"success": True, "message": "Dosya başarıyla silindi."}

# WebSocket Chat Connection
@app.post("/api/sessions/{session_id}/messages/{message_id}/feedback")
def update_message_feedback(session_id: str, message_id: str, payload: Dict[str, Any]):
    try:
        import sqlite3
        from app.database.manager import DB_PATH
        from app.agent.rag import update_feedback
        
        feedback_type = payload.get("type") # "positive" or "negative" or "neutral"
        if not feedback_type:
            raise HTTPException(status_code=400, detail="Feedback type is required.")
            
        # Find the user question immediately preceding this agent message
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get agent message timestamp
        cursor.execute("SELECT created_at FROM messages WHERE id = ? AND session_id = ?", (message_id, session_id))
        msg = cursor.fetchone()
        if not msg:
            conn.close()
            raise HTTPException(status_code=404, detail="Agent message not found.")
            
        # Get user message before it
        cursor.execute(
            "SELECT text FROM messages WHERE session_id = ? AND created_at < ? AND role = 'user' ORDER BY created_at DESC LIMIT 1",
            (session_id, msg["created_at"])
        )
        prev_msg = cursor.fetchone()
        conn.close()
        
        if prev_msg and prev_msg["text"]:
            question_text = prev_msg["text"]
            update_feedback(question_text, feedback_type)
            return {"success": True, "message": "Feedback successfully updated in semantic RAG memory."}
        else:
            raise HTTPException(status_code=400, detail="No preceding user question found to attach feedback to.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket chat connection accepted.")
    
    try:
        while True:
            # Await message from client
            raw_data = await websocket.receive_text()
            payload = json.loads(raw_data)
            
            user_text = payload.get("text", "")
            active_source_id = payload.get("source_id", "")
            source_ids = payload.get("source_ids", [])
            relationships = payload.get("relationships", [])
            session_id = payload.get("session_id")
            api_key = payload.get("api_key")
            base_url = payload.get("base_url")
            model = payload.get("model")
            
            # Fallback to database LLM configs if not provided or empty from client
            if not api_key or not base_url or not model:
                db_config = get_llm_config()
                api_key = api_key or db_config.get("apiKey")
                base_url = base_url or db_config.get("baseUrl")
                model = model or db_config.get("model")

            
            import time
            if not session_id:
                session_id = f"session-{int(time.time() * 1000)}"
                create_session(session_id, user_text[:24] + ("..." if len(user_text) > 24 else ""), active_source_id)
            
            # Save User Message to Database
            user_msg_id = payload.get("user_msg_id") or f"user-{int(time.time() * 1000)}"
            add_chat_message(
                session_id=session_id,
                message_id=user_msg_id,
                role="user",
                text=user_text
            )
            
            # Setup supervisor agent with client configs if provided
            if os.getenv("USE_LANGGRAPH", "true").lower() == "true":
                agent = GraphSupervisorAgent(api_key=api_key, base_url=base_url, model=model)
            else:
                agent = SupervisorAgent(api_key=api_key, base_url=base_url, model=model)
            
            # Define WebSocket callback for sending steps and tracking status history
            status_history = ["Bağlantı kuruluyor..."]
            async def ws_callback(data: Dict[str, Any]):
                if data.get("type") == "status":
                    status_history.append(data.get("message"))
                await websocket.send_json(data)
                
            # Process query — 120 saniye hard timeout
            try:
                import asyncio as _asyncio
                async with _asyncio.timeout(120):
                    result = await agent.process_query(
                        user_question=user_text,
                        active_source_id=active_source_id,
                        source_ids=source_ids,
                        relationships=relationships,
                        ws_callback=ws_callback
                    )
            except _asyncio.TimeoutError:
                logger.warning(f"WebSocket query timed out after 120s for session: {session_id}")
                await websocket.send_json({"type": "error", "message": "Sorgu zaman aşımına uğradı (120s). Lütfen sorgunuzu basitleştirin veya daha küçük bir veri kümesi seçin."})
                await websocket.send_json({"type": "done", "final_response": "⚠️ Sorgu zaman aşımına uğradı (120 saniye). Lütfen tekrar deneyin."})
                continue
            
            agent_msg_id = payload.get("agent_msg_id") or f"agent-{int(time.time() * 1000)}"
            
            # Send final results and done signal
            if result.get("success"):
                # If the backend applied automatic corrections, annotate the final_response for the UI
                final_resp = result.get("final_response")
                auto_corr = result.get("auto_corrections")
                if auto_corr and isinstance(auto_corr, dict) and auto_corr.get("applied"):
                    applied = auto_corr.get("applied")
                    note = "\n\n(Not: Yerel otomatik düzeltme uygulandı: " + ", ".join([f"{k}→{v}" for k, v in applied.items()]) + ")"
                    final_resp = (final_resp or "") + note

                await websocket.send_json({
                    "type": "result",
                    "data": result.get("data"),
                    "visualization": result.get("visualization"),
                    "auto_corrections": auto_corr
                })
                await websocket.send_json({
                    "type": "done",
                    "final_response": final_resp
                })
                
                # Save successful agent response to database
                generated = result.get("generated_code") or ""
                code_lang = "sql" if re.match(r'^\s*(SELECT|WITH\s|INSERT\s|UPDATE\s|DELETE\s|CREATE\s|DROP\s)', generated, re.IGNORECASE) else "python"
                add_chat_message(
                    session_id=session_id,
                    message_id=agent_msg_id,
                    role="agent",
                    text=final_resp,
                    status_history=status_history,
                    code=result.get("generated_code"),
                    code_language=code_lang,
                    data=result.get("data"),
                    visualization=result.get("visualization")
                    ,
                    auto_corrections=auto_corr
                )
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": result.get("error", "Sorgulama başarısız oldu.")
                })
                await websocket.send_json({
                    "type": "done",
                    "final_response": result.get("final_response", "⚠️ Sorgulama sırasında bir hata oluştu.")
                })
                
                # Save failed agent response to database
                generated = result.get("generated_code") or ""
                code_lang = "sql" if re.match(r'^\s*(SELECT|WITH\s|INSERT\s|UPDATE\s|DELETE\s|CREATE\s|DROP\s)', generated, re.IGNORECASE) else "python"
                add_chat_message(
                    session_id=session_id,
                    message_id=agent_msg_id,
                    role="agent",
                    text=result.get("final_response", "⚠️ Sorgulama sırasında bir hata oluştu."),
                    status_history=status_history,
                    code=result.get("generated_code"),
                    code_language=code_lang,
                    error=result.get("error")
                )
                
    except WebSocketDisconnect:
        logger.info("WebSocket chat connection closed by client.")
    except Exception as e:
        logger.error(f"Critical WebSocket error: {str(e)}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Kritik Sistem Hatası: {str(e)}"
            })
        except Exception:
            pass

@app.get("/api/sources/{source_id}/semantic")
def get_source_semantic(source_id: str):
    try:
        from app.database.manager import get_semantic_mapping
        return get_semantic_mapping(source_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sources/{source_id}/semantic")
def update_source_semantic(source_id: str, mapping: Dict[str, Any]):
    try:
        from app.database.manager import save_semantic_mapping
        success = save_semantic_mapping(source_id, mapping)
        if not success:
            raise HTTPException(status_code=400, detail="Semantik tanımlar kaydedilemedi.")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
