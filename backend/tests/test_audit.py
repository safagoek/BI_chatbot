"""
tests/test_audit.py

Denetim kaydı (audit log) testleri:
- giriş / başarısız giriş / kullanıcı yönetimi olayları kaydedilir
- hassas alanlar maskelemeden geçmez
- /api/admin/audit yalnızca admin'e açık
Çalıştırma: cd backend && venv/Scripts/python.exe -m pytest tests/test_audit.py -v
"""
import sys
import os
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from main import app

from app.core.auth import hash_password
from app.database.manager import create_user, delete_user, get_user_by_username

client = TestClient(app)


@pytest.fixture(scope="module")
def admin_token():
    password = "audit-admin-pass"
    user = get_user_by_username("admin")
    if not user:
        create_user("admin", hash_password(password), "Audit Admin", "admin")
    else:
        from app.database.manager import update_user
        update_user(user["id"], password_hash=hash_password(password), is_active=True)
    res = client.post("/api/auth/login", json={"username": "admin", "password": password})
    assert res.status_code == 200
    return res.json()["token"]


def _login(username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


class TestAuditRecording:
    def test_login_recorded(self):
        # Her modül-fixture girişi auth.login üretir; yeni bir olay sayısı artmalı
        _login("admin", "definitely-wrong-password")
        _login("admin", "definitely-wrong-password")
        res = client.post("/api/auth/login", json={"username": "admin", "password": "x"})
        assert res.status_code == 401  # failed

        from app.database.manager import db_connection
        with db_connection() as conn:
            n_fail = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE action = 'auth.login_failed'"
            ).fetchone()[0]
        assert n_fail >= 2

    def test_sensitive_values_never_stored(self, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        username = f"aud_{uuid.uuid4().hex[:6]}"
        res = client.post("/api/admin/users", headers=headers, json={
            "username": username, "password": "secret-pass-999", "role": "user",
        })
        assert res.status_code == 200
        user_id = res.json()["id"]
        try:
            from app.database.manager import db_connection
            with db_connection() as conn:
                rows = conn.execute(
                    "SELECT detail_json FROM audit_log WHERE action = 'admin.user_create'"
                ).fetchall()
            blob = " ".join((r[0] or "") for r in rows)
            assert "secret-pass-999" not in blob
        finally:
            delete_user(user_id)

    def test_permissions_update_recorded(self, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        username = f"audp_{uuid.uuid4().hex[:6]}"
        created = create_user(username, hash_password("pass-12345678"), "", "user")
        try:
            client.put(f"/api/admin/users/{created['id']}/permissions", headers=headers,
                       json={"source_ids": ["src_x"]})
            from app.database.manager import db_connection
            with db_connection() as conn:
                row = conn.execute(
                    "SELECT detail_json FROM audit_log WHERE action = 'admin.permissions_update' ORDER BY id DESC LIMIT 1"
                ).fetchone()
            assert row is not None and "src_x" in row[0]
        finally:
            delete_user(created["id"])


class TestAuditViewer:
    def test_anonymous_rejected(self):
        assert client.get("/api/admin/audit").status_code == 401

    def test_regular_user_rejected(self):
        username = f"audv_{uuid.uuid4().hex[:6]}"
        create_user(username, hash_password("pass-12345678"), "", "user")
        try:
            token = _login(username, "pass-12345678").json()["token"]
            res = client.get("/api/admin/audit", headers={"Authorization": f"Bearer {token}"})
            assert res.status_code == 403
        finally:
            delete_user(get_user_by_username(username)["id"])

    def test_admin_reads_entries(self, admin_token):
        res = client.get("/api/admin/audit?limit=10", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200
        body = res.json()
        assert body["total"] >= 1
        assert len(body["items"]) >= 1
        item = body["items"][0]
        assert {"id", "action", "created_at"} <= set(item.keys())
