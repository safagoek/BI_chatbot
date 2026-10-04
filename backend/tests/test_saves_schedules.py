"""
tests/test_saves_schedules.py
Kayıtlı analizler + zamanlanmış raporlar CRUD testleri.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from main import app

from app.core.auth import hash_password
from app.database.manager import create_user, get_user_by_username

client = TestClient(app)


def _token_for(username, password):
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200
    return res.json()["token"]


def setup_module(module):
    if not get_user_by_username("admin"):
        create_user("admin", hash_password("sched-admin-pass"), "Sched Admin", "admin")
    else:
        from app.database.manager import update_user
        update_user(get_user_by_username("admin")["id"],
                    password_hash=hash_password("sched-admin-pass"), is_active=True)
    module.TOKEN = _token_for("admin", "sched-admin-pass")
    module.HEADERS = {"Authorization": f"Bearer {module.TOKEN}"}


class TestSaves:
    def test_crud_cycle(self):
        h = HEADERS
        res = client.post("/api/saves", headers=h, json={
            "title": "Aylık satış", "question": "aylık satış trendi",
            "source_ids": ["src1"], "relationships": [],
        })
        assert res.status_code == 200
        save_id = res.json()["id"]
        assert res.json()["source_ids"] == ["src1"]

        res_list = client.get("/api/saves", headers=h)
        assert any(r["id"] == save_id for r in res_list.json())

        assert client.delete(f"/api/saves/{save_id}", headers=h).json()["success"]
        assert all(r["id"] != save_id for r in client.get("/api/saves", headers=h).json())

    def test_requires_auth(self):
        assert client.get("/api/saves").status_code == 401


class TestSchedules:
    def test_crud_cycle(self):
        h = HEADERS
        res = client.post("/api/schedules", headers=h, json={
            "title": "Pazartesi raporu", "question": "haftalık satış özeti",
            "source_ids": ["src1"], "frequency": "weekly", "hour": 9,
            "day_of_week": 0, "email": "a@b.com",
        })
        assert res.status_code == 200
        sid = res.json()["id"]
        assert res.json()["active"] is True

        res_upd = client.put(f"/api/schedules/{sid}", headers=h, json={"active": False, "hour": 8})
        assert res_upd.status_code == 200
        assert res_upd.json()["active"] is False and res_upd.json()["hour"] == 8

        assert client.delete(f"/api/schedules/{sid}", headers=h).json()["success"]

    def test_invalid_frequency_rejected(self):
        res = client.post("/api/schedules", headers=HEADERS, json={
            "title": "x", "question": "y", "frequency": "monthly",
        })
        assert res.status_code == 400
        assert res.json()["detail"] == "INVALID_FREQUENCY"

    def test_due_logic(self):
        from app.database.manager import get_due_scheduled_reports, create_scheduled_report, delete_scheduled_report
        created = create_scheduled_report(
            "schedtest-user", "Due test", "q", "[]", "[]", "daily", hour=3, day_of_week=1, email="",
        )
        try:
            # saat 3 → due; saat 4 → değil (son koşu yoksa)
            assert any(r["id"] == created["id"] for r in get_due_scheduled_reports(3, 1, "2026-01-01"))
            assert not any(r["id"] == created["id"] for r in get_due_scheduled_reports(4, 1, "2026-01-01"))
        finally:
            delete_scheduled_report("schedtest-user", created["id"])
