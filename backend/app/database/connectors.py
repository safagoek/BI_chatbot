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
    if "database_path" not in details or not details["database_path"]:
        raise ConnectorError("SQLite bağlantısı için database_path gerekli")
    db_path = details["database_path"]
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

def _get_snowflake_conn(details: Dict[str, Any]):
    try:
        import snowflake.connector
    except ImportError:
        raise ConnectorError("snowflake-connector-python kurulu değil. 'pip install snowflake-connector-python' çalıştırın.")
    
    account = details.get("account", "")
    user = details.get("user", "")
    password = details.get("password", "")
    warehouse = details.get("warehouse", "")
    database = details.get("database", "")
    schema = details.get("schema", "")
    
    try:
        conn = snowflake.connector.connect(
            account=account,
            user=user,
            password=password,
            warehouse=warehouse,
            database=database,
            schema=schema
        )
        return conn, "snowflake"
    except Exception as e:
        raise ConnectorError(f"Snowflake bağlantısı başarısız: {str(e)}")


def _get_mssql_conn(details: Dict[str, Any]):
    try:
        import pymssql
    except ImportError:
        raise ConnectorError("pymssql kurulu değil. 'pip install pymssql' çalıştırın.")
    
    host = details.get("host", "localhost")
    port = int(details.get("port", 1433))
    database = details.get("database", "")
    user = details.get("user", "")
    password = details.get("password", "")
    
    try:
        conn = pymssql.connect(
            server=host,
            port=port,
            database=database,
            user=user,
            password=password,
            timeout=5
        )
        return conn, "mssql"
    except Exception as e:
        raise ConnectorError(f"MSSQL bağlantısı başarısız: {str(e)}")


