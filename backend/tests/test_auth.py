"""
tests/test_auth.py

SaaS kimlik doğrulama katmanı testleri:
- login / me / change-password akışı
- admin kullanıcı yönetimi ve rol koruması
- kullanıcı bazlı kaynak yetkileri
- MCP config endpoint'leri
Çalıştırma: cd backend && venv/Scripts/python.exe -m pytest tests/test_auth.py -v
"""
import sys
import os
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from main import app

from app.core.auth import hash_password
from app.database.manager import (
    create_user, get_user_by_username, replace_user_permissions, update_user,
)

client = TestClient(app)


@pytest.fixture(scope="module")
def admin_token():
    """Bilinen şifreyle admin oturumu."""
    password = "auth-test-admin-pass"
    user = get_user_by_username("admin")
    if not user:
        create_user("admin", hash_password(password), "Auth Test Admin", "admin")
    else:
        update_user(user["id"], password_hash=hash_password(password), is_active=True)
    res = client.post("/api/auth/login", json={"username": "admin", "password": password})
    assert res.status_code == 200
    return res.json()["token"]


@pytest.fixture(scope="module")
def regular_user():
    """Yetkisiz erişim testleri için izole bir normal kullanıcı."""
    suffix = uuid.uuid4().hex[:6]
    username = f"u_{suffix}"
    user = create_user(username, hash_password("user-pass-1234"), "Test User", "user")
    yield {"user": user, "username": username, "password": "user-pass-1234"}
    from app.database.manager import delete_user
    delete_user(user["id"])


def _login(username: str, password: str):
    return client.post("/api/auth/login", json={"username": username, "password": password})


# ─── Login / Me ──────────────────────────────────────────────────────────────

class TestLogin:
    def test_login_success(self, admin_token):
        assert admin_token  # fixture login başarılı

    def test_login_wrong_password(self, admin_token):
        res = _login("admin", "wrong-password")
        assert res.status_code == 401
        assert res.json()["detail"] == "INVALID_CREDENTIALS"

    def test_login_unknown_user(self):
        res = _login(f"nope_{uuid.uuid4().hex[:6]}", "whatever123")
        assert res.status_code == 401

    def test_me_requires_auth(self):
        assert client.get("/api/auth/me").status_code == 401

    def test_me_returns_user(self, admin_token):
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200
        assert res.json()["role"] == "admin"
        assert res.json()["source_ids"] is None  # admin → tüm kaynaklar


# ─── Admin koruması ──────────────────────────────────────────────────────────

class TestAdminGuard:
    def test_admin_endpoints_reject_anonymous(self):
        assert client.get("/api/admin/users").status_code == 401

    def test_admin_endpoints_reject_regular_user(self, regular_user):
        res = _login(regular_user["username"], regular_user["password"])
        token = res.json()["token"]
        assert client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"}).status_code == 403
        assert client.get("/api/mcp/config", headers={"Authorization": f"Bearer {token}"}).status_code == 403
        assert client.get("/api/settings", headers={"Authorization": f"Bearer {token}"}).status_code == 403

    def test_admin_can_list_users(self, admin_token):
        res = client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200
        assert any(u["username"] == "admin" for u in res.json())


# ─── Kullanıcı oluşturma ve yetkilendirme ────────────────────────────────────

