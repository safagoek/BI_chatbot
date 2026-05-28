import os
import sqlite3
import datetime
from typing import Dict, Any, List
from app.database.manager import get_data_source_by_id, add_data_source
from app.database.connectors import get_connection

SNAPSHOTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "snapshots"
)

def create_database_snapshot(source_id: str) -> Dict[str, Any]:
    """
    Connects to a remote database (PostgreSQL, MySQL, SAP HANA),
    extracts all tables in batches, and dumps them into a local SQLite file.
    Registers the newly created SQLite backup file as an offline SQLite data source.
    """
    # 1. Fetch remote source metadata
    src = get_data_source_by_id(source_id)
    if not src:
        raise ValueError("Hedef veri kaynağı bulunamadı.")
    
    if src["type"] == "sqlite":
        raise ValueError("SQLite kaynakları zaten yereldir, snapshot alınamaz.")
        
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
        except OSError as e:
            raise RuntimeError(f"Eski snapshot yedeği silinemedi: {str(e)}")
            
    # Connect to the remote database to pull schema and data
    remote_conn, _ = get_connection(db_type, details)
    remote_cursor = remote_conn.cursor()
    
    # Connect to the local SQLite database that will house the snapshot
    local_conn = sqlite3.connect(snapshot_path)
    local_cursor = local_conn.cursor()
    
    discovered_schema: Dict[str, List[str]] = {}
    
    try:
        # Discover all tables and columns dynamically
        # 3. Tables Fetching depending on DB type
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
        else:
            raise ValueError(f"Desteklenmeyen veritabanı türü: {db_type}")

        # 4. Process each table: schema creation and batch inserts
        for table in tables:
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
            
            if not columns:
                continue
                
            discovered_schema[table] = columns
            
            # Create SQLite Table
            safe_cols = ", ".join([f'"{col}"' for col in columns])
            create_sql = f'CREATE TABLE IF NOT EXISTS "{table}" ({safe_cols})'
            local_cursor.execute(create_sql)
            
            # Select and fetch rows in batches (düşük RAM tüketimi için 5000'er satır)
            if db_type in ("mysql", "mariadb"):
                safe_table = f"`{table}`"
            else:
                safe_table = f'"{table}"'
                
            remote_cursor.execute(f"SELECT * FROM {safe_table}")
            
            placeholders = ", ".join(["?"] * len(columns))
            insert_sql = f'INSERT INTO "{table}" VALUES ({placeholders})'
            
            while True:
                rows = remote_cursor.fetchmany(5000)
                if not rows:
                    break
                # Normalize row items (convert cursors/lists/tuples)
                normalized_rows = []
                for row in rows:
                    normalized_rows.append([None if item is None else str(item) if type(item) in (dict, list) else item for item in row])
                local_cursor.executemany(insert_sql, normalized_rows)
                
            # Smart Auto-indexing to accelerate downstream analytical DuckDB joins/queries
            for col in columns:
                col_lower = col.lower()
                if any(kw in col_lower for kw in ["id", "key", "kod", "no", "tarih", "date", "vbeln", "matnr", "kunnr"]):
                    index_name = f"idx_{table}_{col_lower}"
                    index_name = "".join([c if c.isalnum() else "_" for c in index_name])
                    try:
                        local_cursor.execute(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table}" ("{col}")')
                    except Exception:
                        pass
                        
        local_conn.commit()
        
    finally:
        remote_conn.close()
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
    
    return result
