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
            import plotly.express as px
            import plotly.graph_objects as go
            df_plot = pd.DataFrame(serialized_rows, columns=columns)
            for col in df_plot.columns:
                try:
                    df_plot[col] = pd.to_numeric(df_plot[col])
                except Exception:
                    pass
            fig = None
            
            if is_forecast and "Tip" in df_plot.columns:
                # Premium Time Series Forecast Chart
                num_cols = df_plot.select_dtypes(include=['number']).columns
                str_cols = df_plot.select_dtypes(include=['object', 'string']).columns
                
                time_col = str_cols[0] if len(str_cols) > 0 else columns[0]
                val_col = num_cols[0] if len(num_cols) > 0 else columns[1]
                
                fig = px.line(
                    df_plot,
                    x=time_col,
                    y=val_col,
                    color="Tip",
                    line_dash="Tip",
                    title=f"Yapay Zekâ Tahmin ve Projeksiyon Modeli (Ridge ML)",
                    color_discrete_map={"Gerçek": "#7c3aed", "Tahmin": "#a78bfa"}
                )
                
                # Filter prediction points to draw 95% Confidence Interval band
                df_pred = df_plot[df_plot["Tip"] == "Tahmin"]
                if len(df_pred) > 0 and "Lower_CI" in df_plot.columns:
                    x_ci = list(df_pred[time_col]) + list(df_pred[time_col])[::-1]
                    y_ci = list(df_pred["Upper_CI"]) + list(df_pred["Lower_CI"])[::-1]
                    
                    fig.add_trace(
                        go.Scatter(
                            x=x_ci,
                            y=y_ci,
                            fill='toself',
                            fillcolor='rgba(124, 58, 237, 0.12)', # Electric purple gaze
                            line=dict(color='rgba(255,255,255,0)'),
                            hoverinfo="skip",
                            showlegend=True,
                            name="95% Güven Aralığı"
                        )
                    )
            elif is_anomaly and "Durum" in df_plot.columns:
                # Premium Anomaly Detection Chart
                num_cols = df_plot.select_dtypes(include=['number']).columns
                str_cols = df_plot.select_dtypes(include=['object', 'string']).columns
                
                if len(num_cols) > 0:
                    val_col = num_cols[0]
                    x_col = str_cols[0] if len(str_cols) > 0 else columns[0]
                    
                    is_trend = any("tarih" in col.lower() or "date" in col.lower() or "ay" in col.lower() for col in str_cols)
                    
                    if is_trend:
                        fig = px.line(df_plot, x=x_col, y=val_col, title=f"Zaman Serisi Otomatik Anomali Tespiti ({val_col})")
                        fig.update_traces(line=dict(color="#2f81f7", width=2))
                    else:
                        fig = px.bar(df_plot, x=x_col, y=val_col, title=f"Kategori Bazlı Anomali Tespiti ({val_col})")
                        fig.update_traces(marker_color="#2f81f7")
                        
                    # Filter and superimpose outliers as bright red markers (#f85149)
                    df_outliers = df_plot[df_plot['Durum'] == 'Anomali']
                    if not df_outliers.empty:
                        fig.add_trace(
                            go.Scatter(
                                x=df_outliers[x_col],
                                y=df_outliers[val_col],
                                mode='markers',
                                marker=dict(color='#f85149', size=11, symbol='circle', line=dict(color='#ffffff', width=1)),
                                name='Anomali',
                                hovertemplate=f"{x_col}: %{{x}}<br>{val_col}: %{{y}}<br>Durum: Anomali"
                            )
                        )
            elif is_correlation and "Değişken" in df_plot.columns:
                # Premium Correlation Heatmap
                corr_only = df_plot.drop(columns=['Değişken'])
                y_labels = df_plot['Değişken'].tolist()
                x_labels = corr_only.columns.tolist()
                z_values = corr_only.values.tolist()
                
                fig = px.imshow(
                    z_values,
                    x=x_labels,
                    y=y_labels,
                    text_auto=".2f",
                    aspect="auto",
                    color_continuous_scale="RdBu",
                    zmin=-1,
                    zmax=1,
                    title="Değişkenler Arası Pearson Korelasyon Matrisi (İlişki Analizi)"
                )
            elif is_clustering and "Küme" in df_plot.columns:
                num_cols = df_plot.select_dtypes(include=['number']).columns.tolist()
                num_cols = [c for c in num_cols if not any(id_kw in c.lower() for id_kw in ["id", "key", "index", "kod", "no", "pca"])]
                
                n_clusters = df_plot["Küme"].nunique()
                title_text = f"Yapay Zekâ K-Means Veri Kümeleme Analizi ({n_clusters} Farklı Segment)"
                
                if 'PCA1' in df_plot.columns and 'PCA2' in df_plot.columns:
                    fig = px.scatter(
                        df_plot,
                        x='PCA1',
                        y='PCA2',
                        color='Küme',
                        hover_data=[c for c in columns if c not in ['PCA1', 'PCA2', 'Küme']],
                        title=title_text + " (Çok Boyutlu PCA Projeksiyonu)"
                    )
                elif len(num_cols) >= 2:
                    fig = px.scatter(
                        df_plot,
                        x=num_cols[0],
                        y=num_cols[1],
                        color='Küme',
                        hover_data=[c for c in columns if c != 'Küme'],
                        title=title_text
                    )
                else:
                    str_cols = df_plot.select_dtypes(include=['object', 'string']).columns.tolist()
                    x_col = str_cols[0] if len(str_cols) > 0 else columns[0]
                    y_col = num_cols[0] if len(num_cols) > 0 else columns[-1]
                    fig = px.scatter(
                        df_plot,
                        x=x_col,
                        y=y_col,
                        color='Küme',
                        hover_data=[c for c in columns if c != 'Küme'],
                        title=title_text
                    )
            elif len(columns) >= 2 and not is_listing:
                # Suppress chart for LIMIT-only / SELECT * / raw listing queries
                sql_low_check = sql_query.lower()
                is_listing_query = (
                    ("limit" in sql_low_check and not any(kw in sql_low_check for kw in ["group by", "sum(", "count(", "avg(", "max(", "min("]))
                    or "random()" in sql_low_check or "rand()" in sql_low_check
                    or sql_low_check.replace(" ", "").startswith("select*")
                )
                if not is_listing_query and len(serialized_rows) > 3:
                    # Deduce quantitative vs qualitative columns
                    num_cols = df_plot.select_dtypes(include=['number']).columns
                    str_cols = df_plot.select_dtypes(include=['object', 'string']).columns
                    
                    if len(num_cols) > 0 and len(str_cols) > 0:
                        x_col = str_cols[0]
                        y_col = num_cols[0]
                        
                        # Detect date/trend
                        is_trend = any("tarih" in col.lower() or "date" in col.lower() or "ay" in col.lower() for col in str_cols)
                        
                        if is_trend:
                            fig = px.line(df_plot.head(100), x=x_col, y=y_col, title=f"Zaman Serisi Trendi: {y_col}", markers=True)
                        else:
                            fig = px.bar(df_plot.head(15), x=x_col, y=y_col, title=f"{x_col} Bazında {y_col} Analizi")
                        
            # Apply elegant dark UI layout styles matching the web dashboard theme
            if fig is not None:
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=40, r=10, l=40, b=40),
                    title=dict(
                        text=fig.layout.title.text,
                        font=dict(family="Inter, sans-serif", size=13, color="#e6edf3")
                    ),
                    font=dict(family="Inter, sans-serif", color="#8b949e")
                )
                fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#21262d")
                fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#21262d")
                
                visualization = json.loads(fig.to_json())
        except Exception:
            pass  # fail visualization creation gracefully
            
        return {
            "success": True,
            "data": data,
            "visualization": visualization
        }
        
    finally:
        conn.close()
