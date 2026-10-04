"""
app/routers/sessions.py
Chat oturumu CRUD endpoint'leri.
"""
import os
import re
import json
import asyncio
import sqlite3
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.core.audit import audit
from app.core.auth import get_allowed_source_ids, get_current_user
from app.database.manager import (
    create_session, get_sessions, get_session_by_id,
    update_session, delete_session, add_chat_message,
    get_session_messages, clear_session_chat, get_db_connection, DB_PATH,
)
from app.core.logger import logger
from app.agent.supervisor import SupervisorAgent
from app.agent.graph_supervisor import GraphSupervisorAgent
from app.core.report_builder import build_excel_report, build_pdf_report
from app.agent.rag import update_feedback

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


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


def _verify_ownership(session: Optional[Dict[str, Any]], user: Dict[str, Any]) -> Dict[str, Any]:
    """Oturum kullanıcıya ait mi kontrol eder (admin herkese erişir)."""
    if not session:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
    if user.get("role") != "admin" and session.get("user_id") not in (user["id"], None):
        raise HTTPException(status_code=403, detail="SESSION_FORBIDDEN")
    return session


def _check_source_permission(user: Dict[str, Any], requested_ids: List[str]) -> None:
    """Kullanıcının yetkisi olmayan kaynakları reddeder (admin → tümü)."""
    allowed = get_allowed_source_ids(user)
    if allowed is None:
        return
    denied = [sid for sid in requested_ids if sid and sid not in set(allowed)]
    if denied:
        raise HTTPException(status_code=403, detail=f"SOURCE_FORBIDDEN: {denied}")


@router.get("")
def list_sessions(limit: int = 100, offset: int = 0, user: dict = Depends(get_current_user)):
    try:
        # Admin tüm oturumları, normal kullanıcı sadece kendi oturumlarını görür
        return get_sessions(
            user_id=None if user.get("role") == "admin" else user["id"],
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(f"list_sessions error: {e}")
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")


@router.get("/search")
def search_sessions(q: str = "", user: dict = Depends(get_current_user)):
    """Oturum başlıkları ve mesaj içeriklerinde arama yapar."""
    try:
        import sqlite3
        from app.database.manager import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = f"%{q}%"
        if user.get("role") == "admin":
            cursor.execute(
                """
                SELECT DISTINCT s.id, s.title, s.active_source_id, s.created_at
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                WHERE s.title LIKE ? OR m.text LIKE ?
                ORDER BY s.created_at DESC
                LIMIT 50
                """,
                (query, query),
            )
        else:
            cursor.execute(
                """
                SELECT DISTINCT s.id, s.title, s.active_source_id, s.created_at
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                WHERE (s.title LIKE ? OR m.text LIKE ?) AND s.user_id = ?
                ORDER BY s.created_at DESC
                LIMIT 50
                """,
                (query, query, user["id"]),
            )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"search_sessions error: {e}")
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")


