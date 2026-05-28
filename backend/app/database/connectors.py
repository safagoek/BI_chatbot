"""
app/database/connectors.py

Çok sürücülü veritabanı bağlantı ve şema keşif katmanı.
Desteklenen sürücüler: sqlite, postgresql, mysql
"""
import os
import json
import sqlite3
from typing import Dict, Any, List, Optional, Tuple


class ConnectorError(Exception):
    pass


def _get_sqlite_conn(details: Dict[str, Any]):
    db_path = details.get("database_path", "demo.db")
    # Relative path → resolve from backend root
    if not os.path.isabs(db_path):
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), db_path
        )
    if not os.path.exists(db_path):
        raise ConnectorError(f"SQLite dosyası bulunamadı: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"


def _get_postgresql_conn(details: Dict[str, Any]):
    try:
        import psycopg2
    except ImportError:
        raise ConnectorError("psycopg2-binary kurulu değil. 'pip install psycopg2-binary' çalıştırın.")
    
    host = details.get("host", "localhost")
    port = int(details.get("port", 5432))
    database = details.get("database", "")
    user = details.get("user", "")
    password = details.get("password", "")
    
    try:
        conn = psycopg2.connect(
            host=host, port=port, database=database,
            user=user, password=password,
            connect_timeout=5
        )
        return conn, "postgresql"
    except Exception as e:
        raise ConnectorError(f"PostgreSQL bağlantısı başarısız: {str(e)}")


def _get_mysql_conn(details: Dict[str, Any]):
    try:
        import pymysql
    except ImportError:
        raise ConnectorError("pymysql kurulu değil. 'pip install pymysql' çalıştırın.")
    
    host = details.get("host", "localhost")
    port = int(details.get("port", 3306))
    database = details.get("database", "")
    user = details.get("user", "")
    password = details.get("password", "")
    
    try:
        conn = pymysql.connect(
            host=host, port=port, database=database,
            user=user, password=password,
            connect_timeout=5,
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn, "mysql"
    except Exception as e:
        raise ConnectorError(f"MySQL bağlantısı başarısız: {str(e)}")


def _get_sap_s4hana_conn(details: Dict[str, Any]):
    try:
        from hdbcli import dbapi
    except ImportError:
        raise ConnectorError("hdbcli kurulu değil. 'pip install hdbcli' çalıştırın.")
    
    host = details.get("host", "localhost")
    port = int(details.get("port", 30015))
    user = details.get("user", "")
    password = details.get("password", "")
    
    try:
        conn = dbapi.connect(
            address=host,
            port=port,
            user=user,
            password=password
        )
        return conn, "sap_s4hana"
    except Exception as e:
        raise ConnectorError(f"SAP S/4HANA (HANA) bağlantısı başarısız: {str(e)}")


def get_connection(db_type: str, connection_details: Dict[str, Any]):
    """Returns a (connection, db_type) tuple based on db_type."""
    t = db_type.lower()
    if t == "sqlite":
        return _get_sqlite_conn(connection_details)
    elif t in ("postgresql", "postgres"):
        return _get_postgresql_conn(connection_details)
    elif t in ("mysql", "mariadb"):
        return _get_mysql_conn(connection_details)
    elif t in ("sap_s4hana", "hana", "s4hana"):
        return _get_sap_s4hana_conn(connection_details)
    else:
        raise ConnectorError(f"Desteklenmeyen veritabanı tipi: {db_type}")


def test_connection(db_type: str, connection_details: Dict[str, Any]) -> Tuple[bool, str]:
    """Tests connectivity and returns (success, message)."""
    try:
        conn, _ = get_connection(db_type, connection_details)
        
        # Run a ping query
        if db_type == "sqlite":
            cursor = conn.cursor()
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
            conn.close()
            return True, f"✅ SQLite bağlantısı başarılı. Sürüm: {version}"
        elif db_type in ("sap_s4hana", "hana", "s4hana"):
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM DUMMY")
            conn.close()
            return True, "✅ SAP S/4HANA (HANA) bağlantısı başarılı."
        else:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 AS ping")
            conn.close()
            return True, f"✅ {db_type.upper()} bağlantısı başarılı."
    except ConnectorError as e:
        return False, f"❌ {str(e)}"
    except Exception as e:
        return False, f"❌ Beklenmeyen bağlantı hatası: {str(e)}"


def discover_schema(db_type: str, connection_details: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Automatically discovers all tables and their column names.
    Returns: { "table_name": ["col1", "col2", ...], ... }
    """
    conn, dtype = get_connection(db_type, connection_details)
    schema = {}
    
    try:
        cursor = conn.cursor()
        
        if dtype == "sqlite":
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            for tbl in tables:
                cursor.execute(f"PRAGMA table_info(`{tbl}`)")
                cols = [row[1] for row in cursor.fetchall()]
                schema[tbl] = cols
                
        elif dtype == "postgresql":
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cursor.fetchall()]
            for tbl in tables:
                cursor.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema='public' AND table_name = %s
                    ORDER BY ordinal_position
                """, (tbl,))
                cols = [row[0] for row in cursor.fetchall()]
                schema[tbl] = cols
                
        elif dtype == "mysql":
            cursor.execute("SELECT DATABASE()")
            row = cursor.fetchone()
            db_name = row["DATABASE()"] if isinstance(row, dict) else row[0]
            
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """, (db_name,))
            rows = cursor.fetchall()
            tables = [r["table_name"] if isinstance(r, dict) else r[0] for r in rows]
            
            for tbl in tables:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                """, (db_name, tbl))
                rows = cursor.fetchall()
                cols = [r["column_name"] if isinstance(r, dict) else r[0] for r in rows]
                schema[tbl] = cols
        
        elif dtype == "sap_s4hana":
            schema_name = connection_details.get("schema", "").strip()
            if not schema_name:
                cursor.execute("SELECT CURRENT_SCHEMA FROM DUMMY")
                row = cursor.fetchone()
                schema_name = row[0] if row else "SYSTEM"
            
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM SYS.TABLES 
                WHERE SCHEMA_NAME = ? 
                ORDER BY TABLE_NAME
            """, (schema_name,))
            tables = [row[0] for row in cursor.fetchall()]
            
            for tbl in tables:
                cursor.execute("""
                    SELECT COLUMN_NAME 
                    FROM SYS.TABLE_COLUMNS 
                    WHERE SCHEMA_NAME = ? AND TABLE_NAME = ?
                    ORDER BY POSITION
                """, (schema_name, tbl))
                cols = [row[0] for row in cursor.fetchall()]
                schema[tbl] = cols
                
        return schema
        
    finally:
        conn.close()


def execute_safe_sql(db_type: str, connection_details: Dict[str, Any], sql: str) -> Dict[str, Any]:
    """
    Executes a pre-sanitized SELECT query and returns structured results.
    """
    conn, dtype = get_connection(db_type, connection_details)
    
    try:
        if dtype == "sqlite":
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = [list(r) for r in cursor.fetchall()]
        elif dtype == "postgresql":
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = [list(r) for r in cursor.fetchall()]
        elif dtype == "mysql":
            cursor = conn.cursor()
            cursor.execute(sql)
            rows_raw = cursor.fetchall()
            if rows_raw:
                if isinstance(rows_raw[0], dict):
                    columns = list(rows_raw[0].keys())
                    rows = [list(r.values()) for r in rows_raw]
                else:
                    columns = [desc[0] for desc in cursor.description]
                    rows = [list(r) for r in rows_raw]
            else:
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = []
        elif dtype == "sap_s4hana":
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description]
            rows = [list(r) for r in cursor.fetchall()]
        else:
            raise ConnectorError(f"Desteklenmeyen tip: {dtype}")
            
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
        
    finally:
        conn.close()
