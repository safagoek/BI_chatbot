"""
tests/test_hana_cds.py

S/4HANA CDS view keşfi testleri — sahte hdbcli ile, canlı S/4 bağlantısı olmadan.
Senaryolar:
- RELEASED_OBJECTS katalog görünümü olan sistemde released view'lar bulunur
- Katalog olmayan sistemde I_/C_ önekli geçerli view'lara düşer
- Kolonlar TEK toplu SYS.VIEW_COLUMNS sorgusundan gelir
- max_views sınırı uygulanır
Çalıştırma: cd backend && venv/Scripts/python.exe -m pytest tests/test_hana_cds.py -v
"""
import sys
import os
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database.connectors import discover_cds_views

DETAILS = {"host": "s4.example.com", "port": 30015, "user": "u", "password": "p", "schema": "SAPHANADB"}

TABLES_ROWS = [("I_Customer",), ("C_SalesOrderItem",), ("I_OtherThing",)]
COLUMN_ROWS = [
    ("I_Customer", "Customer", 1),
    ("I_Customer", "CustomerName", 2),
    ("C_SalesOrderItem", "SalesOrder", 1),
    ("C_SalesOrderItem", "NetAmount", 2),
    ("I_OtherThing", "Field1", 1),
]


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._rows = []

    def execute(self, sql, params=None):
        self.conn.queries.append((sql, params))
        if "RELEASED_OBJECTS" in sql:
            if self.conn.has_released_catalog:
                self._rows = [("I_Customer",)]
            else:
                raise RuntimeError("katalog görünümü yok")
        elif "FROM SYS.VIEWS" in sql:
            # released sorgusuyla ikinci kez çağrıldıysa tüm I_/C_ listesi
            self._rows = list(TABLES_ROWS)
        elif "SYS.VIEW_COLUMNS" in sql:
            wanted = (params or [None])[1:]
            self._rows = [r for r in COLUMN_ROWS if r[0] in wanted]
        elif "CURRENT_SCHEMA" in sql:
            self._rows = [("SAPHANADB",)]
        else:
            self._rows = []
        return self

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def close(self):
        pass


class FakeConn:
    def __init__(self, has_released_catalog=True):
        self.queries = []
        self.closed = False
        self.has_released_catalog = has_released_catalog

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


@pytest.fixture()
def fake_driver(monkeypatch):
    holder = {}

    def make_conn(**kwargs):
        conn = FakeConn()
        holder["conn"] = conn
        return conn

    hdbcli = types.ModuleType("hdbcli")
    dbapi = types.ModuleType("hdbcli.dbapi")
    dbapi.connect = make_conn
    hdbcli.dbapi = dbapi
    monkeypatch.setitem(sys.modules, "hdbcli", hdbcli)
    monkeypatch.setitem(sys.modules, "hdbcli.dbapi", dbapi)
    return holder


class TestCDSDiscovery:
    def test_released_catalog_used_when_available(self, fake_driver):
        schema = discover_cds_views(DETAILS)
        # released katalogda yalnız I_Customer vardı; fallback I_/C_ tamamlayıcı → ikisi de gelir
        assert "I_Customer" in schema
        assert "C_SalesOrderItem" in schema
        assert schema["I_Customer"] == ["Customer", "CustomerName"]

    def test_bulk_column_query(self, fake_driver):
        discover_cds_views(DETAILS)
        col_queries = [q for q in fake_driver["conn"].queries if "SYS.VIEW_COLUMNS" in q[0]]
        assert len(col_queries) == 1  # view başına sorgu yok

    def test_fallback_without_catalog(self, monkeypatch):
        holder = {}
        hdbcli = types.ModuleType("hdbcli")
        dbapi = types.ModuleType("hdbcli.dbapi")

        def make_conn(**kw):
            c = FakeConn(has_released_catalog=False)
            holder["conn"] = c
            return c

        dbapi.connect = make_conn
        hdbcli.dbapi = dbapi
        monkeypatch.setitem(sys.modules, "hdbcli", hdbcli)
        monkeypatch.setitem(sys.modules, "hdbcli.dbapi", dbapi)

        schema = discover_cds_views(DETAILS)
        assert set(schema.keys()) == {"I_Customer", "C_SalesOrderItem", "I_OtherThing"}

    def test_max_views_cap(self, fake_driver):
        schema = discover_cds_views({**DETAILS, "max_views": 2})
        assert len(schema) <= 2

    def test_connection_closed(self, fake_driver):
        discover_cds_views(DETAILS)
        assert fake_driver["conn"].closed is True
