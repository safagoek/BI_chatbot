"""
app/core/scheduler.py

Zamanlanmış raporlar: aktif schedule'ları kontrol eder, vadesi geleni
headless çalıştırır (ajan hattı), Excel raporu üretip e-posta ile gönderir.

MVP notu: FastAPI süreci içinde AsyncIOScheduler ile 15 dakikada bir kontrol.
Çok instance'lı dağıtımda kuyruğa taşınmalı (README yol haritası).
"""
import asyncio
import datetime
import json
import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def run_scheduled_report(schedule: Dict[str, Any]) -> bool:
    """Tek bir zamanlanmış raporu koşturur: analiz → Excel → e-posta."""
    from app.core.config import settings
    from app.database.manager import get_llm_config
    from app.agent.graph_supervisor import GraphSupervisorAgent
    from app.core.report_builder import build_excel_report

    source_ids = json.loads(schedule.get("source_ids_json") or "[]")
    relationships = json.loads(schedule.get("relationships_json") or "[]")

    db_cfg = get_llm_config()
    agent = GraphSupervisorAgent(
        api_key=db_cfg.get("apiKey"), base_url=db_cfg.get("baseUrl"), model=db_cfg.get("model"),
    )
    result = await agent.process_query(
        user_question=schedule["question"],
        active_source_id=source_ids[0] if source_ids else "",
        source_ids=source_ids,
        relationships=relationships,
        ws_callback=None,
    )
    if not result.get("success"):
        return False

    data = result.get("data") or {}
    columns, rows = data.get("columns", []), data.get("rows", [])
    if not columns:
        return False
    buffer = build_excel_report(columns, rows, title=f"DeepBI Raporu - {schedule['title']}")

    return _send_mail(
        to=schedule.get("email") or "",
        subject=f"DeepBI Raporu: {schedule['title']}",
        body=(
            f"Zamanlanmış raporunuz hazır.\n\nAnaliz: {schedule['question']}\n"
            f"Tarih: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            "Sonuç özeti:\n" + str(result.get("final_response", ""))[:1500]
        ),
        attachment=(buffer.getvalue(), f"deepbi_rapor_{schedule['id']}.xlsx"),
    )


def _send_mail(to: str, subject: str, body: str, attachment: Optional[tuple] = None) -> bool:
    from app.core.config import settings

    if not settings.smtp_host or not to:
        logger.warning("SMTP yapılandırılmadı veya alıcı yok — rapor e-postası atlandı.")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user or "deepbi@localhost"
    msg["To"] = to
    msg.set_content(body)
    if attachment:
        content, filename = attachment
        msg.add_attachment(content, maintype="application",
                           subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           filename=filename)
    try:
        if settings.smtp_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
            server.starttls()
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logger.error("Rapor e-postası gönderilemedi (%s): %s", to, e)
        return False


async def check_due_reports() -> None:
    """Vadesi gelen aktif raporları bulur ve sırayla koşturur."""
    from app.core.audit import audit
    from app.database.manager import get_due_scheduled_reports, mark_scheduled_run

    now = datetime.datetime.now()
    due = get_due_scheduled_reports(now.hour, now.weekday(), now.date().isoformat())
    for schedule in due:
        try:
            ok = await run_scheduled_report(schedule)
            mark_scheduled_run(schedule["id"], "success" if ok else "partial")
            audit("schedule.run", target=schedule["id"],
                  detail={"title": schedule["title"], "status": "success" if ok else "partial"})
        except Exception as e:
            logger.error("Zamanlanmış rapor hatası (%s): %s", schedule["id"], e)
            mark_scheduled_run(schedule["id"], f"error: {str(e)[:48]}")


def start_scheduler() -> Optional[Any]:
    from app.core.config import settings

    if not settings.schedules_enabled:
        logger.info("Zamanlanmış raporlar kapalı (schedules_enabled=false).")
        return None
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        # 15 dakikada bir vade kontrolü — saat/hatirlatici eşleşmesi job içinde yapılır
        scheduler.add_job(
            lambda: asyncio.ensure_future(check_due_reports()),
            "interval", minutes=15, id="deepbi_due_reports", max_instances=1,
        )
        scheduler.start()
        logger.info("Zamanlanmış rapor scheduler'ı başlatıldı (15 dk kontrol aralığı).")
        return scheduler
    except Exception as e:
        logger.error("Scheduler başlatılamadı: %s", e)
        return None
