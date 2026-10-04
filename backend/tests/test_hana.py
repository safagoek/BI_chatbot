"""
tests/test_hana.py

SAP S/4HANA (HANA) bağlantı katmanı testleri — sahte hdbcli sürücüsü ile:
- bağlantı seçenekleri ve SET SCHEMA davranışı
- check_connection sızıntısız kapanma
- şema keşfinin filtreli/TOPLU (bulk) davranışı (S/4HANA ölçek uyumu)
- foreign key ilişki keşfi
- LOB kolon dönüşümü
Çalıştırma: cd backend && venv/Scripts/python.exe -m pytest tests/test_hana.py -v
"""
import sys
import os
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database.connectors import (
    ConnectorError,
    _get_sap_s4hana_conn,
    check_connection,
    discover_schema,
    discover_relationships,
    execute_safe_sql,
)


# ─── Sahte hdbcli sürücüsü ───────────────────────────────────────────────────

class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._current = None

    def execute(self, sql, params=None):
        self.conn.queries.append((sql, params))
        if "CURRENT_SCHEMA FROM DUMMY" in sql:
            self._current = [("SAPHANADB",)]
        elif "FROM SYS.TABLES" in sql:
            self._current = [("KNA1",), ("VBAK",), ("/1BS/INTERNAL",), ("SAP_HIDDEN",)]
        elif "SYS.TABLE_COLUMNS" in sql:
            self._current = [("KNA1", "KUNNR", 1), ("KNA1", "NAME1", 2), ("VBAK", "VBELN", 1)]
        elif "REFERENTIAL_CONSTRAINTS" in sql:
            self._current = [("VBAK", "KUNNR", "KNA1", "KUNNR")]
        elif "FROM DUMMY" in sql:
            self._current = [(1,)]
        else:
            self._current = []
        return self

    def fetchone(self):
        return self._current[0] if self._current else None

    def fetchall(self):
        return list(self._current)

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.queries = []
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


class FakeLOB:
    def __init__(self, value="lob-data"):
        self._value = value

    def read(self):
        return self._value


@pytest.fixture()
def fake_hdbcli(monkeypatch):
    conn_holder = {}

    def make_conn(**kwargs):
        conn = FakeConnection()
        conn.connect_kwargs = kwargs
        conn_holder["conn"] = conn
        return conn

    hdbcli = types.ModuleType("hdbcli")
    dbapi = types.ModuleType("hdbcli.dbapi")
    dbapi.connect = make_conn
    hdbcli.dbapi = dbapi
    monkeypatch.setitem(sys.modules, "hdbcli", hdbcli)
    monkeypatch.setitem(sys.modules, "hdbcli.dbapi", dbapi)
    return conn_holder


DETAILS = {
    "host": "hana.example.com",
    "port": 30015,
    "user": "SAPUSER",
    "password": "secret",
    "schema": "SAPHANADB",
}


# ─── Bağlantı ────────────────────────────────────────────────────────────────

class TestHANAConnection:
    def test_connects_and_sets_schema(self, fake_hdbcli):
        conn, dtype = _get_sap_s4hana_conn(DETAILS)
        assert dtype == "sap_s4hana"
        set_schema_calls = [q for q in conn.queries if "SET SCHEMA" in q[0]]
        assert len(set_schema_calls) == 1
        assert 'SET SCHEMA "SAPHANADB"' in set_schema_calls[0][0]

    def test_connect_options_passthrough(self, fake_hdbcli):
        details = {**DETAILS, "encrypt": True, "sslValidateCertificate": "false", "communicationTimeout": 50000}
        conn, _ = _get_sap_s4hana_conn(details)
        assert conn.connect_kwargs["encrypt"] is True
        assert conn.connect_kwargs["sslValidateCertificate"] == "false"
        assert conn.connect_kwargs["communicationTimeout"] == 50000

    def test_invalid_port_clear_message(self, fake_hdbcli):
        with pytest.raises(ConnectorError, match="30041"):
            _get_sap_s4hana_conn({**DETAILS, "port": "abc"})

# ─── check_connection ────────────────────────────────────────────────────────

