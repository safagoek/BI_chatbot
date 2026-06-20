"""
app/core/visualizer.py

Merkezi görselleştirme motoru.
Tüm Plotly grafik oluşturma mantığı TEK BİR MODÜLDE toplanmıştır.
duckdb_engine.py ve supervisor.py içinde tekrarlanan ~500 satır kodun yerine geçer.
"""
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

logger = logging.getLogger(__name__)

# ── Dark tema sabitleri ──────────────────────────────────────────────────────
DARK_TEMPLATE = "plotly_dark"
PAPER_BG = "rgba(0,0,0,0)"
PLOT_BG = "rgba(0,0,0,0)"
FONT_FAMILY = "Inter, sans-serif"
FONT_COLOR = "#8b949e"
TITLE_COLOR = "#e6edf3"
GRID_COLOR = "#21262d"
MARGIN = dict(t=40, r=10, l=40, b=40)


def _apply_dark_theme(fig: go.Figure) -> go.Figure:
    """Apply consistent dark theme to any Plotly figure."""
    fig.update_layout(
        template=DARK_TEMPLATE,
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        margin=MARGIN,
        title=dict(
            text=fig.layout.title.text,
            font=dict(family=FONT_FAMILY, size=13, color=TITLE_COLOR),
        ),
        font=dict(family=FONT_FAMILY, color=FONT_COLOR),
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor=GRID_COLOR)
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor=GRID_COLOR)
    return fig


