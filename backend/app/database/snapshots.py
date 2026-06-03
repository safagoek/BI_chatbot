import os
import sqlite3
import datetime
from typing import Dict, Any, List, Optional
from app.database.manager import get_data_source_by_id, add_data_source
from app.database.connectors import get_connection

SNAPSHOTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "snapshots"
)

def yield_database_snapshot_progress(source_id: str, selected_tables: Optional[List[str]] = None):
    """
    Connects to a remote database (PostgreSQL, MySQL, SAP HANA),
    extracts all tables in batches, and dumps them into a local SQLite file.
    Registers the newly created SQLite backup file as an offline SQLite data source.
    Yields JSON progress messages step-by-step.
    """
    # 1. Fetch remote source metadata
    yield {"status": "start", "message": "Hedef veri kaynağı sorgulanıyor..."}
    src = get_data_source_by_id(source_id)
    if not src:
        yield {"status": "error", "message": "Hedef veri kaynağı bulunamadı."}
        return
    
    if src["type"] == "sqlite":
        yield {"status": "error", "message": "SQLite kaynakları zaten yereldir, snapshot alınamaz."}
        return
        
    display_name = src["display_name"]
    db_type = src["type"]
    details = src["connection_details"]
    
    # Ensure snapshots directory exists
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    
    # 2. Define local SQLite snapshot database path
    snapshot_filename = f"{source_id}_snapshot.db"
    snapshot_path = os.path.join(SNAPSHOTS_DIR, snapshot_filename)
    
    # If a previous snapshot exists, delete it to overwrite
    if os.path.exists(snapshot_path):
        try:
            os.remove(snapshot_path)
            yield {"status": "info", "message": "Eski snapshot dosyası temizlendi."}
        except OSError as e:
            yield {"status": "error", "message": f"Eski snapshot yedeği silinemedi: {str(e)}"}
            return
            
    # Connect to the remote database to pull schema and data
    yield {"status": "info", "message": "Uzak veritabanına bağlanılıyor..."}
    try:
        remote_conn, _ = get_connection(db_type, details)
        if db_type not in ("bigquery", "google_bigquery"):
            remote_cursor = remote_conn.cursor()
    except Exception as e:
        yield {"status": "error", "message": f"Uzak veritabanı bağlantı hatası: {str(e)}"}
        return
    
    # Connect to the local SQLite database that will house the snapshot
    local_conn = sqlite3.connect(snapshot_path)
    local_cursor = local_conn.cursor()
    
    discovered_schema: Dict[str, List[str]] = {}
    
    try:
        # Discover all tables and columns dynamically
        # 3. Tables Fetching depending on DB type
        yield {"status": "info", "message": "Veritabanı tabloları keşfediliyor..."}
        if db_type in ("postgresql", "postgres"):
            remote_cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            tables = [row[0] for row in remote_cursor.fetchall()]
        elif db_type in ("mysql", "mariadb"):
            remote_cursor.execute("SELECT DATABASE()")
            db_name = remote_cursor.fetchone()[0]
            remote_cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = %s AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """, (db_name,))
            tables = [row[0] for row in remote_cursor.fetchall()]
        elif db_type in ("sap_s4hana", "hana", "s4hana"):
            schema_name = details.get("schema", "").strip()
            if not schema_name:
                remote_cursor.execute("SELECT CURRENT_SCHEMA FROM DUMMY")
                schema_name = remote_cursor.fetchone()[0]
            remote_cursor.execute("""
                SELECT TABLE_NAME 
                FROM SYS.TABLES 
                WHERE SCHEMA_NAME = ? 
                ORDER BY TABLE_NAME
            """, (schema_name,))
            tables = [row[0] for row in remote_cursor.fetchall()]
        elif db_type == "snowflake":
            current_schema = details.get("schema", "").strip().upper()
            current_database = details.get("database", "").strip().upper()
            if not current_schema or not current_database:
                remote_cursor.execute("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA()")
                db_res = remote_cursor.fetchone()
                if db_res:
                    if not current_database:
                        current_database = db_res[0]
                    if not current_schema:
                        current_schema = db_res[1]
            if current_database and current_schema:
                remote_cursor.execute(f"""
                    SELECT table_name 
                    FROM {current_database}.information_schema.tables 
                    WHERE table_schema = '{current_schema}' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                tables = [row[0] for row in remote_cursor.fetchall()]
            else:
                tables = []
        elif db_type in ("mssql", "sqlserver"):
            remote_cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            tables = [row[0] for row in remote_cursor.fetchall()]
        elif db_type in ("bigquery", "google_bigquery"):
            datasets = list(remote_conn.list_datasets())
            tables = []
            for d in datasets:
                tbls = list(remote_conn.list_tables(d.dataset_id))
                for t in tbls:
                    tables.append(f"{d.dataset_id}.{t.table_id}")
        else:
            yield {"status": "error", "message": f"Desteklenmeyen veritabanı türü: {db_type}"}
            return

        if selected_tables is not None:
            tables = [t for t in tables if t in selected_tables]
            if not tables:
                yield {"status": "error", "message": "Seçilen tabloların hiçbirisi veritabanında bulunamadı."}
                return

        yield {"status": "schema", "message": f"{len(tables)} adet tablo keşfedildi.", "tables": tables}

        # 4. Process each table: schema creation and batch inserts
        for idx, table in enumerate(tables):
            yield {"status": "table_start", "table": table, "index": idx, "total": len(tables), "message": f"'{table}' tablosu kopyalanıyor..."}
            
            sqlite_table_name = table.replace(".", "__")
            
            # Query column names
            if db_type in ("postgresql", "postgres"):
                remote_cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema='public' AND table_name = %s
                    ORDER BY ordinal_position
                """, (table,))
                columns = [row[0] for row in remote_cursor.fetchall()]
            elif db_type in ("mysql", "mariadb"):
                remote_cursor.execute("SELECT DATABASE()")
                db_name = remote_cursor.fetchone()[0]
                remote_cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                """, (db_name, table))
                columns = [row[0] for row in remote_cursor.fetchall()]
            elif db_type in ("sap_s4hana", "hana", "s4hana"):
                schema_name = details.get("schema", "").strip()
                if not schema_name:
                    remote_cursor.execute("SELECT CURRENT_SCHEMA FROM DUMMY")
                    schema_name = remote_cursor.fetchone()[0]
                remote_cursor.execute("""
                    SELECT COLUMN_NAME 
                    FROM SYS.COLUMNS 
                    WHERE SCHEMA_NAME = ? AND TABLE_NAME = ?
                    ORDER BY POSITION
                """, (schema_name, table))
                columns = [row[0] for row in remote_cursor.fetchall()]
            elif db_type == "snowflake":
                current_schema = details.get("schema", "").strip().upper()
                current_database = details.get("database", "").strip().upper()
                remote_cursor.execute(f"""
                    SELECT column_name 
                    FROM {current_database}.information_schema.columns 
                    WHERE table_schema = '{current_schema}' AND table_name = '{table.upper()}'
                    ORDER BY ordinal_position
                """)
                columns = [row[0] for row in remote_cursor.fetchall()]
            elif db_type in ("mssql", "sqlserver"):
                remote_cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """, (table,))
                columns = [row[0] for row in remote_cursor.fetchall()]
            elif db_type in ("bigquery", "google_bigquery"):
                table_ref = remote_conn.get_table(table)
                columns = [field.name for field in table_ref.schema]
            else:
                columns = []
            
            if not columns:
                yield {"status": "table_done", "table": table, "rows_total": 0, "message": f"'{table}' tablosunun sütun şeması alınamadığı için atlandı."}
                continue
                
            discovered_schema[sqlite_table_name] = columns
            
            # Create SQLite Table
            safe_cols = ", ".join([f'"{col}"' for col in columns])
            create_sql = f'CREATE TABLE IF NOT EXISTS "{sqlite_table_name}" ({safe_cols})'
            local_cursor.execute(create_sql)
            
            # Select and fetch rows in batches (düşük RAM tüketimi için 5000'er satır)
            if db_type in ("mysql", "mariadb", "bigquery", "google_bigquery"):
                safe_table = f"`{table}`"
            else:
                safe_table = f'"{table}"'
                
            try:
                if db_type in ("bigquery", "google_bigquery"):
                    query_job = remote_conn.query(f"SELECT * FROM {safe_table}")
                    bq_rows = query_job.result()
                else:
                    remote_cursor.execute(f"SELECT * FROM {safe_table}")
            except Exception as e:
                yield {"status": "table_error", "table": table, "message": f"'{table}' tablosundan veri okunamadı: {str(e)}"}
                continue
            
            placeholders = ", ".join(["?"] * len(columns))
            insert_sql = f'INSERT INTO "{sqlite_table_name}" VALUES ({placeholders})'
            
            total_copied = 0
            if db_type in ("bigquery", "google_bigquery"):
                bq_iterator = iter(bq_rows)
                while True:
                    batch = []
                    for _ in range(5000):
                        try:
                            batch.append(next(bq_iterator))
                        except StopIteration:
                            break
                    if not batch:
                        break
                    normalized_rows = []
                    for row in batch:
                        normalized_rows.append([None if item is None else str(item) if type(item) in (dict, list) else item for item in row.values()])
                    local_cursor.executemany(insert_sql, normalized_rows)
                    total_copied += len(batch)
                    yield {"status": "table_progress", "table": table, "rows_copied": total_copied, "message": f"'{table}' tablosundan {total_copied} satır kopyalandı..."}
            else:
                while True:
                    rows = remote_cursor.fetchmany(5000)
                    if not rows:
                        break
                    normalized_rows = []
                    for row in rows:
                        normalized_rows.append([None if item is None else str(item) if type(item) in (dict, list) else item for item in row])
                    local_cursor.executemany(insert_sql, normalized_rows)
                    
                    total_copied += len(rows)
                    yield {"status": "table_progress", "table": table, "rows_copied": total_copied, "message": f"'{table}' tablosundan {total_copied} satır kopyalandı..."}
                
            # Smart Auto-indexing to accelerate downstream analytical DuckDB joins/queries
            indexes_created = 0
            for col in columns:
                col_lower = col.lower()
                if any(kw in col_lower for kw in ["id", "key", "kod", "no", "tarih", "date", "vbeln", "matnr", "kunnr"]):
                    index_name = f"idx_{sqlite_table_name}_{col_lower}"
                    index_name = "".join([c if c.isalnum() else "_" for c in index_name])
                    try:
                        local_cursor.execute(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{sqlite_table_name}" ("{col}")')
                        indexes_created += 1
                    except Exception:
                        pass
            
            local_conn.commit()
            yield {"status": "table_done", "table": table, "rows_total": total_copied, "indexes_count": indexes_created, "message": f"'{table}' tablosu başarıyla tamamlandı ({total_copied} satır kopyalandı, {indexes_created} akıllı indeks oluşturuldu)."}
                        
        yield {"status": "info", "message": "Yerel veritabanı kayıtları tamamlanıyor..."}
        
    except Exception as e:
        yield {"status": "error", "message": f"Kritik Hata: {str(e)}"}
        return
    finally:
        if db_type not in ("bigquery", "google_bigquery"):
            try:
                remote_conn.close()
            except Exception:
                pass
        local_conn.close()
        
    # 5. Register the snapshot as an offline SQLite source in metadata DB
    snapshot_source_id = f"{source_id}_snapshot"
    snapshot_display_name = f"{display_name} - Yerel Snapshot (Yedek)"
    
    # Store path relative to backend root
    relative_path = os.path.join("snapshots", snapshot_filename)
    
    snapshot_details = {
        "database_path": relative_path,
        "is_snapshot": True,
        "parent_source_id": source_id,
        "snapshot_date": datetime.datetime.now().isoformat()
    }
    
    # Register or overwrite the source in sources metadata
    try:
        from app.database.manager import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sources WHERE id = ?", (snapshot_source_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass
        
    result = add_data_source(
        source_id=snapshot_source_id,
        stype="sqlite",
        display_name=snapshot_display_name,
        connection_details=snapshot_details,
        schema=discovered_schema,
        labels=["snapshot", "yedek", db_type],
        is_active=True
    )
    
    yield {"status": "complete", "message": "Snapshot başarıyla oluşturuldu ve yerel kaynak olarak kaydedildi!", "result": result}


def create_database_snapshot(source_id: str) -> Dict[str, Any]:
    """
    Wrapper for backward compatibility that executes the generator synchronously
    and returns the final registered source dictionary.
    """
    generator = yield_database_snapshot_progress(source_id)
    final_result = None
    for event in generator:
        if event.get("status") == "error":
            raise ValueError(event.get("message"))
        if event.get("status") == "complete":
            final_result = event.get("result")
    return final_result

