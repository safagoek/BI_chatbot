"""
app/database/connectors.py

Çok sürücülü veritabanı bağlantı ve şema keşif katmanı.
Desteklenen sürücüler: sqlite, postgresql, mysql, mssql, sap_s4hana, snowflake, bigquery
"""
import os
import json
import logging
import sqlite3
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)
from app.core import breaker


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
        query_timeout = int(details.get("query_timeout", 30))
        conn = psycopg2.connect(
            host=host, port=port, database=database,
            user=user, password=password,
            connect_timeout=5,
            # Sorgu seviyesi timeout — yavaş sorgu thread'i süresiz meşgul etmesin
            options=f"-c statement_timeout={query_timeout * 1000}"
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
            read_timeout=int(details.get("query_timeout", 30)),
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
    try:
        port = int(details.get("port", 30015))
    except (TypeError, ValueError):
        raise ConnectorError(f"HANA portu sayısal olmalı, gelen değer: {details.get('port')!r} "
                             "(örnek: 30015 tek-container, 30041 tenant DB)")
    user = details.get("user", "")
    password = details.get("password", "")
    schema = (details.get("schema") or "").strip()

    # TLS/dağıtım ayarları: varsayılanlar hdbcli'ye bırakılır; kullanıcı
    # connection_details üzerinden geçirebilir (örn. self-signed sertifika için).
    connect_kwargs: Dict[str, Any] = dict(
        address=host, port=port, user=user, password=password,
        statementTimeout=int(details.get("query_timeout", 30)) * 1000,
    )
    for opt in ("encrypt", "sslValidateCertificate", "communicationTimeout", "packetSize", "connectTimeout"):
        if opt in details and details[opt] not in (None, ""):
            connect_kwargs[opt] = details[opt]

    try:
        conn = dbapi.connect(**connect_kwargs)
    except Exception as e:
        raise ConnectorError(f"SAP S/4HANA (HANA) bağlantısı başarısız: {str(e)}")

    # Şema verilmişse oturumda CURRENT_SCHEMA olarak ayarla — aksi halde
    # nitelenmemiş tablo sorguları kullanıcının default şemasında aranır.
    if schema:
        try:
            cur = conn.cursor()
            cur.execute('SET SCHEMA "{}"'.format(schema.replace('"', '""')))
            cur.close()
        except Exception as e:
            conn.close()
            raise ConnectorError(f"HANA şeması ayarlanamadı ('{schema}'): {str(e)}")

    return conn, "sap_s4hana"

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
            login_timeout=5,
            timeout=int(details.get("query_timeout", 30))
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
    open_, remaining = breaker.is_open(db_type, connection_details)
    if open_:
        raise ConnectorError(
            f"{db_type} bağlantısı devre kesici tarafından geçici olarak bloklandı "
            f"(art arda hatalar). {remaining} sn sonra tekrar denenecek."
        )
    try:
        conn, dtype = _get_connection_impl(db_type, connection_details)
    except ConnectorError:
        breaker.record_failure(db_type, connection_details)
        raise
    except Exception:
        breaker.record_failure(db_type, connection_details)
        raise
    breaker.record_success(db_type, connection_details)
    return conn, dtype


def _get_connection_impl(db_type: str, connection_details: Dict[str, Any]):
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


def check_connection(db_type: str, connection_details: Dict[str, Any]) -> Tuple[bool, str]:
    """Tests connectivity and returns (success, message). ASCII-safe mesaj (Windows konsol uyumlu)."""
    conn = None
    try:
        conn, dtype = get_connection(db_type, connection_details)

        # Run a ping query
        if dtype == "sqlite":
            cursor = conn.cursor()
            cursor.execute("SELECT sqlite_version()")
            row = cursor.fetchone()
            # sqlite3.Row veya tuple olabilir
            version = row[0] if row else "?"
            return True, f"[OK] SQLite baglantisi basarili. Surum: {version}"
        elif dtype in ("sap_s4hana", "hana", "s4hana"):
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM DUMMY")
            cursor.close()
            # Aktif şema bilgisini kullanıcıya göster
            schema = (connection_details.get("schema") or "").strip()
            schema_msg = f". Schema: {schema}" if schema else ""
            return True, f"[OK] SAP S/4HANA (HANA) baglantisi basarili{schema_msg}."
        elif dtype in ("bigquery", "google_bigquery"):
            # List datasets to verify credentials/connection
            list(conn.list_datasets(max_results=1))
            return True, "[OK] Google BigQuery baglantisi basarili."
        else:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 AS ping")
            conn.close()
            conn = None
            return True, f"[OK] {db_type.upper()} baglantisi basarili."
    except ConnectorError as e:
        return False, f"[FAIL] {str(e)}"
    except Exception as e:
        return False, f"[FAIL] Beklenmeyen baglanti hatasi: {str(e)}"
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def check_connection_unicode(db_type: str, connection_details: Dict[str, Any]) -> Tuple[bool, str]:
    """check_connection wrapper — Unicode emoji'li mesaj döner (API/frontend için)."""
    success, msg = check_connection(db_type, connection_details)
    prefix = "\u2705" if success else "\u274c"
    # [OK] / [FAIL] prefix'ini emoji ile değiştir
    msg = msg.replace("[OK]", f"{prefix}").replace("[FAIL]", f"{prefix}")
    return success, msg


# Geriye dönük uyumluluk alias'ları
test_connection = check_connection
test_connection_unicode = check_connection_unicode


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
                cursor.execute(f"PRAGMA table_info(`{tbl.replace('`', '``')}`)")
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
            # SAP S/4HANA şemaları (örn. SAPHANADB) on binlerce tablo içerebilir.
            # Keşif bu yüzden filtreli ve TOPLU sorguyla yapılır; aksi halde
            # tablo başına ayrı sorgu dakikalar sürer ve şema kullanılamaz olur.
            schema_name = (connection_details.get("schema") or "").strip()
            if not schema_name:
                cursor.execute("SELECT CURRENT_SCHEMA FROM DUMMY")
                row = cursor.fetchone()
                schema_name = row[0] if row else "SYSTEM"

            max_tables = int(connection_details.get("max_tables", 500) or 500)
            # table_filter: virgülle ayrılmış LIKE desenleri (örn. "KNA%,VBAK%,MARA%")
            filters = [f.strip() for f in str(connection_details.get("table_filter") or "").split(",") if f.strip()]

            where = "SCHEMA_NAME = ? AND IS_USER_TYPE = 'USER'"
            params: List[Any] = [schema_name]
            # SAP namespace tablolarını (/1BF/, /SAPAPO/ ...) ve sistem objelerini dışla
            exclude = [
                "TABLE_NAME NOT LIKE '/%'",
                "TABLE_NAME NOT LIKE 'SAP_%'",
                "TABLE_NAME NOT LIKE '~%'",
            ]
            if filters:
                ors = " OR ".join(["TABLE_NAME LIKE ?" for _ in filters])
                exclude.append(f"({ors})")
                params.extend(filters)
            where += " AND " + " AND ".join(exclude)

            cursor.execute(f"""
                SELECT TABLE_NAME
                FROM SYS.TABLES
                WHERE {where}
                ORDER BY TABLE_NAME
                LIMIT {max_tables}
            """, params)
            tables = [row[0] for row in cursor.fetchall()]

            if tables:
                # Kolonları TEK sorguda çek (tablo başına sorgu yok)
                col_params: List[Any] = [schema_name]
                placeholders = ", ".join(["?" for _ in tables])
                cursor.execute(f"""
                    SELECT TABLE_NAME, COLUMN_NAME, POSITION
                    FROM SYS.TABLE_COLUMNS
                    WHERE SCHEMA_NAME = ? AND TABLE_NAME IN ({placeholders})
                    ORDER BY TABLE_NAME, POSITION
                """, col_params + tables)
                for row in cursor.fetchall():
                    schema.setdefault(row[0], []).append(row[1])

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
                # information_schema bir veritabanı adıyla nitelenir; identifier'lar
                # çift tırnakla kaçırılarak interpolation injection'ı engellenir.
                def _q_ident(name: str) -> str:
                    return '"' + name.replace('"', '""') + '"'
                cursor.execute(f"""
                    SELECT table_name
                    FROM {_q_ident(current_database)}.information_schema.tables
                    WHERE table_schema = %s AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """, (current_schema,))
                tables = [row[0] for row in cursor.fetchall()]
                for tbl in tables:
                    cursor.execute(f"""
                        SELECT column_name
                        FROM {_q_ident(current_database)}.information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position
                    """, (current_schema, tbl))
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
                # pymssql uses %s for ALL parameter types (string substitution)
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
        if dtype not in ("bigquery",):
            try:
                cursor.close()
            except Exception:
                pass
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
            rows_raw = cursor.fetchall()
            if dtype == "sap_s4hana":
                # hdbcli LOB kolonları locator nesnesi olarak döndürebilir;
                # aşağı akış (pandas/DuckDB) string bekler.
                def _hana_val(v: Any) -> Any:
                    return v.read() if hasattr(v, "read") and callable(v.read) else v
                rows = [[_hana_val(v) for v in r] for r in rows_raw]
            else:
                rows = [list(r) for r in rows_raw]
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
    relationships = []
    conn = None
    dtype = None

    try:
        conn, dtype = get_connection(db_type, connection_details)
        cursor = conn.cursor()
        
        if dtype == "sqlite":
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            for tbl in tables:
                cursor.execute(f"PRAGMA foreign_key_list(`{tbl.replace('`', '``')}`)")
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
        
        elif dtype == "sap_s4hana":
            # HANA katalog görünümü üzerinden FK ilişkileri
            schema_name = (connection_details.get("schema") or "").strip()
            if not schema_name:
                cursor.execute("SELECT CURRENT_SCHEMA FROM DUMMY")
                row = cursor.fetchone()
                schema_name = row[0] if row else "SYSTEM"
            cursor.execute("""
                SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                FROM REFERENTIAL_CONSTRAINTS
                WHERE SCHEMA_NAME = ? AND REFERENCED_TABLE_NAME IS NOT NULL
                ORDER BY TABLE_NAME
            """, (schema_name,))
            for row in cursor.fetchall():
                relationships.append({
                    "source_table": row[0],
                    "source_column": row[1],
                    "target_table": row[2],
                    "target_column": row[3]
                })

        return relationships
    except (ConnectorError, Exception) as e:
        logger.warning("İlişki keşfi başarısız (db_type=%s): %s", db_type, e)
        return []
    finally:
        if conn is not None and dtype not in ("bigquery",):
            try:
                cursor.close()
            except Exception:
                pass
            conn.close()




def discover_cds_views(connection_details: Dict[str, Any], max_views: int = 300) -> Dict[str, List[str]]:
    """
    SAP S/4HANA released CDS view keşfi (VDM: I_*/C_* view'ları).

    SAP, S/4HANA analitiği için ham tablolar yerine yayınlanmış (released) CDS
    view'larını önerir. Bu fonksiyon:
      1. RELEASED_OBJECTS katalog görünümü varsa onu kullanır (en doğru kaynak),
      2. yoksa SYS.VIEWS üzerinden geçerli I_/C_ önekli view'ları alır,
      3. kolonları SYS.VIEW_COLUMNS'dan toplu çeker.

    connection_details ek anahtarları:
      - schema:      hedef S/4 şeması (boşsa CURRENT_SCHEMA)
      - max_views:   üst sınır (varsayılan 300)
    Döndürülen şema, discover_schema sonucuyla birleştirilip ajan hattına verilir.
    """
    max_views = int(connection_details.get("max_views", max_views))
    conn, dtype = get_connection("sap_s4hana", connection_details)
    if dtype != "sap_s4hana":
        return {}
    schema_out: Dict[str, List[str]] = {}
    try:
        cursor = conn.cursor()
        schema_name = (connection_details.get("schema") or "").strip()
        if not schema_name:
            cursor.execute("SELECT CURRENT_SCHEMA FROM DUMMY")
            row = cursor.fetchone()
            schema_name = row[0] if row else "SYSTEM"

        view_names: List[str] = []
        # 1) Released katalog denemesi (her sistemde yok — sessizce düş)
        try:
            cursor.execute(
                """
                SELECT DISTINCT v.VIEW_NAME
                FROM SYS.VIEWS v
                JOIN RELEASED_OBJECTS r ON r.OBJECT_NAME = v.VIEW_NAME
                WHERE v.SCHEMA_NAME = ? AND v.IS_VALID = 'TRUE'
                ORDER BY v.VIEW_NAME
                LIMIT ?
                """,
                (schema_name, int(max_views)),
            )
            view_names = [row[0] for row in cursor.fetchall()]
        except Exception:
            view_names = []

        # 2) Fallback / tamamlayıcı: I_ ve C_ önekli geçerli view'lar
        cursor.execute(
            """
            SELECT VIEW_NAME
            FROM SYS.VIEWS
            WHERE SCHEMA_NAME = ? AND IS_VALID = 'TRUE'
              AND (VIEW_NAME LIKE 'I\\_%' ESCAPE '\\' OR VIEW_NAME LIKE 'C\\_%' ESCAPE '\\')
              AND VIEW_NAME NOT LIKE '%\\_P' ESCAPE '\\'
            ORDER BY VIEW_NAME
            LIMIT ?
            """,
            (schema_name, int(max_views)),
        )
        for row in cursor.fetchall():
            if row[0] not in view_names:
                view_names.append(row[0])
        view_names = view_names[: int(max_views)]

        if not view_names:
            return {}

        placeholders = ", ".join(["?" for _ in view_names])
        cursor.execute(
            f"""
            SELECT VIEW_NAME, COLUMN_NAME, POSITION
            FROM SYS.VIEW_COLUMNS
            WHERE SCHEMA_NAME = ? AND VIEW_NAME IN ({placeholders})
            ORDER BY VIEW_NAME, POSITION
            """,
            [schema_name] + view_names,
        )
        for row in cursor.fetchall():
            schema_out.setdefault(row[0], []).append(row[1])
        return schema_out
    finally:
        try:
            conn.close()
        except Exception:
            pass