class TestHANACheckConnection:
    def test_success_message_includes_schema(self, fake_hdbcli):
        ok, msg = check_connection("sap_s4hana", DETAILS)
        assert ok is True
        assert "SAPHANADB" in msg

    def test_connection_closed_on_success(self, fake_hdbcli):
        check_connection("sap_s4hana", DETAILS)
        assert fake_hdbcli["conn"].closed is True

    def test_connection_closed_on_ping_failure(self, fake_hdbcli, monkeypatch):
        def broken_execute(self, sql, params=None):
            raise RuntimeError("ping kaboom")

        holder = {}

        class Conn(FakeConnection):
            def cursor(self):
                cur = FakeCursor(self)
                cur.execute = broken_execute.__get__(cur)
                return cur

        def make_conn(**kwargs):
            c = Conn()
            holder["conn"] = c
            return c

        hdbcli = types.ModuleType("hdbcli")
        dbapi = types.ModuleType("hdbcli.dbapi")
        dbapi.connect = make_conn
        hdbcli.dbapi = dbapi
        monkeypatch.setitem(sys.modules, "hdbcli", hdbcli)
        monkeypatch.setitem(sys.modules, "hdbcli.dbapi", dbapi)

        ok, msg = check_connection("sap_s4hana", DETAILS)
        assert ok is False
        assert holder["conn"].closed is True


# ─── Şema keşfi (S/4HANA ölçek uyumu) ────────────────────────────────────────

class TestHANADiscoverSchema:
    def test_sap_namespace_tables_excluded(self, fake_hdbcli):
        schema = discover_schema("sap_s4hana", DETAILS)
        assert "/1BS/INTERNAL" not in schema
        assert "SAP_HIDDEN" not in schema
        assert "KNA1" in schema

    def test_bulk_column_query_no_per_table_roundtrips(self, fake_hdbcli):
        schema = discover_schema("sap_s4hana", DETAILS)
        col_queries = [q for q in fake_hdbcli["conn"].queries if "SYS.TABLE_COLUMNS" in q[0]]
        assert len(col_queries) == 1  # tablo başına sorgu yok, tek toplu sorgu
        assert schema["KNA1"] == ["KUNNR", "NAME1"]
        assert schema["VBAK"] == ["VBELN"]

    def test_table_filter_narrows_results(self, fake_hdbcli):
        details = {**DETAILS, "table_filter": "KNA%"}
        discover_schema("sap_s4hana", details)
        table_queries = [q for q in fake_hdbcli["conn"].queries if "FROM SYS.TABLES" in q[0]]
        assert any("KNA%" in p for _, p in table_queries if p)

    def test_max_tables_cap_sent(self, fake_hdbcli):
        details = {**DETAILS, "max_tables": 50}
        discover_schema("sap_s4hana", details)
        table_queries = [q for q in fake_hdbcli["conn"].queries if "FROM SYS.TABLES" in q[0]]
        assert any("LIMIT 50" in q[0] for q in table_queries)


# ─── İlişki keşfi ────────────────────────────────────────────────────────────

class TestHANARelationships:
    def test_foreign_keys_discovered(self, fake_hdbcli):
        rels = discover_relationships("sap_s4hana", DETAILS)
        assert {"source_table": "VBAK", "source_column": "KUNNR",
                "target_table": "KNA1", "target_column": "KUNNR"} in rels


# ─── execute_safe_sql ────────────────────────────────────────────────────────

class TestHANAExecuteSafeSQL:
    def test_lob_values_converted(self, fake_hdbcli, monkeypatch):
        from app.database import connectors

        conn = FakeConnection()

        class LOBCursor(FakeCursor):
            def execute(self, sql, params=None):
                self._current = [("X", FakeLOB("lob-value"))]
                self.description = [("COL1",), ("COL2",)]
                return self

            def fetchall(self):
                return list(self._current)

        conn.cursor = lambda: LOBCursor(conn)

        orig = connectors._get_sap_s4hana_conn
        monkeypatch.setattr(connectors, "_get_sap_s4hana_conn", lambda d: (conn, "sap_s4hana"))
        res = execute_safe_sql("sap_s4hana", DETAILS, "SELECT COL1, COL2 FROM KNA1")
        assert res["rows"][0][1] == "lob-value"  # LOB → string
