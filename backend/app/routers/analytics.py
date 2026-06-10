"""
app/routers/analytics.py
Dashboard ve analitik özet istatistikleri endpoint'leri.
"""
from fastapi import APIRouter, HTTPException
from app.core.logger import logger

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary")
def get_analytics_summary():
    """Tüm oturumlar genelinde sorgu istatistiklerini döndürür."""
    try:
        import sqlite3
        from app.database.manager import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Toplam oturum sayısı
        cursor.execute("SELECT COUNT(*) as total FROM sessions")
        total_sessions = cursor.fetchone()["total"]

        # Toplam mesaj sayısı ve rol bazlı dağılım
        cursor.execute(
            "SELECT role, COUNT(*) as cnt FROM messages GROUP BY role"
        )
        msg_counts = {r["role"]: r["cnt"] for r in cursor.fetchall()}
        total_user = msg_counts.get("user", 0)
        total_agent = msg_counts.get("agent", 0)

        # Başarılı sorgu sayısı (error sütunu NULL olan agent mesajları)
        cursor.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE role = 'agent' AND (error IS NULL OR error = '')"
        )
        success_count = cursor.fetchone()["cnt"]

        # Başarı oranı
        success_rate = round((success_count / total_agent * 100), 1) if total_agent > 0 else 0.0

        # Son 7 gün günlük aktivite
        cursor.execute(
            """
            SELECT DATE(created_at) as day, COUNT(*) as cnt
            FROM messages
            WHERE created_at >= DATE('now', '-7 days')
            GROUP BY DATE(created_at)
            ORDER BY day ASC
            """
        )
        daily_activity = [{"day": r["day"], "count": r["cnt"]} for r in cursor.fetchall()]

        # Toplam kod dili dağılımı
        cursor.execute(
            """
            SELECT code_language, COUNT(*) as cnt
            FROM messages
            WHERE code_language IS NOT NULL AND code_language != ''
            GROUP BY code_language
            ORDER BY cnt DESC
            """
        )
        code_types = [{"language": r["code_language"], "count": r["cnt"]} for r in cursor.fetchall()]

        conn.close()

        return {
            "total_sessions": total_sessions,
            "total_queries": total_user,
            "total_agent_responses": total_agent,
            "success_count": success_count,
            "success_rate": success_rate,
            "daily_activity": daily_activity,
            "code_type_distribution": code_types,
        }
    except Exception as e:
        logger.error(f"analytics summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources")
def get_source_analytics():
    """Kaynak bazlı kullanım istatistikleri — hangi veri kaynakları en çok kullanılıyor."""
    try:
        import sqlite3
        from app.database.manager import DB_PATH, get_data_sources
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT active_source_id, COUNT(*) as session_count
            FROM sessions
            WHERE active_source_id IS NOT NULL AND active_source_id != ''
            GROUP BY active_source_id
            ORDER BY session_count DESC
            LIMIT 20
            """
        )
        rows = cursor.fetchall()
        conn.close()

        # Kaynak isimlerini çöz
        sources_map = {s["id"]: s["display_name"] for s in get_data_sources()}
        result = []
        for r in rows:
            sid = r["active_source_id"]
            result.append({
                "source_id": sid,
                "display_name": sources_map.get(sid, sid),
                "session_count": r["session_count"],
            })

        return result
    except Exception as e:
        logger.error(f"source analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
