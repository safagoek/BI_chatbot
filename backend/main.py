import os
import re
import json
import asyncio
import uuid
import pandas as pd
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logger import logger, request_id_var
from app.core.audit import audit, prune_old_entries
from app.core.auth import decode_token, get_allowed_source_ids
from app.database.manager import (
    init_metadata_db, create_session, add_chat_message, get_llm_config, seed_main_admin
)
from app.agent.supervisor import SupervisorAgent
from app.agent.graph_supervisor import GraphSupervisorAgent

# Modular routers
from app.routers.sessions import router as sessions_router
from app.routers.sources import router as sources_router
from app.routers.files import router as files_router
from app.routers.settings_router import router as settings_router
from app.routers.analytics import router as analytics_router
from app.routers.rag_router import router as rag_router
from app.routers.auth_router import router as auth_router
from app.routers.admin_router import router as admin_router
from app.routers.mcp_router import router as mcp_router
from app.routers.saves_router import router as saves_router
from app.routers.schedules_router import router as schedules_router

# Initialize FastAPI
app = FastAPI(title="DeepBI Analytics Studio API", version="2.0.0")

# Register routers
app.include_router(sessions_router)
app.include_router(sources_router)
app.include_router(files_router)
app.include_router(settings_router)
app.include_router(analytics_router)
app.include_router(rag_router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(mcp_router)
app.include_router(saves_router)
app.include_router(schedules_router)

# Ensure upload directory exists
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), settings.upload_dir))
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize metadata DB (idempotent) + seed main admin on first run
try:
    from app.database.manager import _ensure_feature_tables
    init_metadata_db()
    seed_main_admin()
    _ensure_feature_tables()
    prune_old_entries()
except Exception as _e:
    logger.warning(f"metadata DB init failed: {str(_e)}")


# JWT ile kimliklenen path'ler dışında auth gerektirmeyen uçlar
_PUBLIC_API_PATHS = {"/api/auth/login", "/api/health"}


@app.middleware("http")
async def token_auth_middleware(request, call_next):
    """/api/* isteklerinde kimlik doğrulama: JWT (Bearer) veya APP_TOKEN (X-API-Token).
    Rol kontrolü endpoint'lerde (require_admin) yapılır."""
    # Correlation ID: gelen X-Request-ID'yi al ya da üret; tüm log kayıtlarına ve
    # yanıt başlığına yansır — üretimde bir hatayı istekle ilişkilendirmeyi sağlar.
    rid = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
    request_id_var.set(rid)

    # CORS preflight istekleri (OPTIONS) Authorization taşımaz — bırakın geçsin,
    # aksi halde tarayıcı tüm gerçek istekleri CORS hatasıyla bloklar.
    if request.method == "OPTIONS":
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    path = request.url.path
    if path.startswith("/api/") and path not in _PUBLIC_API_PATHS:
        provided = request.headers.get("Authorization", "")
        if provided.startswith("Bearer "):
            provided = provided[len("Bearer "):]
        else:
            provided = request.headers.get("X-API-Token", "")
        valid = False
        if provided:
            if settings.app_token and provided == settings.app_token:
                valid = True
            elif decode_token(provided):
                valid = True
        if not valid:
            resp = JSONResponse(status_code=401, content={"detail": "UNAUTHORIZED"})
            resp.headers["X-Request-ID"] = rid
            return resp
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    """Yakalanmayan istisnalar: istemciye tek tip zarf, log'a tam detay (request ID ile)."""
    rid = request_id_var.get()
    logger.error("UNHANDLED [req:%s] %s %s: %s", rid, request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "INTERNAL_ERROR"}, headers={"X-Request-ID": rid})


# Zamanlanmış rapor scheduler'ı
from app.core.scheduler import start_scheduler
start_scheduler()

