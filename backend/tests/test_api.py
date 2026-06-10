"""
tests/test_api.py

FastAPI endpoint'leri için kapsamlı entegrasyon test suite'i.
FastAPI TestClient kullanarak tüm router'ları (sessions, sources, files, settings, analytics, rag) test eder.
Çalıştırma: cd backend && venv/bin/pytest tests/test_api.py -v
"""
import pytest
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def setup_module(module):
    """Test öncesi demo_sqlite veritabanı kaynağını tohumlar."""
    import sqlite3
    import json
    from app.database.manager import DB_PATH
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM sources WHERE id = 'demo_sqlite'")
    if not cursor.fetchone():
        cursor.execute(
            """
            INSERT INTO sources (id, type, display_name, connection_details, schema_cache, labels_json, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "demo_sqlite",
                "sqlite",
                "Demo SQLite",
                json.dumps({"database_path": "demo.db"}),
                json.dumps({
                    "satislar": ["id", "urun_adi", "kategori", "ciro", "adet", "tarih", "musteri_id"],
                    "musteriler": ["id", "ad_soyad", "sehir", "kayit_tarihi"]
                }),
                json.dumps(["demo", "sales"]),
                1
            )
        )
        conn.commit()
    conn.close()


class TestAPIEndpoints:
    """Tüm API endpoint'leri için uçtan uca testler."""

    # ==========================================
    # 1. SESSIONS API TESTS
    # ==========================================
    def test_sessions_lifecycle(self):
        """Oturum oluşturma, listeleme, güncelleme ve silme döngüsü."""
        test_session_id = f"test-session-{uuid.uuid4().hex[:6]}"
        
        # A. Create session
        create_payload = {
            "id": test_session_id,
            "title": "Test Oturumu",
            "active_source_id": "demo_sqlite",
            "selected_sources": ["demo_sqlite"],
            "relationships": []
        }
        res_create = client.post("/api/sessions", json=create_payload)
        assert res_create.status_code == 200
        data_create = res_create.json()
        assert data_create["id"] == test_session_id
        assert data_create["title"] == "Test Oturumu"

        # B. Get single session
        res_get = client.get(f"/api/sessions/{test_session_id}")
        assert res_get.status_code == 200
        assert res_get.json()["id"] == test_session_id

        # C. List sessions
        res_list = client.get("/api/sessions")
        assert res_list.status_code == 200
        sessions = res_list.json()
        assert any(s["id"] == test_session_id for s in sessions)

        # D. Search sessions
        res_search = client.get(f"/api/sessions/search?q=Test")
        assert res_search.status_code == 200
        search_results = res_search.json()
        assert any(s["id"] == test_session_id for s in search_results)

        # E. Update session (rename)
        update_payload = {
            "title": "Güncellenmiş Test Oturumu",
            "active_source_id": "demo_sqlite"
        }
        res_update = client.put(f"/api/sessions/{test_session_id}", json=update_payload)
        assert res_update.status_code == 200
        assert res_update.json() == {"success": True}

        # Verify rename
        res_get_updated = client.get(f"/api/sessions/{test_session_id}")
        assert res_get_updated.json()["title"] == "Güncellenmiş Test Oturumu"

        # F. Get chat messages (should be empty initially)
        res_msgs = client.get(f"/api/sessions/{test_session_id}/messages")
        assert res_msgs.status_code == 200
        assert isinstance(res_msgs.json(), list)

        # G. Clear chat messages
        res_clear = client.post(f"/api/sessions/{test_session_id}/clear")
        assert res_clear.status_code == 200
        assert res_clear.json() == {"success": True}

        # H. Delete session
        res_delete = client.delete(f"/api/sessions/{test_session_id}")
        assert res_delete.status_code == 200
        assert res_delete.json() == {"success": True}

        # Verify deleted
        res_get_deleted = client.get(f"/api/sessions/{test_session_id}")
        assert res_get_deleted.status_code == 404

    # ==========================================
    # 2. SOURCES API TESTS
    # ==========================================
    def test_sources_endpoints(self):
        """Veri kaynakları endpoint'leri."""
        # A.0 List local SQLite files
        res_local_files = client.get("/api/sources/local-sqlite-files")
        assert res_local_files.status_code == 200
        local_files = res_local_files.json()
        assert isinstance(local_files, list)
        assert "demo.db" in local_files

        # A.0.0 Upload SQLite file test
        import io
        fake_db_content = b"SQLite format 3\x00\x04\x00\x01\x01\x00@  \x00\x00\x00\x00\x00\x00\x00\x00"
        res_upload = client.post(
            "/api/sources/upload-sqlite",
            files={"file": ("test_upload.db", io.BytesIO(fake_db_content), "application/x-sqlite3")}
        )
        assert res_upload.status_code == 200
        assert res_upload.json()["success"] is True
        assert "test_upload.db" in res_upload.json()["database_path"]

        # A. List sources
        res_list = client.get("/api/sources")
        assert res_list.status_code == 200
        sources = res_list.json()
        assert isinstance(sources, list)
        # Demo sqlite source should be present
        assert any(s["id"] == "demo_sqlite" for s in sources)

        # B. Get source details
        res_get = client.get("/api/sources/demo_sqlite")
        assert res_get.status_code == 200
        assert res_get.json()["id"] == "demo_sqlite"

        # C. Get source semantic mapping
        res_semantic = client.get("/api/sources/demo_sqlite/semantic")
        assert res_semantic.status_code == 200
        assert isinstance(res_semantic.json(), dict)

        # D. Get connector status
        res_connectors = client.get("/api/sources/connectors/status")
        assert res_connectors.status_code == 200
        connectors = res_connectors.json()
        assert "snowflake" in connectors
        assert "mssql" in connectors
        assert "bigquery" in connectors

        # E. Test connection (with bad credentials - should fail gracefully)
        test_payload = {
            "type": "postgresql",
            "connection_details": {"host": "127.0.0.1", "port": 9999, "database": "nonexistent_db_xyz"}
        }
        res_test = client.post("/api/sources/test-connection", json=test_payload)
        assert res_test.status_code == 200
        assert res_test.json()["success"] is False

    def test_source_clone_and_delete(self):
        """Veri kaynağı kopyalama ve silme."""
        # A. Clone demo source
        clone_payload = {
            "display_name": "Demo SQLite Kopya Test"
        }
        res_clone = client.post("/api/sources/demo_sqlite/clone", json=clone_payload)
        assert res_clone.status_code == 200
        cloned_source = res_clone.json()
        cloned_id = cloned_source["id"]
        assert cloned_id.startswith("db_")
        assert cloned_source["display_name"] == "Demo SQLite Kopya Test"

        # B. Update cloned source status
        status_payload = {"is_active": False}
        res_status = client.put(f"/api/sources/{cloned_id}/status", json=status_payload)
        assert res_status.status_code == 200
        assert res_status.json() == {"success": True, "is_active": False}

        # C. Update cloned source labels
        labels_payload = {"labels": ["test", "cloned"]}
        res_labels = client.put(f"/api/sources/{cloned_id}/labels", json=labels_payload)
        assert res_labels.status_code == 200
        assert res_labels.json()["labels"] == ["test", "cloned"]

        # D. Delete cloned source
        res_delete = client.delete(f"/api/sources/{cloned_id}")
        assert res_delete.status_code == 200
        assert res_delete.json() == {"success": True}

    def test_demo_source_readonly_protection(self):
        """Demo veri kaynağının silinememesi veya kapatılamaması koruması."""
        # Silme testi
        res_delete = client.delete("/api/sources/demo_sqlite")
        assert res_delete.status_code == 403
        assert res_delete.json()["detail"] == "DEMO_SOURCE_READONLY"

        # Durum güncelleme testi
        res_status = client.put("/api/sources/demo_sqlite/status", json={"is_active": False})
        assert res_status.status_code == 403
        assert res_status.json()["detail"] == "DEMO_SOURCE_READONLY"

    # ==========================================
    # 3. FILES API TESTS
    # ==========================================
    def test_files_list(self):
        """Yüklenen dosyalar listesi."""
        res = client.get("/api/files")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    # ==========================================
    # 4. SETTINGS API TESTS
    # ==========================================
    def test_settings_endpoints(self):
        """LLM ayarları get/update."""
        # A. Get settings
        res_get = client.get("/api/settings")
        assert res_get.status_code == 200
        config = res_get.json()
        assert "baseUrl" in config
        assert "model" in config

        # B. Save settings
        save_payload = {
            "apiKey": config.get("apiKey", "test_key"),
            "baseUrl": "https://api.deepseek.com/v1",
            "model": "deepseek-coder-v2"
        }
        res_save = client.put("/api/settings", json=save_payload)
        assert res_save.status_code == 200
        assert res_save.json() == {"success": True}

    # ==========================================
    # 5. ANALYTICS API TESTS
    # ==========================================
    def test_analytics_endpoints(self):
        """Dashboard analitik istatistikleri."""
        # A. Analytics Summary
        res_sum = client.get("/api/analytics/summary")
        assert res_sum.status_code == 200
        summary = res_sum.json()
        assert "total_sessions" in summary
        assert "total_queries" in summary
        assert "success_rate" in summary
        assert isinstance(summary["daily_activity"], list)
        assert isinstance(summary["code_type_distribution"], list)

        # B. Analytics Sources Usage
        res_sources = client.get("/api/analytics/sources")
        assert res_sources.status_code == 200
        assert isinstance(res_sources.json(), list)

    # ==========================================
    # 6. RAG MEMORY API TESTS
    # ==========================================
    def test_rag_memory_endpoints(self):
        """RAG bellek yönetimi API'leri."""
        # A. List RAG memory
        res_list = client.get("/api/rag/memory")
        assert res_list.status_code == 200
        memory = res_list.json()
        assert isinstance(memory, list)

        # B. Filter by source_id
        res_filtered = client.get("/api/rag/memory?source_id=demo_sqlite")
        assert res_filtered.status_code == 200
        assert isinstance(res_filtered.json(), list)
