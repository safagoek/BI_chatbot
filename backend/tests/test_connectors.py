"""
tests/test_connectors.py

Veritabanı connector katmanı için kapsamlı testler.
- SQLite gerçek bağlantı testi (diğerleri mock)
- do_check_connection / do_check_connection_unicode API doğruluğu
- discover_schema / execute_safe_sql / discover_relationships
- Hata yönetimi ve ConnectorError davranışı

Calistirma: .\\venv\\Scripts\\python.exe -m pytest tests/test_connectors.py -v
"""
import os
import sys
import sqlite3
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database.connectors import (
    ConnectorError,
    get_connection,
    # Not: test_ prefix'li alias kullanma — pytest bu fonksiyonları test sanıp toplar.
    check_connection as do_check_connection,
    check_connection_unicode as do_check_connection_unicode,
    discover_schema,
    execute_safe_sql,
    discover_relationships,
)


# --- Fixtures ----------------------------------------------------------------

@pytest.fixture(scope="module")
def temp_sqlite_db():
    """
    In-memory yerine disk üzerinde geçici bir SQLite DB oluşturur.
    orders, products ve foreign-key içeren bir şema barındırır.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE products (
            id      INTEGER PRIMARY KEY,
            name    TEXT NOT NULL,
            price   REAL
        )
    """)
    conn.execute("""
        CREATE TABLE orders (
            id         INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL REFERENCES products(id),
            amount     REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("INSERT INTO products VALUES (1, 'Laptop', 1500.0)")
    conn.execute("INSERT INTO products VALUES (2, 'Mouse', 25.0)")
    conn.execute("INSERT INTO orders VALUES (1, 1, 3, '2024-01-01')")
    conn.execute("INSERT INTO orders VALUES (2, 2, 10, '2024-01-02')")
    conn.commit()
    conn.close()

    yield path

    os.unlink(path)


@pytest.fixture()
def sqlite_details(temp_sqlite_db):
    return {"database_path": temp_sqlite_db}


# --- get_connection -----------------------------------------------------------

class TestGetConnection:
    def test_sqlite_returns_connection(self, sqlite_details):
        conn, dtype = get_connection("sqlite", sqlite_details)
        assert dtype == "sqlite"
        assert conn is not None
        conn.close()

    def test_sqlite_alias_lowercase(self, sqlite_details):
        """Büyük/küçük harf fark etmemeli."""
        conn, dtype = get_connection("SQLITE", sqlite_details)
        assert dtype == "sqlite"
        conn.close()

    def test_unsupported_type_raises(self):
        with pytest.raises(ConnectorError, match="Desteklenmeyen"):
            get_connection("oracle", {})

    def test_sqlite_missing_path_raises(self):
        with pytest.raises(ConnectorError, match="database_path"):
            get_connection("sqlite", {})

    def test_sqlite_nonexistent_file_raises(self):
        with pytest.raises(ConnectorError):
            get_connection("sqlite", {"database_path": "/nonexistent/path/db.sqlite"})

    def test_postgresql_missing_driver_raises(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "psycopg2":
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        with pytest.raises(ConnectorError, match="psycopg2"):
            get_connection("postgresql", {"host": "localhost", "port": 5432, "database": "test"})

    def test_mysql_missing_driver_raises(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pymysql":
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        with pytest.raises(ConnectorError, match="pymysql"):
            get_connection("mysql", {"host": "localhost"})

    def test_mssql_missing_driver_raises(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "pymssql":
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        with pytest.raises(ConnectorError, match="pymssql"):
            get_connection("mssql", {"host": "localhost"})

    def test_snowflake_missing_driver_raises(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "snowflake" in name:
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        with pytest.raises(ConnectorError, match="snowflake"):
            get_connection("snowflake", {"account": "x", "user": "y", "password": "z"})

    def test_bigquery_missing_driver_raises(self, monkeypatch):
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "google.cloud" in name or "google.oauth2" in name:
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        with pytest.raises(ConnectorError, match="google-cloud-bigquery"):
            get_connection("bigquery", {"project_id": "my-proj"})


# --- do_check_connection ----------------------------------------------------------

class TestTestConnection:
    def test_sqlite_success(self, sqlite_details):
        ok, msg = do_check_connection("sqlite", sqlite_details)
        assert ok is True
        assert "[OK]" in msg
        assert "SQLite" in msg

    def test_sqlite_bad_path_failure(self):
        ok, msg = do_check_connection("sqlite", {"database_path": "/no/such/file.db"})
        assert ok is False
        assert "[FAIL]" in msg

    def test_no_encoding_error_on_console(self, sqlite_details):
        """do_check_connection mesaji ASCII-safe olmali (Windows cp1254 uyumlu)."""
        ok, msg = do_check_connection("sqlite", sqlite_details)
        # Herhangi bir encoding ile encode edilebilmeli
        msg.encode("ascii", errors="strict")

    def test_unicode_variant_has_checkmark(self, sqlite_details):
        """do_check_connection_unicode emoji icermeli."""
        ok, msg = do_check_connection_unicode("sqlite", sqlite_details)
        assert ok is True
        assert "\u2705" in msg

    def test_unicode_variant_failure_has_cross(self):
        ok, msg = do_check_connection_unicode("sqlite", {"database_path": "/bad/path.db"})
        assert ok is False
        assert "\u274c" in msg

    def test_unsupported_type_returns_failure(self):
        ok, msg = do_check_connection("oracle", {})
        assert ok is False
        assert "[FAIL]" in msg


# --- discover_schema ----------------------------------------------------------

class TestDiscoverSchema:
    def test_discovers_all_tables(self, sqlite_details):
        schema = discover_schema("sqlite", sqlite_details)
        assert "products" in schema
        assert "orders" in schema

    def test_discovers_columns(self, sqlite_details):
        schema = discover_schema("sqlite", sqlite_details)
        assert "id" in schema["products"]
        assert "name" in schema["products"]
        assert "price" in schema["products"]
        assert "product_id" in schema["orders"]
        assert "amount" in schema["orders"]

    def test_schema_returns_dict(self, sqlite_details):
        schema = discover_schema("sqlite", sqlite_details)
        assert isinstance(schema, dict)
        for tbl, cols in schema.items():
            assert isinstance(tbl, str)
            assert isinstance(cols, list)
            assert len(cols) > 0

    def test_bad_connection_raises(self):
        with pytest.raises(Exception):
            discover_schema("sqlite", {"database_path": "/nonexistent.db"})


# --- execute_safe_sql ---------------------------------------------------------

class TestExecuteSafeSQL:
    def test_simple_select(self, sqlite_details):
        result = execute_safe_sql("sqlite", sqlite_details, "SELECT * FROM products")
        assert result["row_count"] == 2
        assert "id" in result["columns"]
        assert "name" in result["columns"]

    def test_aggregate_query(self, sqlite_details):
        result = execute_safe_sql(
            "sqlite", sqlite_details,
            "SELECT COUNT(*) AS cnt, SUM(price) AS total FROM products"
        )
        assert result["row_count"] == 1
        row = result["rows"][0]
        assert row[0] == 2

    def test_join_query(self, sqlite_details):
        result = execute_safe_sql(
            "sqlite", sqlite_details,
            "SELECT o.id, p.name, o.amount FROM orders o JOIN products p ON o.product_id = p.id"
        )
        assert result["row_count"] == 2
        assert "name" in result["columns"]

    def test_empty_result(self, sqlite_details):
        result = execute_safe_sql(
            "sqlite", sqlite_details,
            "SELECT * FROM products WHERE price > 999999"
        )
        assert result["row_count"] == 0
        assert result["rows"] == []
        assert "id" in result["columns"]

    def test_result_structure(self, sqlite_details):
        result = execute_safe_sql("sqlite", sqlite_details, "SELECT 1 AS num")
        assert "columns" in result
        assert "rows" in result
        assert "row_count" in result
        assert result["row_count"] == len(result["rows"])

    def test_bad_sql_raises(self, sqlite_details):
        with pytest.raises(Exception):
            execute_safe_sql("sqlite", sqlite_details, "SELECT * FROM nonexistent_table")


# --- discover_relationships ---------------------------------------------------

class TestDiscoverRelationships:
    def test_returns_list(self, sqlite_details):
        rels = discover_relationships("sqlite", sqlite_details)
        assert isinstance(rels, list)

    def test_bad_connection_returns_empty_list(self):
        rels = discover_relationships("sqlite", {"database_path": "/no/such.db"})
        assert rels == []

    def test_relationship_structure(self, sqlite_details):
        rels = discover_relationships("sqlite", sqlite_details)
        for rel in rels:
            assert "source_table" in rel
            assert "source_column" in rel
            assert "target_table" in rel
            assert "target_column" in rel


# --- metadata.db entegrasyon testi -------------------------------------------

class TestMetadataDBIntegration:
    """Backend'in kendi metadata.db'sini test eder."""

    @pytest.fixture()
    def metadata_details(self):
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        db_path = os.path.join(backend_dir, "metadata.db")
        if not os.path.exists(db_path):
            pytest.skip("metadata.db bulunamadi")
        return {"database_path": db_path}

    def test_metadata_db_connection(self, metadata_details):
        ok, msg = do_check_connection("sqlite", metadata_details)
        assert ok is True

    def test_metadata_db_schema_has_required_tables(self, metadata_details):
        schema = discover_schema("sqlite", metadata_details)
        required = {"sources", "sessions", "messages", "settings", "files"}
        missing = required - set(schema.keys())
        assert not missing, f"Eksik tablolar: {missing}"

    def test_metadata_sources_columns(self, metadata_details):
        schema = discover_schema("sqlite", metadata_details)
        assert "sources" in schema
        for col in ("id", "type", "display_name", "connection_details", "is_active"):
            assert col in schema["sources"], f"'sources' tablosunda '{col}' eksik"

    def test_metadata_sessions_columns(self, metadata_details):
        schema = discover_schema("sqlite", metadata_details)
        assert "sessions" in schema
        for col in ("id", "title", "active_source_id"):
            assert col in schema["sessions"], f"'sessions' tablosunda '{col}' eksik"

    def test_metadata_messages_columns(self, metadata_details):
        schema = discover_schema("sqlite", metadata_details)
        assert "messages" in schema
        for col in ("id", "session_id", "role", "text", "code"):
            assert col in schema["messages"], f"'messages' tablosunda '{col}' eksik"

    def test_metadata_settings_has_llm_keys(self, metadata_details):
        result = execute_safe_sql(
            "sqlite", metadata_details,
            "SELECT key FROM settings WHERE key IN ('deepseek_key','deepseek_url','deepseek_model')"
        )
        found_keys = {row[0] for row in result["rows"]}
        assert "deepseek_url" in found_keys
        assert "deepseek_model" in found_keys