# CORS middleware'i auth'tan SONRA ekliyoruz → stack'te en dışta çalışır;
# böylece preflight ve 401 yanıtları dahil her yanıt CORS başlıkları taşır.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket chat connection accepted.")

    try:
        while True:
            # Await message from client
            raw_data = await websocket.receive_text()
            payload = json.loads(raw_data)

            # Kimlik doğrulama: JWT oturumu veya makine APP_TOKEN'ı
            ws_token = payload.get("token") or ""
            ws_user: Optional[Dict[str, Any]] = None
            if settings.app_token and ws_token == settings.app_token:
                ws_user = {"id": "machine", "username": "machine", "role": "admin"}
            elif ws_token:
                ws_payload = decode_token(ws_token)
                if ws_payload:
                    from app.database.manager import get_user_by_id
                    db_user = get_user_by_id(ws_payload.get("sub", ""))
                    if db_user and db_user.get("is_active"):
                        ws_user = db_user
            if ws_user is None:
                await websocket.send_json({"type": "error", "message": "UNAUTHORIZED: oturum geçersiz. Lütfen tekrar giriş yapın."})
                await websocket.close(code=4401)
                return

            user_text = payload.get("text", "")
            active_source_id = payload.get("source_id", "")
            source_ids = payload.get("source_ids", []) or []
            relationships = payload.get("relationships", [])

            # Kullanıcı bazlı kaynak yetkisi zorlaması (admin → tüm kaynaklar)
            allowed_sources = get_allowed_source_ids(ws_user)
            if allowed_sources is not None:
                allowed_set = set(allowed_sources)
                requested = {sid for sid in [active_source_id, *source_ids] if sid}
                denied = requested - allowed_set
                if denied:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Bu veri kaynaklarına erişim yetkiniz yok: {sorted(denied)}. Lütfen yöneticinizle görüşün."
                    })
                    await websocket.send_json({"type": "done", "final_response": "⚠️ Erişim yetkisi olmayan kaynak seçildi."})
                    continue
                source_ids = [sid for sid in source_ids if sid in allowed_set]
            session_id = payload.get("session_id")
            api_key = payload.get("api_key")
            base_url = payload.get("base_url")
            model = payload.get("model")

            import time
            if not session_id:
                session_id = f"session-{int(time.time() * 1000)}"
                await asyncio.to_thread(
                    create_session,
                    session_id,
                    user_text[:24] + ("..." if len(user_text) > 24 else ""),
                    active_source_id,
                    ws_user.get("id", ""),
                )

            # Save User Message to Database
            user_msg_id = payload.get("user_msg_id") or f"user-{int(time.time() * 1000)}"
            await asyncio.to_thread(
                add_chat_message,
                session_id=session_id,
                message_id=user_msg_id,
                role="user",
                text=user_text,
            )

            # Fallback to database LLM configs if not provided or empty from client
            if not api_key or not base_url or not model:
                db_config = await asyncio.to_thread(get_llm_config)
                api_key = api_key or db_config.get("apiKey")
                base_url = base_url or db_config.get("baseUrl")
                model = model or db_config.get("model")

            query_started = time.monotonic()
            audit("chat.query", target=session_id, detail={
                "question": user_text[:200],
                "sources": source_ids,
                "active_source": active_source_id,
            }, user=ws_user)

            # Setup supervisor agent with client configs if provided
            if os.getenv("USE_LANGGRAPH", "true").lower() == "true":
                agent = GraphSupervisorAgent(api_key=api_key, base_url=base_url, model=model)
            else:
                agent = SupervisorAgent(api_key=api_key, base_url=base_url, model=model)

            # Define WebSocket callback for sending steps and tracking status history
            status_history = ["Bağlantı kuruluyor..."]
            cancelled = False
            main_loop = asyncio.get_running_loop()

            async def ws_callback(data: Dict[str, Any]):
                nonlocal cancelled
                if cancelled:
                    return
                if data.get("type") == "status":
                    status_history.append(data.get("message"))
                # process_query worker thread'inde çalıştığı için WS gönderimini
                # ana event loop'a marshal ediyoruz (Starlette WS thread-safe değil).
                await asyncio.wrap_future(
                    asyncio.run_coroutine_threadsafe(websocket.send_json(data), main_loop)
                )

            def _run_agent() -> Dict[str, Any]:
                # Ajan hattının tamamı (LLM çağrıları, DuckDB, sandbox subprocess)
                # izole bir event loop'ta çalıştırılarak ana döngünün bloklanması önlenir.
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    return loop.run_until_complete(agent.process_query(
                        user_question=user_text,
                        active_source_id=active_source_id,
                        source_ids=source_ids,
                        relationships=relationships,
                        ws_callback=ws_callback,
                    ))
                finally:
                    asyncio.set_event_loop(None)
                    loop.close()

            # Process query — 120 saniye hard timeout
            try:
                result = await asyncio.wait_for(asyncio.to_thread(_run_agent), timeout=120)
            except asyncio.TimeoutError:
                cancelled = True
                logger.warning(f"WebSocket query timed out after 120s for session: {session_id}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Sorgu zaman aşımına uğradı (120s). Lütfen sorgunuzu basitleştirin veya daha küçük bir veri kümesi seçin."
                })
                await websocket.send_json({
                    "type": "done",
                    "final_response": "⚠️ Sorgu zaman aşımına uğradı (120 saniye). Lütfen tekrar deneyin."
                })
                continue

            agent_msg_id = payload.get("agent_msg_id") or f"agent-{int(time.time() * 1000)}"

            # Send final results and done signal
            if result.get("success"):
                final_resp = result.get("final_response")
                auto_corr = result.get("auto_corrections")
                if auto_corr and isinstance(auto_corr, dict) and auto_corr.get("applied"):
                    applied = auto_corr.get("applied")
                    note = "\n\n(Not: Yerel otomatik düzeltme uygulandı: " + ", ".join([f"{k}→{v}" for k, v in applied.items()]) + ")"
                    final_resp = (final_resp or "") + note

                audit("chat.result", target=session_id, detail={
                    "success": True,
                    "duration_s": round(time.monotonic() - query_started, 2),
                }, user=ws_user)
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
                await asyncio.to_thread(
                    add_chat_message,
                    session_id=session_id,
                    message_id=agent_msg_id,
                    role="agent",
                    text=final_resp,
                    status_history=status_history,
                    code=result.get("generated_code"),
                    code_language=code_lang,
                    data=result.get("data"),
                    visualization=result.get("visualization"),
                    auto_corrections=auto_corr,
                )
            else:
                audit("chat.result", target=session_id, detail={
                    "success": False,
                    "duration_s": round(time.monotonic() - query_started, 2),
                }, user=ws_user)
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
                await asyncio.to_thread(
                    add_chat_message,
                    session_id=session_id,
                    message_id=agent_msg_id,
                    role="agent",
                    text=result.get("final_response", "⚠️ Sorgulama sırasında bir hata oluştu."),
                    status_history=status_history,
                    code=result.get("generated_code"),
                    code_language=code_lang,
                    error=result.get("error"),
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