def _detect_numeric_columns(df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    """Returns (numeric_columns, string_columns) tuples."""
    num_cols = df.select_dtypes(include=["number"]).columns.tolist()
    str_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
    return num_cols, str_cols


def _detect_time_column(str_cols: List[str]) -> Optional[str]:
    """Find the most likely time/date column from a list of string column names."""
    time_keywords = ["tarih", "date", "ay", "year", "month", "gün", "day", "yıl", "yil"]
    for col in str_cols:
        if any(kw in col.lower() for kw in time_keywords):
            return col
    return str_cols[0] if str_cols else None


def serialize_figure(fig: go.Figure) -> Optional[Dict[str, Any]]:
    """Safely serialize a Plotly figure to a JSON-serializable dict."""
    try:
        return json.loads(fig.to_json())
    except Exception as e:
        logger.warning(f"Figure serialization failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Grafik Oluşturucular
# ═══════════════════════════════════════════════════════════════════════════════


def build_forecast_chart(
    df: pd.DataFrame,
    time_col: str,
    val_col: str,
) -> Optional[Dict[str, Any]]:
    """
    Build a premium time-series forecast chart with confidence interval band.
    Expects a 'Tip' column with 'Gerçek'/'Tahmin' values and optional
    'Lower_CI'/'Upper_CI' columns.
    """
    try:
        fig = px.line(
            df,
            x=time_col,
            y=val_col,
            color="Tip",
            line_dash="Tip",
            title="Yapay Zekâ Tahmin ve Projeksiyon Modeli (Ridge ML)",
            color_discrete_map={"Gerçek": "#7c3aed", "Tahmin": "#a78bfa"},
        )

        df_pred = df[df["Tip"] == "Tahmin"]
        if len(df_pred) > 0 and "Lower_CI" in df.columns:
            x_ci = list(df_pred[time_col]) + list(df_pred[time_col])[::-1]
            y_ci = list(df_pred["Upper_CI"]) + list(df_pred["Lower_CI"])[::-1]
            fig.add_trace(
                go.Scatter(
                    x=x_ci,
                    y=y_ci,
                    fill="toself",
                    fillcolor="rgba(124, 58, 237, 0.12)",
                    line=dict(color="rgba(255,255,255,0)"),
                    hoverinfo="skip",
                    showlegend=True,
                    name="95% Güven Aralığı",
                )
            )

        fig = _apply_dark_theme(fig)
        return serialize_figure(fig)
    except Exception as e:
        logger.warning(f"Forecast chart failed: {e}")
        return None


def build_anomaly_chart(
    df: pd.DataFrame,
    val_col: str,
) -> Optional[Dict[str, Any]]:
    """
    Build an anomaly detection chart.
    Expects a 'Durum' column with 'Anomali' markers.
    """
    try:
        str_cols, _ = _detect_numeric_columns(df)  # swapped, need str cols
        num_cols, str_cols = _detect_numeric_columns(df)
        x_col = str_cols[0] if str_cols else df.columns[0]

        is_trend = any(
            "tarih" in col.lower() or "date" in col.lower() or "ay" in col.lower()
            for col in str_cols
        )

        if is_trend:
            fig = px.line(
                df,
                x=x_col,
                y=val_col,
                title=f"Zaman Serisi Otomatik Anomali Tespiti ({val_col})",
            )
            fig.update_traces(line=dict(color="#2f81f7", width=2))
        else:
            fig = px.bar(
                df,
                x=x_col,
                y=val_col,
                title=f"Kategori Bazlı Anomali Tespiti ({val_col})",
            )
            fig.update_traces(marker_color="#2f81f7")

        df_outliers = df[df["Durum"] == "Anomali"]
        if not df_outliers.empty:
            fig.add_trace(
                go.Scatter(
                    x=df_outliers[x_col],
                    y=df_outliers[val_col],
                    mode="markers",
                    marker=dict(
                        color="#f85149",
                        size=11,
                        symbol="circle",
                        line=dict(color="#ffffff", width=1),
                    ),
                    name="Anomali",
                    hovertemplate=f"{x_col}: %{{x}}<br>{val_col}: %{{y}}<br>Durum: Anomali",
                )
            )

        fig = _apply_dark_theme(fig)
        return serialize_figure(fig)
    except Exception as e:
        logger.warning(f"Anomaly chart failed: {e}")
        return None


def build_correlation_heatmap(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Build a correlation matrix heatmap.
    Expects a 'Değişken' column for row labels.
    """
    try:
        if "Değişken" not in df.columns:
            return None

        corr_only = df.drop(columns=["Değişken"])
        y_labels = df["Değişken"].tolist()
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
            title="Değişkenler Arası Pearson Korelasyon Matrisi (İlişki Analizi)",
        )

        fig = _apply_dark_theme(fig)
        return serialize_figure(fig)
    except Exception as e:
        logger.warning(f"Correlation heatmap failed: {e}")
        return None


def build_clustering_chart(df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Build a clustering scatter chart.
    Expects a 'Küme' column and optionally 'PCA1'/'PCA2' columns.
    """
    try:
        if "Küme" not in df.columns:
            return None

        num_cols, _ = _detect_numeric_columns(df)
        num_cols = [
            c
            for c in num_cols
            if not any(id_kw in c.lower() for id_kw in ["id", "key", "index", "kod", "no", "pca"])
        ]

        n_clusters = df["Küme"].nunique()
        title_text = f"Yapay Zekâ K-Means Veri Kümeleme Analizi ({n_clusters} Farklı Segment)"

        if "PCA1" in df.columns and "PCA2" in df.columns:
            fig = px.scatter(
                df,
                x="PCA1",
                y="PCA2",
                color="Küme",
                hover_data=[c for c in df.columns if c not in ["PCA1", "PCA2", "Küme"]],
                title=title_text + " (Çok Boyutlu PCA Projeksiyonu)",
            )
        elif len(num_cols) >= 2:
            fig = px.scatter(
                df,
                x=num_cols[0],
                y=num_cols[1],
                color="Küme",
                hover_data=[c for c in df.columns if c != "Küme"],
                title=title_text,
            )
        else:
            str_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
            x_col = str_cols[0] if str_cols else df.columns[0]
            y_col = num_cols[0] if num_cols else df.columns[-1]
            fig = px.scatter(
                df,
                x=x_col,
                y=y_col,
                color="Küme",
                hover_data=[c for c in df.columns if c != "Küme"],
                title=title_text,
            )

        fig = _apply_dark_theme(fig)
        return serialize_figure(fig)
    except Exception as e:
        logger.warning(f"Clustering chart failed: {e}")
        return None


def build_auto_chart(
    df: pd.DataFrame,
    columns: List[str],
    sql_query: str = "",
    max_bar_items: int = 15,
) -> Optional[Dict[str, Any]]:
    """
    Automatically build a chart based on data shape.
    - Time-series data → line chart
    - Categorical + numeric → bar chart
    - Returns None for listing queries or data too small.
    """
    try:
        sql_low = sql_query.lower()
        is_listing_query = (
            ("limit" in sql_low and not any(kw in sql_low for kw in ["group by", "sum(", "count(", "avg(", "max(", "min("]))
            or "random()" in sql_low
            or sql_low.replace(" ", "").startswith("select*")
        )

        if is_listing_query or len(df) <= 3:
            return None

        num_cols, str_cols = _detect_numeric_columns(df)

        if len(num_cols) > 0 and len(str_cols) > 0:
            x_col = str_cols[0]
            y_col = num_cols[0]
            is_trend = any(
                "tarih" in col.lower() or "date" in col.lower() or "ay" in col.lower()
                for col in str_cols
            )

            if is_trend:
                fig = px.line(
                    df.head(100),
                    x=x_col,
                    y=y_col,
                    title=f"Zaman Serisi Trendi: {y_col}",
                    markers=True,
                )
            else:
                fig = px.bar(
                    df.head(max_bar_items),
                    x=x_col,
                    y=y_col,
                    title=f"{x_col} Bazında {y_col} Analizi",
                )

            fig = _apply_dark_theme(fig)
            return serialize_figure(fig)

        return None
    except Exception as e:
        logger.warning(f"Auto chart failed: {e}")
        return None