def _get_bigquery_conn(details: Dict[str, Any]):
    try:
        from google.cloud import bigquery
        from google.oauth2 import service_account
    except ImportError:
        raise ConnectorError("google-cloud-bigquery kurulu değil. 'pip install google-cloud-bigquery google-auth' çalıştırın.")
    
    project_id = details.get("project_id", "")
    credentials_json = details.get("credentials_json", "")
    credentials_path = details.get("credentials_path", "")
    
    try:
        if credentials_json:
            import json
            info = json.loads(credentials_json)
            credentials = service_account.Credentials.from_service_account_info(info)
            client = bigquery.Client(project=project_id, credentials=credentials)
        elif credentials_path:
            client = bigquery.Client.from_service_account_json(credentials_path)
        else:
            client = bigquery.Client(project=project_id) if project_id else bigquery.Client()
        return client, "bigquery"
    except Exception as e:
        raise ConnectorError(f"Google BigQuery bağlantısı başarısız: {str(e)}")


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
    elif t == "snowflake":
        return _get_snowflake_conn(connection_details)
    elif t in ("mssql", "sqlserver"):
        return _get_mssql_conn(connection_details)
    elif t in ("bigquery", "google_bigquery"):
        return _get_bigquery_conn(connection_details)
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
        elif db_type in ("bigquery", "google_bigquery"):
            # List datasets to verify credentials/connection
            list(conn.list_datasets(max_results=1))
            return True, "✅ Google BigQuery bağlantısı başarılı."
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
        if dtype == "bigquery":
            datasets = list(conn.list_datasets())
            for dataset in datasets:
                dataset_id = dataset.dataset_id
                tables = list(conn.list_tables(dataset_id))
                for table in tables:
                    tbl_name = f"{dataset_id}.{table.table_id}"
                    table_ref = conn.get_table(table.reference)
                    cols = [field.name for field in table_ref.schema]
                    schema[tbl_name] = cols
            return schema

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
                cursor.execute("""
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

        elif dtype == "snowflake":
            current_schema = connection_details.get("schema", "").strip().upper()
            current_database = connection_details.get("database", "").strip().upper()
            
            if not current_schema or not current_database:
                cursor.execute("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA()")
                db_res = cursor.fetchone()
                if db_res:
                    if not current_database:
                        current_database = db_res[0]
                    if not current_schema:
                        current_schema = db_res[1]
            
            if current_database and current_schema:
                cursor.execute(f"""
                    SELECT table_name 
                    FROM {current_database}.information_schema.tables 
                    WHERE table_schema = '{current_schema}' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                tables = [row[0] for row in cursor.fetchall()]
                for tbl in tables:
                    cursor.execute(f"""
                        SELECT column_name 
                        FROM {current_database}.information_schema.columns 
                        WHERE table_schema = '{current_schema}' AND table_name = '{tbl}'
                        ORDER BY ordinal_position
                    """)
                    cols = [row[0] for row in cursor.fetchall()]
                    schema[tbl] = cols

        elif dtype == "mssql":
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cursor.fetchall()]
            for tbl in tables:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """, (tbl,))
                cols = [row[0] for row in cursor.fetchall()]
                schema[tbl] = cols
                
        return schema
        
    finally:
        if dtype != "bigquery":
            conn.close()


def execute_safe_sql(db_type: str, connection_details: Dict[str, Any], sql: str) -> Dict[str, Any]:
    """
    Executes a pre-sanitized SELECT query and returns structured results.
    """
    conn, dtype = get_connection(db_type, connection_details)
    
    try:
        if dtype == "bigquery":
            query_job = conn.query(sql)
            results = query_job.result()
            columns = [field.name for field in results.schema]
            rows = [list(row.values()) for row in results]
        elif dtype in ("sqlite", "postgresql", "sap_s4hana", "snowflake", "mssql"):
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
        else:
            raise ConnectorError(f"Desteklenmeyen tip: {dtype}")
            
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
        
    finally:
        if dtype != "bigquery":
            conn.close()

def discover_relationships(db_type: str, connection_details: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Extracts Foreign Key relationships from the database.
    Returns: [{"source_table": "...", "source_column": "...", "target_table": "...", "target_column": "..."}, ...]
    """
    conn, dtype = get_connection(db_type, connection_details)
    relationships = []
    
    try:
        cursor = conn.cursor()
        
        if dtype == "sqlite":
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            for tbl in tables:
                cursor.execute(f"PRAGMA foreign_key_list(`{tbl}`)")
                for row in cursor.fetchall():
                    relationships.append({
                        "source_table": tbl,
                        "source_column": row["from"],
                        "target_table": row["table"],
                        "target_column": row["to"]
                    })
                    
        elif dtype == "postgresql":
            cursor.execute("""
                SELECT
                    tc.table_name AS source_table,
                    kcu.column_name AS source_column,
                    ccu.table_name AS target_table,
                    ccu.column_name AS target_column
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema='public';
            """)
            for row in cursor.fetchall():
                relationships.append({
                    "source_table": row[0],
                    "source_column": row[1],
                    "target_table": row[2],
                    "target_column": row[3]
                })
                
        elif dtype == "mysql":
            cursor.execute("SELECT DATABASE()")
            row = cursor.fetchone()
            db_name = row["DATABASE()"] if isinstance(row, dict) else row[0]
            
            cursor.execute("""
                SELECT 
                    TABLE_NAME as source_table,
                    COLUMN_NAME as source_column,
                    REFERENCED_TABLE_NAME as target_table,
                    REFERENCED_COLUMN_NAME as target_column
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE REFERENCED_TABLE_SCHEMA = %s;
            """, (db_name,))
            for r in cursor.fetchall():
                relationships.append({
                    "source_table": r["source_table"] if isinstance(r, dict) else r[0],
                    "source_column": r["source_column"] if isinstance(r, dict) else r[1],
                    "target_table": r["target_table"] if isinstance(r, dict) else r[2],
                    "target_column": r["target_column"] if isinstance(r, dict) else r[3]
                })
        
        return relationships
    except Exception:
        # Silently fail for unsupported types or permission errors
        return []
    finally:
        if dtype != "bigquery":
            conn.close()