class TestUserManagement:
    def test_admin_creates_user_and_assigns_permissions(self, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        username = f"created_{uuid.uuid4().hex[:6]}"

        res = client.post("/api/admin/users", headers=headers, json={
            "username": username, "password": "init-pass-1234", "display_name": "Created", "role": "user",
        })
        assert res.status_code == 200
        user_id = res.json()["id"]

        try:
            # Kullanıcı ilk şifreyle giriş yapabilmeli
            res_login = _login(username, "init-pass-1234")
            assert res_login.status_code == 200
            assert res_login.json()["user"]["must_change_password"] is True

            # Admin kaynak yetkisi atar
            src_ids = ["src_a", "src_b"]
            res_perm = client.put(f"/api/admin/users/{user_id}/permissions", headers=headers,
                                  json={"source_ids": src_ids})
            assert res_perm.status_code == 200

            res_me = client.get("/api/auth/me", headers={
                "Authorization": f"Bearer {_login(username, 'init-pass-1234').json()['token']}"
            })
            assert res_me.json()["source_ids"] == src_ids
        finally:
            from app.database.manager import delete_user
            delete_user(user_id)

    def test_duplicate_username_rejected(self, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        res = client.post("/api/admin/users", headers=headers, json={
            "username": "admin", "password": "whatever-123", "role": "user",
        })
        assert res.status_code == 409

    def test_short_password_rejected(self, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        res = client.post("/api/admin/users", headers=headers, json={
            "username": f"short_{uuid.uuid4().hex[:6]}", "password": "short", "role": "user",
        })
        assert res.status_code == 400

    def test_cannot_delete_last_admin(self, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        admin_id = get_user_by_username("admin")["id"]
        # Kendini silme CANNOT_DELETE_SELF döndürür
        res = client.delete(f"/api/admin/users/{admin_id}", headers=headers)
        assert res.status_code == 400
        # Son adminin rolü düşürülememeli: LAST_ADMIN
        res_demote = client.put(f"/api/admin/users/{admin_id}", headers=headers,
                                json={"role": "user", "is_active": False})
        assert res_demote.status_code == 400
        assert res_demote.json()["detail"] == "LAST_ADMIN"


# ─── Şifre değiştirme ────────────────────────────────────────────────────────

class TestChangePassword:
    def test_change_password_flow(self, admin_token):
        username = f"pw_{uuid.uuid4().hex[:6]}"
        old_password = "old-pass-12345"
        new_password = "new-pass-67890"
        created = create_user(username, hash_password(old_password), "", "user")
        try:
            token = _login(username, old_password).json()["token"]
            res = client.post("/api/auth/change-password", headers={
                "Authorization": f"Bearer {token}"
            }, json={"current_password": old_password, "new_password": new_password})
            assert res.status_code == 200

            # Eski şifre artık çalışmıyor, yenisi çalışıyor
            assert _login(username, old_password).status_code == 401
            assert _login(username, new_password).status_code == 200
        finally:
            from app.database.manager import delete_user
            delete_user(created["id"])

    def test_change_password_rejects_wrong_current(self, admin_token):
        username = f"pw_{uuid.uuid4().hex[:6]}"
        created = create_user(username, hash_password("correct-pass-1"), "", "user")
        try:
            token = _login(username, "correct-pass-1").json()["token"]
            res = client.post("/api/auth/change-password", headers={
                "Authorization": f"Bearer {token}"
            }, json={"current_password": "wrong-pass-12", "new_password": "another-12345"})
            assert res.status_code == 401
        finally:
            from app.database.manager import delete_user
            delete_user(created["id"])


# ─── Oturum sahipliği ────────────────────────────────────────────────────────

class TestSessionScoping:
    def test_users_see_only_own_sessions(self, admin_token, regular_user):
        headers_user = {"Authorization": f"Bearer {_login(regular_user['username'], regular_user['password']).json()['token']}"}
        res_create = client.post("/api/sessions", headers=headers_user, json={"title": "User Session"})
        assert res_create.status_code == 200
        session_id = res_create.json()["id"]

        try:
            # Kullanıcı kendi oturumunu görür
            res_list = client.get("/api/sessions", headers=headers_user)
            assert any(s["id"] == session_id for s in res_list.json())

            # Admin görür
            res_admin = client.get("/api/sessions", headers={"Authorization": f"Bearer {admin_token}"})
            assert any(s["id"] == session_id for s in res_admin.json())
        finally:
            client.delete(f"/api/sessions/{session_id}", headers={"Authorization": f"Bearer {admin_token}"})


# ─── MCP config ──────────────────────────────────────────────────────────────

class TestMCPConfig:
    def test_admin_reads_and_writes_config(self, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        res = client.get("/api/mcp/config", headers=headers)
        assert res.status_code == 200
        original = res.json()
        assert "mcpServers" in original

        res_put = client.put("/api/mcp/config", headers=headers, json={"config": original})
        assert res_put.status_code == 200

    def test_invalid_config_rejected(self, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        res = client.put("/api/mcp/config", headers=headers, json={"config": {"foo": 1}})
        assert res.status_code == 400