@router.get("/{session_id}")
def get_session(session_id: str, user: dict = Depends(get_current_user)):
    try:
        session = get_session_by_id(session_id)
        return _verify_ownership(session, user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("500 - %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")


@router.post("")
def create_new_session(req: SessionCreate, user: dict = Depends(get_current_user)):
    try:
        import time
        s_id = req.id or f"session-{int(time.time() * 1000)}"
        title = req.title or "Yeni Sohbet"
        active_source = req.active_source_id or ""
        _check_source_permission(user, [active_source] + (req.selected_sources or []))

        result = create_session(s_id, title, active_source, user_id=user["id"])
        audit("session.create", target=s_id, user=user)

        if req.selected_sources is not None or req.relationships is not None:
            sel_str = json.dumps(req.selected_sources) if req.selected_sources is not None else None
            rel_str = json.dumps(req.relationships) if req.relationships is not None else None
            update_session(s_id, selected_sources=sel_str, relationships=rel_str)

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{session_id}")
def update_session_endpoint(session_id: str, req: SessionUpdate, user: dict = Depends(get_current_user)):
    try:
        _verify_ownership(get_session_by_id(session_id), user)
        sel_str = json.dumps(req.selected_sources) if req.selected_sources is not None else None
        rel_str = json.dumps(req.relationships) if req.relationships is not None else None

        success = update_session(session_id, req.title, req.active_source_id, sel_str, rel_str)
        if not success:
            raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("500 - %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")


@router.delete("/{session_id}")
def delete_session_endpoint(session_id: str, user: dict = Depends(get_current_user)):
    try:
        _verify_ownership(get_session_by_id(session_id), user)
        audit("session.delete", target=session_id, user=user)
        success = delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("500 - %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")


@router.get("/{session_id}/messages")
def get_session_chat_messages(session_id: str, limit: int = 500, user: dict = Depends(get_current_user)):
    try:
        _verify_ownership(get_session_by_id(session_id), user)
        return get_session_messages(session_id, limit=limit)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("500 - %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")


@router.post("/{session_id}/clear")
def clear_session_chat_endpoint(session_id: str, user: dict = Depends(get_current_user)):
    try:
        _verify_ownership(get_session_by_id(session_id), user)
        clear_session_chat(session_id)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("500 - %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")


class CodeExecuteRequest(BaseModel):
    code: str
    code_language: str
    active_source_id: str
    source_ids: Optional[List[str]] = None
    relationships: Optional[List[Dict[str, Any]]] = None


class ExportRequest(BaseModel):
    format: str
    chart_image: Optional[str] = None
    selected_rows: Optional[List[List[Any]]] = None


@router.post("/{session_id}/messages/{message_id}/execute")
async def execute_edited_code(session_id: str, message_id: str, req: CodeExecuteRequest, user: dict = Depends(get_current_user)):
    try:
        _verify_ownership(get_session_by_id(session_id), user)
        _check_source_permission(user, [req.active_source_id] + (req.source_ids or []))
        if os.getenv("USE_LANGGRAPH", "true").lower() == "true":
            agent = GraphSupervisorAgent()
        else:
            agent = SupervisorAgent()
        # Ağ/DB/sandbox çağrıları event loop'u bloklamasın diye thread'de çalışır.
        resolved = await asyncio.to_thread(
            agent._resolve_sources, req.active_source_id, req.source_ids or [], bool(req.source_ids)
        )
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
                    exec_result = await asyncio.to_thread(agent._execute_local_sql, safe_sql, source_meta)
                else:
                    corrected_sql = safe_sql
                    if source_meta.get("db_sources"):
                        file_table_names = set()
                        if isinstance(source_meta.get("file_mappings"), dict):
                            file_table_names.update([k.lower() for k in source_meta.get("file_mappings").keys()])
                        if source_meta.get("alias") and source_meta.get("type") == "file":
                            file_table_names.add(source_meta.get("alias").lower())

                        for db in source_meta["db_sources"]:
                            db_id = db["id"]
                            for table_name in db.get("schema", {}).keys():
                                if table_name.lower() in file_table_names:
                                    continue
                                registered_name = f"{db_id}__{table_name}"
                                if registered_name not in corrected_sql:
                                    pattern = re.compile(rf'\b{re.escape(table_name)}\b', re.IGNORECASE)
                                    corrected_sql = pattern.sub(registered_name, corrected_sql)

                    if source_meta.get("file_mappings"):
                        file_mappings = source_meta.get("file_mappings")
                    elif source_meta.get("type") == "file" and source_meta.get("file_path"):
                        file_mappings = {source_meta["alias"]: source_meta["file_path"]}
                    else:
                        file_mappings = {}
                    temp_dir = None
                    if source_meta.get("db_sources"):
                        db_files, db_schema, temp_dir = await asyncio.to_thread(
                            agent._materialize_db_sources, source_meta["db_sources"], max_rows=50000
                        )
                        file_mappings = {**file_mappings, **db_files}

                    try:
                        allowed_tables = set([k.lower() for k in file_mappings.keys()])
                        if source_meta.get("db_sources"):
                            for db in source_meta.get("db_sources"):
                                db_id = db.get("id")
                                for tbl in db.get("schema", {}).keys():
                                    allowed_tables.add(f"{db_id}__{tbl}".lower())

                        from app.core.table_resolver import resolve_unknown_tables
                        corrected_sql, corrections, ambiguous, unknown = resolve_unknown_tables(corrected_sql, allowed_tables)

                        if unknown and not corrections:
                            unresolved = ambiguous or unknown
                            raise Exception(
                                f"Seçili kaynaklarda bulunmayan veya belirsiz tablolar sorguda referans edilmiş: "
                                f"{unresolved}. Mevcut tablolar: {sorted(list(allowed_tables))}"
                            )

                        from app.core.duckdb_engine import execute_duckdb_query
                        exec_result = await asyncio.to_thread(
                            execute_duckdb_query,
                            corrected_sql,
                            file_mappings,
                            False,   # is_forecast
                            False,   # is_anomaly
                            False,   # is_correlation
                            True,    # is_listing
                            False,   # is_clustering
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
                if source_meta.get("file_mappings"):
                    file_mappings = dict(source_meta.get("file_mappings"))
                elif source_meta.get("type") == "file" and source_meta.get("file_path"):
                    file_mappings = {source_meta["alias"]: source_meta["file_path"]}
                else:
                    file_mappings = {}

                if file_mappings and "df" not in file_mappings:
                    first_key = list(file_mappings.keys())[0]
                    file_mappings["df"] = file_mappings[first_key]

                sandbox_result = await asyncio.to_thread(agent.sandbox.run_pandas_code, req.code, file_mappings)
                if "error" in sandbox_result and sandbox_result["error"]:
                    success = False
                    exec_result = sandbox_result["error"]
                else:
                    success = True
                    exec_result = sandbox_result
            except Exception as e:
                exec_result = str(e)

        if success:
            final_summary = agent._generate_agent_summary("düzenlenmiş kod", exec_result, is_sql)
            auto_corr = exec_result.get("_auto_corrections") if isinstance(exec_result, dict) else None
            if auto_corr and isinstance(auto_corr, dict) and auto_corr.get("applied"):
                applied = auto_corr.get("applied")
                note = "\n\n(Not: Yerel otomatik düzeltme uygulandı: " + ", ".join([f"{k}→{v}" for k, v in applied.items()]) + ")"
                final_summary = final_summary + note

            def _save_success():
                conn = get_db_connection()
                cursor = conn.cursor()
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

            await asyncio.to_thread(_save_success)
            audit("code.execute", target=message_id, detail={
                "language": req.code_language, "success": True, "session": session_id,
            }, user=user)

            return {
                "success": True,
                "code": req.code,
                "data": exec_result.get("data"),
                "visualization": exec_result.get("visualization"),
                "final_response": final_summary,
                "auto_corrections": auto_corr
            }
        else:
            error_text = f"⚠️ Koddaki düzenlemeniz sonrasında hata oluştu:\n```\n{str(exec_result)}\n```"

            def _save_failure():
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE messages
                SET code = ?, error = ?, data_json = NULL, visualization_json = NULL, auto_corrections_json = NULL, text = ?
                WHERE id = ? AND session_id = ?
                """, (
                    req.code,
                    str(exec_result),
                    error_text,
                    message_id,
                    session_id
                ))
                conn.commit()
                conn.close()

            await asyncio.to_thread(_save_failure)
            audit("code.execute", target=message_id, detail={
                "language": req.code_language, "success": False, "session": session_id,
            }, user=user)

            return {
                "success": False,
                "error": str(exec_result),
                "final_response": error_text
            }

    except Exception as e:
        logger.error(f"execute_edited_code error: {e}")
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")


@router.post("/{session_id}/messages/{message_id}/export")
def export_message_report(session_id: str, message_id: str, req: ExportRequest, user: dict = Depends(get_current_user)):
    try:
        _verify_ownership(get_session_by_id(session_id), user)
        format = req.format.lower()
        chart_image = req.chart_image

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM messages WHERE id = ? AND session_id = ?", (message_id, session_id))
        msg = cursor.fetchone()
        conn.close()

        if not msg:
            raise HTTPException(status_code=404, detail="Mesaj bulunamadı.")

        data_json_str = msg["data_json"]
        if not data_json_str and format in ("excel", "csv"):
            raise HTTPException(status_code=400, detail="Bu mesaj dışa aktarılacak veri tablosu içermiyor.")

        data = json.loads(data_json_str) if data_json_str else {}
        columns = data.get("columns", [])
        rows = data.get("rows", [])

        if req.selected_rows is not None and len(req.selected_rows) > 0:
            rows = req.selected_rows

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
            output.write('\ufeff')
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
        logger.error(f"export_message_report error: {e}")
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")


@router.post("/{session_id}/messages/{message_id}/feedback")
def update_message_feedback_endpoint(session_id: str, message_id: str, payload: Dict[str, Any], user: dict = Depends(get_current_user)):
    try:
        _verify_ownership(get_session_by_id(session_id), user)
        feedback_type = payload.get("type")
        if not feedback_type:
            raise HTTPException(status_code=400, detail="Feedback type is required.")

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT created_at FROM messages WHERE id = ? AND session_id = ?", (message_id, session_id))
        msg = cursor.fetchone()
        if not msg:
            conn.close()
            raise HTTPException(status_code=404, detail="Agent message not found.")

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_message_feedback error: {e}")
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")

