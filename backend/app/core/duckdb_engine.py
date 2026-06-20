import os
import json
import datetime
from typing import Dict, Any, List
import pandas as pd

class DuckDBEngineError(Exception):
    pass

_excel_cache: Dict[str, Any] = {}  # {file_path: (mtime, dataframe)}

def _get_excel_dataframe(file_path: str) -> pd.DataFrame:
    """Caching excel parsing based on file modification time (mtime) to boost performance."""
    global _excel_cache
    mtime = os.path.getmtime(file_path)
    if file_path in _excel_cache:
        cached_mtime, df = _excel_cache[file_path]
        if cached_mtime == mtime:
            return df
            
    df = pd.read_excel(file_path)
    _excel_cache[file_path] = (mtime, df)
    return df

def execute_duckdb_query(sql_query: str, file_mappings: Dict[str, str], is_forecast: bool = False, is_anomaly: bool = False, is_correlation: bool = False, is_listing: bool = False, is_clustering: bool = False) -> Dict[str, Any]:
    """
    Spins up an in-memory DuckDB connection, registers all provided Excel/CSV/TSV
    files as relational table views, runs the SQL query, and returns the result
    along with an automatically generated Plotly dark theme chart.
    Supports auto-detected ML forecasting on time-series queries.
    """
    try:
        import duckdb
    except ImportError:
        raise DuckDBEngineError("duckdb kütüphanesi kurulu değil. Lütfen 'pip install duckdb' çalıştırın.")

    # 1. Establish an isolated in-memory DuckDB instance
    conn = duckdb.connect(database=':memory:')
    
    try:
        # 2. Register each source file as a virtual view/table
        for table_name, file_path in file_mappings.items():
            if not os.path.exists(file_path):
                raise DuckDBEngineError(f"Dosya bulunamadı: {file_path}")
                
            suffix = os.path.splitext(file_path)[1].lower()
            
            try:
                if suffix in ('.xlsx', '.xls'):
                    # Load Excel file using cached parser, then register it in DuckDB
                    df = _get_excel_dataframe(file_path)
                    conn.register(table_name, df)
                elif suffix == '.tsv':
                    # Register TSV directly using auto CSV scanner
                    conn.execute(f"CREATE VIEW \"{table_name}\" AS SELECT * FROM read_csv_auto('{file_path}', delim='\\t')")
                else:
                    # Register CSV directly using auto CSV scanner
                    conn.execute(f"CREATE VIEW \"{table_name}\" AS SELECT * FROM read_csv_auto('{file_path}')")
            except Exception as e:
                raise DuckDBEngineError(f"Veri kaynağı yüklenirken hata oluştu ({table_name}): {str(e)}")

        # 3. Clean query string and enforce read-only policy via sanitizer
        try:
            from app.core.sql_sanitizer import sanitize_and_validate_sql, SQLSanitationError
            clean_query = sanitize_and_validate_sql(sql_query.strip())
        except SQLSanitationError as se:
            raise DuckDBEngineError(f"SQL Güvenlik Hatası: {str(se)}")
        except Exception as parse_err:
            # sanitizer import veya parse hatası — basit temizleme ile devam et
            import logging
            logging.getLogger(__name__).warning(f"SQL sanitizer bypass (fallback): {parse_err}")
            clean_query = sql_query.strip().rstrip(';')

        # 4. Execute the SQL query
        try:
            res = conn.execute(clean_query)
        except Exception as e:
            raise DuckDBEngineError(f"DuckDB SQL Çalıştırma Hatası:\n{str(e)}")
            
        columns = [desc[0] for desc in res.description]
        rows = res.fetchall()
        
        # 5. Serialize rows securely (limit output to 5000 rows to prevent high memory usage)
        serialized_rows = []
        for r in rows[:5000]:
            row_items = []
            for item in r:
                if isinstance(item, (datetime.date, datetime.datetime)):
                    row_items.append(item.isoformat())
                elif isinstance(item, (dict, list)):
                    row_items.append(json.dumps(item))
                elif pd.isna(item):
                    row_items.append(None)
                else:
                    row_items.append(item)
            serialized_rows.append(row_items)
            
        data = {
            "columns": columns,
            "index": list(range(len(serialized_rows))),
            "rows": serialized_rows,
            "row_count": len(rows)
        }
        
        # If is_forecast is requested, execute time series prediction
        if is_forecast and len(serialized_rows) >= 2:
            try:
                from app.core.predictor import run_time_series_forecast
                df_raw = pd.DataFrame(serialized_rows, columns=columns)
                for col in df_raw.columns:
                    try:
                        df_raw[col] = pd.to_numeric(df_raw[col])
                    except Exception:
                        pass
                
                # Deduce time and value columns
                num_cols = df_raw.select_dtypes(include=['number']).columns
                str_cols = df_raw.select_dtypes(include=['object', 'string']).columns
                
                if len(num_cols) > 0 and len(str_cols) > 0:
                    time_col = None
                    for col in str_cols:
                        if any(kw in col.lower() for kw in ["tarih", "date", "ay", "year", "month", "gün", "day"]):
                            time_col = col
                            break
                    if not time_col:
                        time_col = str_cols[0]
                        
                    val_col = num_cols[0]
                    
                    df_forecast = run_time_series_forecast(df_raw, time_col, val_col, periods=6)
                    
                    # Update columns and serialized rows
                    columns = list(df_forecast.columns)
                    serialized_rows = []
                    for _, row in df_forecast.iterrows():
                        serialized_rows.append([None if pd.isna(item) else item for item in row.values])
                        
                    data = {
                        "columns": columns,
                        "index": list(range(len(serialized_rows))),
                        "rows": serialized_rows,
                        "row_count": len(serialized_rows)
                    }
            except Exception:
                pass  # fallback to baseline data if forecasting fails

        # If is_anomaly is requested, execute anomaly detection
        elif is_anomaly and len(serialized_rows) >= 2:
            try:
                from app.core.anomaly import detect_anomalies
                df_raw = pd.DataFrame(serialized_rows, columns=columns)
                for col in df_raw.columns:
                    try:
                        df_raw[col] = pd.to_numeric(df_raw[col])
                    except Exception:
                        pass
                
                num_cols = df_raw.select_dtypes(include=['number']).columns
                if len(num_cols) > 0:
                    val_col = num_cols[0]
                    df_anom = detect_anomalies(df_raw, val_col, method="isolation_forest")
                    
                    columns = list(df_anom.columns)
                    serialized_rows = []
                    for _, row in df_anom.iterrows():
                        serialized_rows.append([None if pd.isna(item) else item for item in row.values])
                        
                    data = {
                        "columns": columns,
                        "index": list(range(len(serialized_rows))),
                        "rows": serialized_rows,
                        "row_count": len(serialized_rows)
                    }
            except Exception:
                pass

        # If is_correlation is requested, compute Pearson correlation matrix
        elif is_correlation and len(serialized_rows) >= 2:
            try:
                from app.core.correlation import compute_correlation
                df_raw = pd.DataFrame(serialized_rows, columns=columns)
                for col in df_raw.columns:
                    try:
                        df_raw[col] = pd.to_numeric(df_raw[col])
                    except Exception:
                        pass
                df_corr = compute_correlation(df_raw)
                
                if not df_corr.empty:
                    columns = list(df_corr.columns)
                    serialized_rows = []
                    for _, row in df_corr.iterrows():
                        serialized_rows.append([None if pd.isna(item) else item for item in row.values])
                        
                    data = {
                        "columns": columns,
                        "index": list(range(len(serialized_rows))),
                        "rows": serialized_rows,
                        "row_count": len(serialized_rows)
                    }
            except Exception:
                pass

        # If is_clustering is requested, execute KMeans clustering
        elif is_clustering and len(serialized_rows) >= 2:
            try:
                from app.core.clustering import run_kmeans_clustering
                df_raw = pd.DataFrame(serialized_rows, columns=columns)
                
                # Check if cluster count is specified in query
                n_clusters = 3
                sql_low = sql_query.lower()
                import re as _re
                match = _re.search(r'(\d+)\s*(küme|segment|cluster)', sql_low)
                if match:
                    try:
                        n_clusters = int(match.group(1))
                    except Exception:
                        pass
                        
                df_clustered = run_kmeans_clustering(df_raw, n_clusters=n_clusters)
                
                columns = list(df_clustered.columns)
                serialized_rows = []
                for _, row in df_clustered.iterrows():
                    serialized_rows.append([None if pd.isna(item) else item for item in row.values])
                    
                data = {
                    "columns": columns,
                    "index": list(range(len(serialized_rows))),
                    "rows": serialized_rows,
                    "row_count": len(serialized_rows)
                }
            except Exception:
                pass
        
        # 6. Automate premium dark mode Plotly visualization
        visualization = None
        try:
            from app.core.visualizer import (
                build_forecast_chart,
                build_anomaly_chart,
                build_correlation_heatmap,
                build_clustering_chart,
                build_auto_chart,
            )

            df_plot = pd.DataFrame(serialized_rows, columns=columns)
            for col in df_plot.columns:
                try:
                    df_plot[col] = pd.to_numeric(df_plot[col])
                except Exception:
                    pass

            if is_forecast and "Tip" in df_plot.columns:
                num_cols = df_plot.select_dtypes(include=["number"]).columns
                str_cols = df_plot.select_dtypes(include=["object", "string"]).columns
                time_col = str_cols[0] if len(str_cols) > 0 else columns[0]
                val_col = num_cols[0] if len(num_cols) > 0 else columns[1]
                visualization = build_forecast_chart(df_plot, time_col, val_col)
            elif is_anomaly and "Durum" in df_plot.columns:
                num_cols = df_plot.select_dtypes(include=["number"]).columns
                if len(num_cols) > 0:
                    visualization = build_anomaly_chart(df_plot, num_cols[0])
            elif is_correlation and "Değişken" in df_plot.columns:
                visualization = build_correlation_heatmap(df_plot)
            elif is_clustering and "Küme" in df_plot.columns:
                visualization = build_clustering_chart(df_plot)
            elif len(columns) >= 2 and not is_listing:
                visualization = build_auto_chart(df_plot, columns, sql_query)
        except Exception:
            pass  # fail visualization creation gracefully

        return {
            "success": True,
            "data": data,
            "visualization": visualization
        }
        
    finally:
        conn.close()
