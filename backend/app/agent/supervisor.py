import os
import re
import json
import httpx
import sqlite3
import csv
import tempfile
import shutil
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from app.core.sandbox import PythonSandbox, SandboxExecutionError
from app.core.duckdb_engine import execute_duckdb_query
from app.core.sql_sanitizer import sanitize_and_validate_sql, SQLSanitationError
from app.agent.rag import retrieve_similar, add_to_memory, self_correct_loop
from app.database.manager import get_data_sources, get_uploaded_files
from app.database.demo_db import DEMO_DB_PATH
from app.core.logger import logger

class SupervisorAgent:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        try:
            from app.database.manager import get_llm_config
            db_config = get_llm_config()
        except Exception:
            db_config = {}

        self.api_key = api_key or db_config.get("apiKey") or os.getenv("DEEPSEEK_API_KE ")
        self.base_url = base_url or db_config.get("baseUrl") or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.model = model or db_config.get("model") or os.getenv("DEEPSEEK_MODEL", "deepseek-coder")
        self.sandbox = PythonSandbox()

    async def process_query(
        self,
        user_question: str,
        active_source_id: str,
        source_ids: Optional[List[str]] = None,
        relationships: Optional[List[Dict[str, Any]]] = None,
        ws_callback=None
    ) -> Dict[str, Any]:
        """
        Main query orchestration pipeline.
        ws_callback: Async function to send stream steps back to React frontend.
        """
        async def send_status(msg: str):
            if ws_callback:
                await ws_callback({"type": "status", "message": msg})

        async def send_code(lang: str, code: str):
            if ws_callback:
                await ws_callback({"type": "code", "language": lang, "code": code})

        # Step 1: Discover schema & metadata of the selected source
        logger.info(f"Processing query: '{user_question}' for source: '{active_source_id}'")
        await send_status("[RouterAgent] Kullanıcı sorusu ve veri kaynağı şeması analiz ediliyor...")
        
        resolved = self._resolve_sources(active_source_id, source_ids or [], bool(source_ids))
        source_meta = resolved.get("meta")
        warnings = resolved.get("warnings", [])
        for warning in warnings:
            await send_status(f"[RouterAgent] {warning}")
        if not source_meta:
            return {"error": f"Veri kaynağı bulunamadı: {active_source_id}"}
            
        # Determine intent dynamically (Supports Manual Slash Commands & Heuristics)
        forced_intent = None
        cleaned_question = user_question.strip()
        
        # Exact command mappings for Autocomplete commands
        if cleaned_question.startswith("/graph ") or cleaned_question == "/graph":
            forced_intent = "file_analysis"
            cleaned_question = cleaned_question[6:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: FILE_ANALYSIS (Görsel Grafik Çizimi)")
        elif cleaned_question.startswith("/ask ") or cleaned_question == "/ask":
            forced_intent = "conceptual"
            cleaned_question = cleaned_question[4:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: CONCEPTUAL (Kavramsal Bilgi)")
        elif cleaned_question.startswith("/ml ") or cleaned_question == "/ml":
            forced_intent = "file_analysis"
            cleaned_question = cleaned_question[3:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: FILE_ANALYSIS (Makine Öğrenmesi)")
        elif cleaned_question.startswith("/table ") or cleaned_question == "/table":
            forced_intent = "sql_query"
            cleaned_question = cleaned_question[6:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: SQL_QUERY (Tablo Listeleme)")
        elif cleaned_question.startswith("/sqlquery ") or cleaned_question == "/sqlquery":
            forced_intent = "sql_query"
            cleaned_question = cleaned_question[9:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: SQL_QUERY (SQL Sorgusu)")
        elif cleaned_question.startswith("/pythonscript ") or cleaned_question == "/pythonscript":
            forced_intent = "file_analysis"
            cleaned_question = cleaned_question[13:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: FILE_ANALYSIS (Python Script)")
        elif cleaned_question.startswith("/explain ") or cleaned_question == "/explain":
            forced_intent = "file_analysis"
            cleaned_question = cleaned_question[8:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: FILE_ANALYSIS (Veri Açıklama & Analiz)")
        elif cleaned_question.startswith("/forecast ") or cleaned_question == "/forecast":
            forced_intent = "file_analysis"
            cleaned_question = cleaned_question[9:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: FILE_ANALYSIS (Zaman Serisi Tahmini)")
        elif cleaned_question.startswith("/clean ") or cleaned_question == "/clean":
            forced_intent = "file_analysis"
            cleaned_question = cleaned_question[6:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: FILE_ANALYSIS (Veri Temizleme & Keşif)")
        elif cleaned_question.startswith("/pivot ") or cleaned_question == "/pivot":
            forced_intent = "file_analysis"
            cleaned_question = cleaned_question[6:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: FILE_ANALYSIS (Dinamik Pivot Analizi)")
        elif cleaned_question.startswith("/corr ") or cleaned_question == "/corr":
            forced_intent = "file_analysis"
            cleaned_question = cleaned_question[5:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: FILE_ANALYSIS (Korelasyon Analizi)")
        elif cleaned_question.startswith("/help ") or cleaned_question == "/help":
            forced_intent = "conceptual"
            cleaned_question = cleaned_question[5:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: CONCEPTUAL (Kullanım Rehberi & Yardım)")
        # Legacy/Alias mappings
        elif cleaned_question.startswith("/python ") or cleaned_question == "/python":
            forced_intent = "file_analysis"
            cleaned_question = cleaned_question[7:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: FILE_ANALYSIS (Python/Pandas)")
        elif cleaned_question.startswith("/sql ") or cleaned_question == "/sql":
            forced_intent = "sql_query"
            cleaned_question = cleaned_question[4:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: SQL_QUERY")
        elif cleaned_question.startswith("/sorgu ") or cleaned_question == "/sorgu":
            forced_intent = "sql_query"
            cleaned_question = cleaned_question[6:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: SQL_QUERY")
        elif cleaned_question.startswith("/sor ") or cleaned_question == "/sor":
            forced_intent = "conceptual"
            cleaned_question = cleaned_question[4:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: CONCEPTUAL (Kavramsal Bilgi)")
        elif cleaned_question.startswith("/bilgi ") or cleaned_question == "/bilgi":
            forced_intent = "conceptual"
            cleaned_question = cleaned_question[6:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: CONCEPTUAL (Kavramsal Bilgi)")
        elif cleaned_question.startswith("/konsept ") or cleaned_question == "/konsept":
            forced_intent = "conceptual"
            cleaned_question = cleaned_question[8:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: CONCEPTUAL (Kavramsal Bilgi)")
        elif cleaned_question.startswith("/rapor ") or cleaned_question == "/rapor":
            forced_intent = "report"
            cleaned_question = cleaned_question[6:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: REPORT (Gelişmiş Raporlama)")
        elif cleaned_question.startswith("/report ") or cleaned_question == "/report":
            forced_intent = "report"
            cleaned_question = cleaned_question[7:].strip()
            await send_status("[RouterAgent] Yönlendirme algılandı: REPORT (Gelişmiş Raporlama)")

        if forced_intent:
            intent = forced_intent
            is_sql = (intent == "sql_query")
            user_question = cleaned_question
        else:
            q_low = user_question.lower().strip()
            # Conceptual question heuristic: queries seeking explanations rather than active data calculations/charts
            is_conceptual_q = any(kw in q_low for kw in [
                "tahminleyebiliriz", "tahmin edebiliriz", "neleri", "neler yapabiliriz", "nedir", 
                "nelerdir", "nasıl çalışır", "nasıl calisir", "ne demektir", "ne işe yarar", 
                "ne ise yarar", "what is", "how does", "explain", "açıkla", "bilgi ver", 
                "tanımla", "öğret", "neden olur", "anlamı ne", "kavram", "teori"
            ]) and not any(kw in q_low for kw in [
                "göster", "listele", "hesapla", "çiz", "grafik", "tablo", "kaç", "toplam", 
                "ortalama", "yarat", "oluştur", "sorgula", "top 5", "limit"
            ])
            
            if is_conceptual_q:
                intent = "conceptual"
                is_sql = False
                await send_status("[RouterAgent] Kavramsal/Bilgi sorgusu algılandı: CONCEPTUAL (Kavramsal Açıklama)")
            else:
                wants_python = any(kw in q_low for kw in [
                    "python", "pandas", "makine öğrenmesi", "makine ogrenmesi", "machine learning", "ml", 
                    "tahmin", "tahminleme", "tahminlemesi", "öngörü", "ongoru", "yapay zeka", "yapay zekâ", 
                    "model", "regresyon", "sınıflandırma", "siniflandirma", "kümeleme", "kumeleme",
                    "korelasyon", "correlation", "heatmap", "anomali", "anomaly", "aykırı", "outlier",
                    "satacağım", "satacagim", "satıcam", "saticam", "satacağız", "satacagiz",
                    "gelecek ay", "gelecek yil", "gelecek yıl", "önümüzdeki ay", "onumuzdeki ay", "önümüzdeki yıl", "onumuzdeki yil",
                    "gelecek dönem", "gelecek donem", "forecast", "forecasting", "predict", "predictive", "prediction",
                    "projection", "projeksiyon", "churn", "müşteri kaybı", "musteri kaybi", "clustering"
                ])
                is_file_source = (source_meta["type"] == "file")
                
                if wants_python or (is_file_source and any(kw in q_low for kw in ["tahmin", "forecast", "predict", "projeksiyon", "gelecek", "anomali", "aykırı", "outlier", "korelasyon", "correlation"])):
                    intent = "file_analysis"
                    is_sql = False
                    await send_status("[RouterAgent] Sorgu rotası başarıyla belirlendi: FILE_ANALYSIS (Python/Pandas & ML)")
                else:
                    intent = "sql_query"
                    is_sql = True
                    await send_status("[RouterAgent] Sorgu rotası başarıyla belirlendi: SQL_QUERY")

        # Step 1.5: Conceptual Query Bypass
        if intent == "conceptual":
            await send_status("[ConceptualAgent] Konsept ve analitik açıklama raporu hazırlanıyor...")
            schema_str = json.dumps(source_meta.get("schema", {}), ensure_ascii=False)
            prompt = f""" ou are a senior Business Intelligence and Data Science consultant. Answer the user's conceptual, theoretical, or informational question.
Format your answer professionally, focusing purely on data analytics and data science perspectives.
If the question is related to the dataset schema, connect it directly to the active dataset columns with concrete examples.

Active Dataset Schema:
{schema_str}

User Question:
{user_question}

Instructions:
- Avoid generic conversational introductions or filler text (e.g., "Sure, I can help", "As an AI..."). Start directly with the analysis.
- Output high-quality, rich markdown formatting using bolding, bullet points, tables, and headers.
- Respond in Turkish (or match the language of the user question).

Answer:"""
            if self.api_key:
                try:
                    answer_text = await self._call_deepseek(prompt)
                except Exception as e:
                    answer_text = f"### 🔮 Kavramsal Açıklama\n\nMakine öğrenmesi ile verilerinizdeki kalıpları öğrenerek gelecek dönem tahminleri yapabilir, müşteri kaybı (churn) olasılıklarını hesaplayabilir, sayısal trendleri modelleyebilir ve anomali tespiti gerçekleştirebilirsiniz.\n\n*(Not: Gecikme veya bağlantı hatası sebebiyle daha detaylı analitik yanıt üretilemedi: {str(e)})*"
            else:
                answer_text = "### 🔮 Kavramsal Açıklama\n\nMakine öğrenmesi ile veri setleriniz üzerinde:\n1. **Sınıflandırma (Classification):** Müşteri kaybı (churn), dolandırıcılık veya segmentasyon tespiti.\n2. **Regresyon (Regression):** Satış hacmi, ciro veya talep tahminlemeleri.\n3. **Anomali Tespiti (Anomaly Detection):** Olağandışı işlem veya hataların tespiti yapılabilir.\n\n*(Not: API anahtarı girilmediği için özelleştirilmiş şema analizi yapılamadı.)*"
            
            return {
                "success": True,
                "generated_code": "",
                "data": None,
                "visualization": None,
                "final_response": answer_text,
                "auto_corrections": None
            }

        # Step 1.6: Dynamic Executive Report Bypass
        if intent == "report":
            await send_status("[ReportAgent] Yönetici özeti ve genel analitik şema raporu derleniyor...")
            schema_str = json.dumps(source_meta.get("schema", {}), ensure_ascii=False)
            prompt = f""" ou are an elite enterprise Data Architect and BI Analyst. Compile a comprehensive Executive Summary and Analytical Roadmap Report about the active database source.

Active Source Schema:
{schema_str}

Instructions:
- Provide a clear, professional analysis of what queries (SQL, DuckDB) and predictive modeling (ML, forecasting, anomaly detection) are feasible using this specific schema.
- Interpret the column types and suggest practical analytical use-cases.
- Format the response using clean markdown with tables, headers, and bulleted lists.
- Respond in Turkish (or match the language of the user question).

Report:"""
            if self.api_key:
                try:
                    answer_text = await self._call_deepseek(prompt)
                except Exception as e:
                    answer_text = f"### Yönetici Raporu\n\nAktif veri kaynağınız ({source_meta.get('alias')}) başarıyla şemalandırılmıştır. Şemada yer alan alanlar üzerinde ML regresyon modelleri veya DuckDB analitik agregasyonları koşturulabilir.\n\n*(Bağlantı hatası: {str(e)})*"
            else:
                answer_text = f"### Yönetici Raporu\n\nAktif veri kaynağınız ({source_meta.get('alias')}) başarıyla şemalandırılmıştır.\n\nŞemadaki sütunlar:\n{schema_str}\n\nDetaylı LLM analizi ve yol haritası raporu üretmek için lütfen API anahtarınızı tanımlayın."
            
            return {
                "success": True,
                "generated_code": "",
                "data": None,
                "visualization": None,
                "final_response": answer_text,
                "auto_corrections": None
            }

        # Step 2: Query construction (LLM or Heuristic fallbacks)
        generated_code = ""
        
        # Load relevant context from TF-IDF Cosine-Similarity RAG Memory
        rag_key = source_meta.get("rag_key") or active_source_id
        rag_examples = retrieve_similar(user_question, rag_key, active_schema=source_meta.get("schema"))
        
        is_direct_db = (source_meta["type"] == "database")
        
        if is_sql:
            await send_status(f"[CoderAgent] Şema ile uyumlu salt-okunur {'Canlı Veritabanı' if is_direct_db else 'Yerel DuckDB'} SQL kod mantığı hazırlanıyor...")
            if self.api_key:
                try:
                    if is_direct_db:
                        generated_code = await self._generate_sql_llm(user_question, source_meta, rag_examples)
                    else:
                        generated_code = await self._generate_duckdb_sql_llm(user_question, source_meta, rag_examples, relationships or [])
                except Exception as e:
                    await send_status(f"[CoderAgent] LLM API hatası, yerel zeka motoruna geçiliyor... (Hata: {str(e)})")
                    generated_code = self._generate_fallback_code(user_question, source_meta, is_sql=True)
            else:
                await send_status("[CoderAgent] API anahtarı bulunamadı. Yerel akıllı NLP motoru ile kod üretiliyor...")
                generated_code = self._generate_fallback_code(user_question, source_meta, is_sql=True)
        else:
            await send_status("[CoderAgent] Şema ile uyumlu güvenli Pandas ve Görselleştirme kod mantığı hazırlanıyor...")
            if self.api_key:
                try:
                    generated_code = await self._generate_pandas_llm(user_question, source_meta, rag_examples, relationships or [])
                except Exception as e:
                    await send_status(f"[CoderAgent] LLM API hatası, yerel zeka motoruna geçiliyor... (Hata: {str(e)})")
                    generated_code = self._generate_fallback_code(user_question, source_meta, is_sql=False)
            else:
                await send_status("[CoderAgent] API anahtarı bulunamadı. Yerel akıllı NLP motoru ile kod üretiliyor...")
                generated_code = self._generate_fallback_code(user_question, source_meta, is_sql=False)

        # Auto-correct table names for multi-source/mixed-source (DuckDB) compatibility
        if is_sql and not is_direct_db and source_meta.get("db_sources"):
            # Don't rewrite table names that are provided by uploaded files
            file_table_names = set()
            if isinstance(source_meta.get("file_mappings"), dict):
                file_table_names.update([k.lower() for k in source_meta.get("file_mappings").keys()])
            if source_meta.get("alias") and source_meta.get("type") == "file":
                file_table_names.add(source_meta.get("alias").lower())

            for db in source_meta["db_sources"]:
                db_id = db["id"]
                for table_name in db.get("schema", {}).keys():
                    # If a file mapping provides this table name, prefer the file and skip replacement
                    if table_name.lower() in file_table_names:
                        continue
                    registered_name = f"{db_id}__{table_name}"
                    if registered_name not in generated_code:
                        pattern = re.compile(rf'\b{re.escape(table_name)}\b', re.IGNORECASE)
                        generated_code = pattern.sub(registered_name, generated_code)

        # Output the initial generated code to UI
        await send_code("sql" if is_sql else "python", generated_code)

        # Detect prediction, anomaly, and correlation intents
        q_low = user_question.lower()
        is_forecast = any(kw in q_low for kw in ["tahmin", "forecast", "predict", "projeksiyon", "gelecek"])
        is_anomaly = any(kw in q_low for kw in ["anomali", "aykırı", "outlier", "sapma"])
        is_correlation = any(kw in q_low for kw in ["korelasyon", "ilişki", "heatmap", "correlation"])
        is_clustering = any(kw in q_low for kw in ["kümeleme", "segmentasyon", "segment", "cluster", "clustering"])
        
        # Detect listing/sample intent — these should return a table, NOT a chart
        is_listing = any(kw in q_low for kw in [
            "göster", "listele", "getir", "örnek", "sample", "random", "rastgele",
            "ilk", "first", "son", "last", "tüm", "all", "tümünü", "hepsini",
            "sat\u0131r", "row", "kayıt", "record", "veri göster", "veri getir"
        ])

        # Visualizer agent step
        if is_forecast:
            await send_status("[VisualizerAgent] Yapay Zekâ ML Tahmin Modeli ve Plotly grafik motoru yükleniyor...")
        elif is_anomaly:
            await send_status("[VisualizerAgent] Yapay Zekâ ML Anomali Tespit Modeli ve Plotly görselleştirme katmanı yükleniyor...")
        elif is_correlation:
            await send_status("[VisualizerAgent] İstatistiki İlişki Matrisi ve Plotly Heatmap görselleştirme katmanı yükleniyor...")
        elif is_clustering:
            await send_status("[VisualizerAgent] Yapay Zekâ ML Veri Kümeleme Modeli ve Plotly görselleştirme katmanı yükleniyor...")
        elif is_listing:
            await send_status("[VisualizerAgent] Listeleme sorgusu tespit edildi — tablo formatında veri hazırlanıyor...")
        else:
            await send_status("[VisualizerAgent] Modern koyu tema, yazı tipleri ve otomatik Plotly grafik motoru entegre ediliyor...")

        # Step 3: Secure Sandbox Execution with Self-Correction
        async def execute_sql_fn(code_to_exec: str) -> Tuple[bool, Any]:
            try:
                import pandas as pd
                db_type = source_meta.get("db_type") if source_meta.get("type") == "database" else None
                safe_sql = sanitize_and_validate_sql(code_to_exec, db_type=db_type)
                result_data = self._execute_local_sql(safe_sql, source_meta)
                
                # If is_forecast is requested, execute time series prediction
                if is_forecast and result_data.get("success") and result_data.get("data") and len(result_data["data"].get("rows", [])) >= 2:
                    try:
                        from app.core.predictor import run_time_series_forecast
                        df_raw = pd.DataFrame(result_data["data"]["rows"], columns=result_data["data"]["columns"])
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
                            
                            columns = list(df_forecast.columns)
                            serialized_rows = []
                            for _, row in df_forecast.iterrows():
                                serialized_rows.append([None if pd.isna(item) else item for item in row.values])
                                
                            result_data["data"] = {
                                "columns": columns,
                                "index": list(range(len(serialized_rows))),
                                "rows": serialized_rows,
                                "row_count": len(serialized_rows)
                            }
                            
                            # Premium Time Series Forecast Chart
                            import plotly.express as px
                            import plotly.graph_objects as go
                            
                            fig = px.line(
                                df_forecast,
                                x=time_col,
                                y=val_col,
                                color="Tip",
                                line_dash="Tip",
                                title=f" apay Zekâ Tahmin ve Projeksiyon Modeli (Ridge ML)",
                                color_discrete_map={"Gerçek": "#7c3aed", "Tahmin": "#a78bfa"}
                            )
                            
                            # Filter prediction points to draw 95% Confidence Interval band
                            df_pred = df_forecast[df_forecast["Tip"] == "Tahmin"]
                            if len(df_pred) > 0 and "Lower_CI" in df_forecast.columns:
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
                            
                            result_data["visualization"] = json.loads(fig.to_json())
                    except Exception:
                        pass
                # If is_anomaly is requested, execute anomaly detection
                elif is_anomaly and result_data.get("success") and result_data.get("data") and len(result_data["data"].get("rows", [])) >= 2:
                    try:
                        from app.core.anomaly import detect_anomalies
                        df_raw = pd.DataFrame(result_data["data"]["rows"], columns=result_data["data"]["columns"])
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
                                
                            result_data["data"] = {
                                "columns": columns,
                                "index": list(range(len(serialized_rows))),
                                "rows": serialized_rows,
                                "row_count": len(serialized_rows)
                            }
                            
                            # Premium Outlier chart
                            import plotly.express as px
                            import plotly.graph_objects as go
                            
                            str_cols = df_anom.select_dtypes(include=['object', 'string']).columns
                            x_col = str_cols[0] if len(str_cols) > 0 else columns[0]
                            is_trend = any("tarih" in col.lower() or "date" in col.lower() or "ay" in col.lower() for col in str_cols)
                            
                            if is_trend:
                                fig = px.line(df_anom, x=x_col, y=val_col, title=f"Zaman Serisi Otomatik Anomali Tespiti ({val_col})")
                                fig.update_traces(line=dict(color="#2f81f7", width=2))
                            else:
                                fig = px.bar(df_anom, x=x_col, y=val_col, title=f"Kategori Bazlı Anomali Tespiti ({val_col})")
                                fig.update_traces(marker_color="#2f81f7")
                                
                            df_outliers = df_anom[df_anom['Durum'] == 'Anomali']
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
                            
                            result_data["visualization"] = json.loads(fig.to_json())
                    except Exception:
                        pass
                # If is_correlation is requested, compute Pearson correlation matrix
                elif is_correlation and result_data.get("success") and result_data.get("data") and len(result_data["data"].get("rows", [])) >= 2:
                    try:
                        from app.core.correlation import compute_correlation
                        df_raw = pd.DataFrame(result_data["data"]["rows"], columns=result_data["data"]["columns"])
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
                                
                            result_data["data"] = {
                                "columns": columns,
                                "index": list(range(len(serialized_rows))),
                                "rows": serialized_rows,
                                "row_count": len(serialized_rows)
                            }
                            
                            import plotly.express as px
                            corr_only = df_corr.drop(columns=['Değişken'])
                            y_labels = df_corr['Değişken'].tolist()
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
                            
                            result_data["visualization"] = json.loads(fig.to_json())
                    except Exception:
                        pass
                # If is_clustering is requested, run KMeans clustering
                elif is_clustering and result_data.get("success") and result_data.get("data") and len(result_data["data"].get("rows", [])) >= 2:
                    try:
                        from app.core.clustering import run_kmeans_clustering
                        df_raw = pd.DataFrame(result_data["data"]["rows"], columns=result_data["data"]["columns"])
                        
                        n_clusters = 3
                        match = re.search(r'(\d+)\s*(küme|segment|cluster)', q_low)
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
                            
                        result_data["data"] = {
                            "columns": columns,
                            "index": list(range(len(serialized_rows))),
                            "rows": serialized_rows,
                            "row_count": len(serialized_rows)
                        }
                        
                        import plotly.express as px
                        num_cols = df_clustered.select_dtypes(include=['number']).columns.tolist()
                        num_cols = [c for c in num_cols if not any(id_kw in c.lower() for id_kw in ["id", "key", "index", "kod", "no", "pca"])]
                        
                        title_text = f" apay Zekâ K-Means Müşteri/Veri Kümeleme Analizi ({n_clusters} Farklı Segment)"
                        
                        if 'PCA1' in df_clustered.columns and 'PCA2' in df_clustered.columns:
                            fig = px.scatter(
                                df_clustered,
                                x='PCA1',
                                y='PCA2',
                                color='Küme',
                                hover_data=[c for c in columns if c not in ['PCA1', 'PCA2', 'Küme']],
                                title=title_text + " (Çok Boyutlu PCA Projeksiyonu)"
                            )
                        elif len(num_cols) >= 2:
                             fig = px.scatter(
                                 df_clustered,
                                 x=num_cols[0],
                                 y=num_cols[1],
                                 color='Küme',
                                 hover_data=[c for c in columns if c != 'Küme'],
                                 title=title_text
                             )
                        else:
                             str_cols = df_clustered.select_dtypes(include=['object', 'string']).columns.tolist()
                             x_col = str_cols[0] if len(str_cols) > 0 else columns[0]
                             y_col = num_cols[0] if len(num_cols) > 0 else columns[-1]
                             fig = px.scatter(
                                 df_clustered,
                                 x=x_col,
                                 y=y_col,
                                 color='Küme',
                                 hover_data=[c for c in columns if c != 'Küme'],
                                 title=title_text
                             )
                            
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
                        
                        result_data["visualization"] = json.loads(fig.to_json())
                    except Exception:
                        pass
                return True, result_data
            except Exception as ex:
                return False, str(ex)

        async def execute_duckdb_fn(code_to_exec: str) -> Tuple[bool, Any]:
            temp_dir = None
            try:
                # Only expose file mappings for file-based sources; otherwise start empty.
                if source_meta.get("file_mappings"):
                    file_mappings = source_meta.get("file_mappings")
                elif source_meta.get("type") == "file" and source_meta.get("file_path"):
                    file_mappings = {source_meta["alias"]: source_meta["file_path"]}
                else:
                    file_mappings = {}

                if source_meta.get("db_sources"):
                    # Increase materialization limit to 50,000 safely for DuckDB
                    db_files, db_schema, temp_dir = self._materialize_db_sources(source_meta["db_sources"], max_rows=50000)
                    file_mappings = {**file_mappings, **db_files}
                    if isinstance(source_meta.get("schema"), dict):
                        source_meta["schema"].update(db_schema)
                # Build allowed table list from selected file mappings and materialized DB tables
                allowed_tables = set([k.lower() for k in file_mappings.keys()])
                if source_meta.get("db_sources"):
                    for db in source_meta.get("db_sources"):
                        db_id = db.get("id")
                        for tbl in db.get("schema", {}).keys():
                            allowed_tables.add(f"{db_id}__{tbl}".lower())

                # Simple SQL parser to extract referenced table identifiers
                import re as _re
                refs = set()
                for m in _re.finditer(r"\bfrom\s+([\w\"\'\.]+)|\bjoin\s+([\w\"\'\.]+)", code_to_exec, _re.IGNORECASE):
                    t = m.group(1) or m.group(2)
                    if not t:
                        continue
                    # Remove surrounding quotes and any aliasing
                    t_clean = t.strip().strip('"').strip("'")
                    t_clean = t_clean.split()[:1][0]
                    # Remove schema prefix if present (e.g., db.table)
                    if "." in t_clean:
                        t_clean = t_clean.split(".")[-1]
                    refs.add(t_clean.lower())

                unknown = [r for r in refs if r and r not in allowed_tables]
                corrections = {}
                ambiguous = []
                if unknown:
                    import difflib as _difflib
                    allowed_map = {t.lower(): t for t in allowed_tables}
                    for u in unknown:
                        #  üksek eşleşme eşiği (0.72) — 0.66'dan düşük eşleşmeler kabul edilmez
                        candidates = _difflib.get_close_matches(u, list(allowed_map.keys()), n=2, cutoff=0.72)
                        if len(candidates) == 1:
                            matched = allowed_map[candidates[0]]
                            corrections[u] = matched
                        elif len(candidates) > 1:
                            seq0 = _difflib.SequenceMatcher(None, u, candidates[0]).ratio()
                            seq1 = _difflib.SequenceMatcher(None, u, candidates[1]).ratio()
                            #  alnızca fark %20'den büyükse güvenli eşleşme
                            if abs(seq0 - seq1) > 0.20:
                                corrections[u] = allowed_map[candidates[0] if seq0 > seq1 else candidates[1]]
                            else:
                                # Belirsiz eşleşme — otomatik düzeltme yok, hata döndür
                                ambiguous.append(u)
                        else:
                            ambiguous.append(u)

                    # Belirsiz tablolar varsa ve hiç kesin düzeltme yoksa hemen hata döndür
                    if ambiguous and not corrections:
                        return False, {
                            "error": (
                                f"Sorgudaki tablo isimleri belirsiz veya bulunamadı: {ambiguous}. "
                                f"Lütfen şu tablolardan birini kullanın: {sorted(list(allowed_tables))}"
                            ),
                            "unknown": unknown,
                            "ambiguous": ambiguous,
                            "allowed": sorted(list(allowed_tables))
                        }

                    # Kesin düzeltmeleri uygula + kullanıcıya UI'dan bildir
                    corrected_code = code_to_exec
                    if corrections:
                        for src, tgt in corrections.items():
                            try:
                                corrected_code = re.sub(
                                    rf"\b{re.escape(src)}\b", tgt, corrected_code, flags=re.IGNORECASE
                                )
                            except Exception:
                                pass
                        code_to_exec = corrected_code
                        # Kullanıcıya yapılan düzeltmeleri bildir — sessiz değişiklik yok
                        correction_msg = ", ".join(f"'{s}' → '{t}'" for s, t in corrections.items())
                        await send_status(
                            f"[AutoCorrectAgent] Tablo adı otomatik düzeltildi: {correction_msg}. "
                            f"Sonuç yanlış görünüyorsa lütfen sorgunuzu kontrol edin."
                        )
                        if ambiguous:
                            await send_status(
                                f"[AutoCorrectAgent] Belirsiz tablo referansları atlandı: {ambiguous}"
                            )

                # Execute utilizing our premium local DuckDB SQL engine
                res = execute_duckdb_query(
                    code_to_exec, 
                    file_mappings, 
                    is_forecast=is_forecast, 
                    is_anomaly=is_anomaly, 
                    is_correlation=is_correlation,
                    is_listing=is_listing,
                    is_clustering=is_clustering
                )
                # Attach meta about auto-corrections if any were applied
                if corrections:
                    try:
                        if isinstance(res, dict):
                            res.setdefault("_auto_corrections", {})
                            res["_auto_corrections"]["applied"] = corrections
                            if ambiguous:
                                res["_auto_corrections"]["ambiguous"] = ambiguous
                    except Exception:
                        pass
                return True, res
            except Exception as ex:
                return False, str(ex)
            finally:
                if temp_dir and os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)

        # Define execute_pandas_fn
        async def execute_pandas_fn(code_to_exec: str) -> Tuple[bool, Any]:
            try:
                file_mappings = {}
                temp_dir = None
                
                # Resolve file sources
                if source_meta.get("file_mappings"):
                    file_mappings = dict(source_meta.get("file_mappings"))
                elif source_meta.get("type") == "file" and source_meta.get("file_path"):
                    file_mappings = {source_meta["alias"]: source_meta["file_path"]}
                
                # Resolve DB sources dynamically (supports multi-db, mixed-db, and single active direct databases)
                db_sources_list = []
                if source_meta.get("db_sources"):
                    db_sources_list = source_meta.get("db_sources")
                elif source_meta.get("type") == "database":
                    db_sources_list = [source_meta]
                    
                if db_sources_list:
                    # Materialize DB tables to CSV files
                    db_files, db_schema, temp_dir = self._materialize_db_sources(db_sources_list, max_rows=50000)
                    for df_name, csv_path in db_files.items():
                        file_mappings[df_name] = csv_path
                        # Also expose short table name if not already exists to allow simple query references
                        if "__" in df_name:
                            short_name = df_name.split("__", 1)[1]
                            if short_name not in file_mappings:
                                file_mappings[short_name] = csv_path
                                
                # Expose 'df' as a fallback pointing to the first/primary dataframe path to prevent failure on manual 'df' usage
                if file_mappings and "df" not in file_mappings:
                    first_key = list(file_mappings.keys())[0]
                    file_mappings["df"] = file_mappings[first_key]

                try:
                    sandbox_result = self.sandbox.run_pandas_code(code_to_exec, file_mappings)
                    if "error" in sandbox_result and sandbox_result["error"]:
                        return False, sandbox_result["error"]
                    return True, sandbox_result
                finally:
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as ex:
                return False, str(ex)

        if is_sql:
            execute_fn = execute_sql_fn if is_direct_db else execute_duckdb_fn
        else:
            execute_fn = execute_pandas_fn

        # Setup LLM correction lambda
        if self.api_key:
            if is_sql:
                llm_correct_fn = (
                    (lambda q, c, err, sch: self._llm_correct_sql(q, c, err, sch))
                    if is_direct_db
                    else (lambda q, c, err, sch: self._llm_correct_duckdb(q, c, err, sch))
                )
            else:
                llm_correct_fn = (lambda q, c, err, sch: self._llm_correct_python(q, c, err, sch))
        else:
            llm_correct_fn = None

        # Build critique schema
        critique_schema = source_meta["schema"]
        if is_sql and source_meta["type"] == "file":
            if not source_meta.get("file_mappings"):
                critique_schema = {source_meta["alias"]: list(source_meta["schema"].keys())}
            else:
                critique_schema = {}
                for k, v in source_meta["schema"].items():
                    if isinstance(v, dict):
                        critique_schema[k] = list(v.keys())
                    elif isinstance(v, list):
                        critique_schema[k] = v
                    else:
                        critique_schema[k] = [k]

        await send_status(
            "[CritiqueAgent] SQL sorgusu güvenli sandbox analitik ortamına gönderiliyor..."
            if is_sql
            else "[CritiqueAgent] Python kodu güvenli sandbox analitik ortamına gönderiliyor..."
        )
        
        success, final_code, exec_result = await self_correct_loop(
            question=user_question,
            initial_code=generated_code,
            schema=critique_schema,
            intent=intent,
            execute_fn=execute_fn,
            llm_correct_fn=llm_correct_fn,
            max_attempts=3,
            ws_callback=ws_callback
        )

        if success:
            # If it is a time-series forecast and LLM API is available, generate a highly detailed report using the PredictorAgent
            if is_forecast and self.api_key and exec_result.get("data") and "Tip" in exec_result["data"].get("columns", []):
                try:
                    await send_status("[PredictorAgent] Gelecek dönem tahminleri yorumlanıyor, LLM Analiz Raporu hazırlanıyor...")
                    import logging
                    df_forecast = pd.DataFrame(
                        exec_result["data"]["rows"],
                        columns=exec_result["data"]["columns"]
                    )
                    cols = exec_result["data"]["columns"]
                    time_col = cols[0]
                    val_col = cols[1]
                    agent_msg = await self._generate_forecast_narrative(user_question, df_forecast, time_col, val_col)
                except Exception as e:
                    logging.error(f"PredictorAgent narrative failed: {e}")
                    agent_msg = self._generate_agent_summary(user_question, exec_result, is_sql)
            else:
                agent_msg = self._generate_agent_summary(user_question, exec_result, is_sql)
            
            # Cache successfully executed query in TF-IDF memory RAG
            add_to_memory(
                question=user_question,
                intent=intent,
                code=final_code,
                source_id=rag_key,
                feedback="neutral",
                execution_success=True,
                schema_snapshot=source_meta["schema"]
            )
            
            return {
                "success": True,
                "generated_code": final_code,
                "data": exec_result.get("data"),
                "visualization": exec_result.get("visualization"),
                "final_response": agent_msg,
                "auto_corrections": exec_result.get("_auto_corrections") if isinstance(exec_result, dict) else None
            }
        else:
            # Cache failed query in TF-IDF memory for avoidance
            add_to_memory(
                question=user_question,
                intent=intent,
                code=final_code,
                source_id=rag_key,
                feedback="neutral",
                execution_success=False,
                schema_snapshot=source_meta["schema"]
            )
            
            return {
                "success": False,
                "error": str(exec_result),
                "generated_code": final_code,
                "final_response": f"Kod 3 otomatik deneme sonrasında çalıştırılamadı.\n\nAlınan Son Hata:\n```\n{str(exec_result)}\n```",
                "auto_corrections": None
            }

    def _get_source_metadata(self, source_id: str) -> Optional[Dict[str, Any]]:
        # Check files
        files = get_uploaded_files()
        for f in files:
            if f["id"] == source_id or f["alias"] == source_id:
                return {
                    "id": f["id"],
                    "alias": f["alias"],
                    "type": "file",
                    "file_path": f["file_path"],
                    "schema": f["schema"],
                    "row_count": f["row_count"]
                }
        # Check databases
        sources = get_data_sources()
        for s in sources:
            if s["id"] == source_id:
                db_path = DEMO_DB_PATH
                if s["connection_details"] and "database_path" in s["connection_details"]:
                    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), s["connection_details"]["database_path"])
                return {
                    "id": s["id"],
                    "alias": s["id"],
                    "type": "database",
                    "db_type": s["type"],
                    "db_path": db_path,
                    "connection_details": s["connection_details"],
                    "schema": s["schema"]
                }
        return None

    def _resolve_sources(self, active_source_id: str, source_ids: List[str], explicit: bool) -> Dict[str, Any]:
        warnings: List[str] = []
        all_files = get_uploaded_files()
        all_dbs = get_data_sources()

        if not source_ids:
            source_ids = [active_source_id]

        file_items = []
        db_items = []

        for sid in source_ids:
            file_match = next((f for f in all_files if f["id"] == sid or f["alias"] == sid), None)
            if file_match:
                file_items.append({
                    "id": file_match["id"],
                    "alias": file_match["alias"],
                    "type": "file",
                    "file_path": file_match["file_path"],
                    "schema": file_match["schema"],
                    "row_count": file_match["row_count"]
                })
                continue
            db_match = next((s for s in all_dbs if s["id"] == sid), None)
            if db_match:
                db_path = DEMO_DB_PATH
                if db_match["connection_details"] and "database_path" in db_match["connection_details"]:
                    db_path = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                        db_match["connection_details"]["database_path"]
                    )
                db_items.append({
                    "id": db_match["id"],
                    "alias": db_match["id"],
                    "type": "database",
                    "db_type": db_match["type"],
                    "db_path": db_path,
                    "connection_details": db_match["connection_details"],
                    "schema": db_match["schema"]
                })

        if not file_items and not db_items:
            return {"meta": None, "warnings": warnings}

        source_map: Dict[str, List[str]] = {}
        for item in file_items:
            source_map[item["id"]] = [item["alias"]]
        db_schema_map: Dict[str, List[str]] = {}
        for item in db_items:
            table_names = list(item.get("schema", {}).keys())
            source_map[item["id"]] = [f"{item['id']}__{tbl}" for tbl in table_names]
            for tbl, cols in item.get("schema", {}).items():
                db_schema_map[f"{item['id']}__{tbl}"] = cols

        if not explicit and file_items:
            if db_items:
                warnings.append("Secim yapilmadi. Tum dosyalar kullaniliyor, veritabanlari disarida birakildi.")
            if len(file_items) == 1:
                meta = file_items[0]
                meta["rag_key"] = meta["id"]
                meta["source_map"] = source_map
                return {"meta": meta, "warnings": warnings}
            combined_schema = {item["alias"]: item["schema"] for item in file_items}
            file_mappings = {item["alias"]: item["file_path"] for item in file_items}
            rag_key = "multi:" + ",".join(sorted([item["id"] for item in file_items]))
            return {
                "meta": {
                    "id": rag_key,
                    "alias": "multi_file",
                    "type": "file",
                    "schema": combined_schema,
                    "file_mappings": file_mappings,
                    "rag_key": rag_key,
                    "source_map": source_map
                },
                "warnings": warnings
            }

        if db_items and not file_items:
            if len(db_items) == 1:
                primary = db_items[0]
                primary["rag_key"] = primary["id"]
                primary["source_map"] = source_map
                return {"meta": primary, "warnings": warnings}
            # Deterministic rag_key: her DB kombinasyonu kendi bellek kovasina sahip
            multi_db_rag_key = "multi_db:" + ",".join(sorted([item["id"] for item in db_items]))
            return {
                "meta": {
                    "id": "multi_db",
                    "alias": "multi_db",
                    "type": "file",
                    "schema": db_schema_map,
                    "db_sources": db_items,
                    "rag_key": multi_db_rag_key,
                    "source_map": source_map
                },
                "warnings": ["Birden fazla veritabani secildi. Analiz pandas ile yapilacak."]
            }

        # Deterministic rag_key: dosya ve DB kombinasyonu icin benzersiz anahtar
        mixed_rag_key = "mixed:" + ",".join(sorted(
            [item["id"] for item in file_items] + [item["id"] for item in db_items]
        ))
        return {
            "meta": {
                "id": "mixed_sources",
                "alias": "mixed_sources",
                "type": "file",
                "schema": {**{item["alias"]: item["schema"] for item in file_items}, **db_schema_map},
                "file_mappings": {item["alias"]: item["file_path"] for item in file_items},
                "db_sources": db_items,
                "rag_key": mixed_rag_key,
                "source_map": source_map
            },
            "warnings": ["Dosya ve veritabani birlikte secildi. Analiz pandas ile yapilacak."]
        }

        if len(file_items) == 1:
            meta = file_items[0]
            meta["rag_key"] = meta["id"]
            meta["source_map"] = source_map
            return {"meta": meta, "warnings": warnings}

        combined_schema = {item["alias"]: item["schema"] for item in file_items}
        file_mappings = {item["alias"]: item["file_path"] for item in file_items}
        rag_key = "multi:" + ",".join(sorted([item["id"] for item in file_items]))
        return {
            "meta": {
                "id": rag_key,
                "alias": "multi_file",
                "type": "file",
                "schema": combined_schema,
                "file_mappings": file_mappings,
                "rag_key": rag_key,
                "source_map": source_map
            },
            "warnings": warnings
        }

    def _materialize_db_sources(self, db_sources: List[Dict[str, Any]], max_rows: int = 2000) -> Tuple[Dict[str, str], Dict[str, List[str]], str]:
        from app.database.connectors import execute_safe_sql

        temp_dir = tempfile.mkdtemp(prefix="deepbi_db_")
        file_mappings: Dict[str, str] = {}
        schema_map: Dict[str, List[str]] = {}

        for db in db_sources:
            db_id = db["id"]
            db_type = db.get("db_type", "sqlite")
            schema = db.get("schema", {})
            for table_name, cols in schema.items():
                if not table_name:
                    continue
                if db_type in ("mysql", "mariadb"):
                    safe_table = f"`{table_name}`"
                else:
                    safe_table = f"\"{table_name}\""
                sql = f"SELECT * FROM {safe_table} LIMIT {max_rows}"
                try:
                    res = execute_safe_sql(db_type, db.get("connection_details", {}), sql)
                except Exception:
                    continue

                columns = res.get("columns", [])
                rows = res.get("rows", [])
                df_name = f"{db_id}__{table_name}"
                csv_path = os.path.join(temp_dir, f"{df_name}.csv")
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if columns:
                        writer.writerow(columns)
                    for row in rows:
                        writer.writerow(row)

                file_mappings[df_name] = csv_path
                schema_map[df_name] = columns or list(cols or [])

        return file_mappings, schema_map, temp_dir

    def _classify_intent(self, question: str, source_meta: Dict[str, Any]) -> str:
        if source_meta["type"] == "database":
            return "sql_query"
        return "file_analysis"

    def _build_semantic_context(self, source_id: str) -> str:
        try:
            from app.database.manager import get_semantic_mapping
            mapping = get_semantic_mapping(source_id)
            if not mapping:
                return ""
            
            lines = []
            for table, cols in mapping.items():
                if not cols:
                    continue
                lines.append(f"- Tablo '{table}':")
                for col, info in cols.items():
                    label = info.get("label", "")
                    desc = info.get("description", "")
                    if label or desc:
                        label_part = f' Takma Ad: "{label}"' if label else ""
                        desc_part = f' Açıklama: "{desc}"' if desc else ""
                        lines.append(f"  * Kolon '{col}':{label_part}{desc_part}")
            
            if lines:
                return "\n### Tablo ve Kolonların İş Tanımları (Semantik Katman):\n" + "\n".join(lines) + "\n"
        except Exception:
            pass
        return ""

    async def _generate_sql_llm(self, question: str, meta: Dict[str, Any], examples: List[Dict[str, Any]]) -> str:
        # Build compact schema: {table: [col1, col2, ...]}
        schema = meta.get("schema", {})
        schema_lines = []
        for tbl, cols in schema.items():
            if isinstance(cols, dict):
                col_names = list(cols.keys())
            elif isinstance(cols, list):
                col_names = cols
            else:
                continue
            schema_lines.append(f"  {tbl}({', '.join(col_names)})")
        schema_str = "\n".join(schema_lines) or json.dumps(schema)

        db_type = meta.get("db_type", "sqlite")
        dialect = ""
        if db_type in ("sap_s4hana", "hana"):
            dialect = "\nDiyalekt: SAP HANA SQL. Dummy tablo için DUMMY kullan."
        elif db_type == "postgresql":
            dialect = "\nDiyalekt: PostgreSQL. Uygun sözdizimini kullan."
        elif db_type == "mysql":
            dialect = "\nDiyalekt: MySQL 8+. BACKTICK ile tablo/sütun sar."
        elif db_type == "snowflake":
            dialect = "\nDiyalekt: Snowflake SQL. Sütun ve tablo isimlerini büyük harfle çift tırnak (örneğin \"ID\", \"NAME\") ile sarmak gerekebilir."
        elif db_type in ("mssql", "sqlserver"):
            dialect = "\nDiyalekt: Microsoft SQL Server (T-SQL). Sorguda LIMIT yerine SELECT TOP N kullanın."
        elif db_type in ("bigquery", "google_bigquery"):
            dialect = "\nDiyalekt: Google BigQuery Standard SQL. Dataset ve tablo adlarını backtick (örneğin `dataset.table`) ile sar."

        semantic_desc = self._build_semantic_context(meta.get("id") or meta.get("alias"))

        # Intent hint
        q_low = question.lower()
        is_listing = any(kw in q_low for kw in ["göster", "listele", "getir", "örnek", "sample", "random", "rastgele", "ilk", "first", "son", "last"])
        is_agg = any(kw in q_low for kw in ["toplam", "sum", "ortalama", "avg", "say", "count", "max", "min", "en çok", "en az", "grupla", "group"])

        if is_listing and not is_agg:
            intent_hint = "Not: Bu bir listeleme/örnek sorgusudur. LIMIT kullan (genellikle 5-20 arası), GROUP B  veya aggregation KULLANMA."
        elif is_agg:
            intent_hint = "Not: Bu bir analiz/aggregasyon sorgusudur. SUM/COUNT/AVG/MAX/MIN ve GROUP B  kullan."
        else:
            intent_hint = "Not: Sorguyu amaca uygun yaz; gerekirse LIMIT ekle."

        examples_str = "\n".join([f"S: {e['question']}\nSQL: {e['code']}" for e in examples[:3]]) or " ok"

        prompt = f""" ou are a senior SQL Expert. Write a read-only SQL query based on the following schema.{dialect}

## Schema
{schema_str}
{semantic_desc}

## Examples
{examples_str}

## Instructions & Rules:
1. Use SELECT or WITH only. DML/DDL (UPDATE/DELETE/INSERT/DROP/ALTER) is strictly forbidden.
2. Never add semicolons or wrap output in code blocks (e.g. ```sql). Return raw query string.
3. {intent_hint}
4. Superlatives Rule: Always order by the metric (ORDER B  DESC for "highest", "most", "largest", "maximum"; ORDER B  ASC for "lowest", "least", "smallest", "minimum") before using LIMIT.
5. Limit Rule: If the question implies a singular item (e.g., "highest revenue product"), always use LIMIT 1. For lists or plurals, use the specified limit or a reasonable default (e.g., 5 or 10). Never use LIMIT without ORDER B !
6. Output: SADECE/ONL  runnable executable SQL. No explanations.

Question: {question}
SQL:"""

        return await self._call_deepseek(prompt)

    async def _generate_duckdb_sql_llm(self, question: str, meta: Dict[str, Any], examples: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> str:
        alias = meta["alias"]
        schema = meta.get("schema", {})
        dataset_names = list(meta.get("file_mappings", {alias: meta.get("file_path")}).keys())
        for key in (schema.keys() if isinstance(schema, dict) else []):
            if key not in dataset_names:
                dataset_names.append(key)

        # Compact schema: table(col1, col2, ...)
        schema_lines = []
        for tbl, cols in (schema.items() if isinstance(schema, dict) else []):
            if isinstance(cols, dict):
                col_names = list(cols.keys())
            elif isinstance(cols, list):
                col_names = [str(c) for c in cols]
            else:
                continue
            schema_lines.append(f"  {tbl}({', '.join(col_names)})")
        schema_str = "\n".join(schema_lines) or json.dumps(schema, ensure_ascii=False)

        # Relationships
        rel_desc = " ok"
        if relationships:
            source_map = meta.get("source_map", {})
            rel_lines = []
            for r in relationships:
                ls, rs = r.get("leftSourceId", ""), r.get("rightSourceId", "")
                lc, rc = r.get("leftColumn", ""), r.get("rightColumn", "")
                ldf = f"{ls}__{lc.split('.')[0]}" if "." in lc else (source_map.get(ls, [""])[0] if source_map.get(ls) else ls)
                rdf = f"{rs}__{rc.split('.')[0]}" if "." in rc else (source_map.get(rs, [""])[0] if source_map.get(rs) else rs)
                rel_lines.append(f"  {ldf}.{lc} = {rdf}.{rc} ({r.get('joinType', 'auto')} join)")
            rel_desc = "\n".join(rel_lines)

        semantic_desc = self._build_semantic_context(meta.get("id") or meta.get("alias"))
        examples_str = "\n".join([f"S: {e['question']}\nSQL: {e['code']}" for e in examples[:3]]) or " ok"

        # Intent-aware hint
        q_low = question.lower()
        is_listing = any(kw in q_low for kw in ["göster", "listele", "getir", "örnek", "sample", "random", "rastgele", "ilk", "first", "son", "last", "tüm", "all"])
        is_agg = any(kw in q_low for kw in ["toplam", "sum", "ortalama", "avg", "say", "count", "max", "min", "en çok", "en az", "grupla", "group", "däğilşim", "dağılım"])

        if is_listing and not is_agg:
            intent_hint = "Listeleme/örnek sorgusu — LIMIT kullan (5-20 satır), GROUP B  / aggregation KULLANMA."
            if "random" in q_low or "rastgele" in q_low:
                intent_hint += " Rastgele sıralıyor ise ORDER B  RANDOM() kullan."
        elif is_agg:
            intent_hint = "Analiz/aggregasyon sorgusu — GROUP B , SUM/COUNT/AVG/MAX/MIN kullan. LIMIT gerekmedikçe ekleme."
        else:
            intent_hint = "Uygun bir SELECT sorgusu yaz; ihtiyaç duyulursa LIMIT ekle."

        prompt = f""" ou are a senior DuckDB SQL Expert. Write a read-only DuckDB SQL query based on the following tables and schema.

## Tables
{chr(10).join(f'  - {n}' for n in dataset_names)}

## Schema
{schema_str}
{semantic_desc}

## Relationships (JOIN)
{rel_desc}

## Examples
{examples_str}

## Instructions & Rules:
1. Use SELECT or WITH only. DML/DDL (UPDATE/DELETE/INSERT/DROP) is strictly forbidden.
2. Never add semicolons or wrap output in code blocks (e.g. ```sql). Return raw query string.
3. Intent: {intent_hint}
4. Superlatives Rule: Always order by the metric (ORDER B  DESC for "highest", "most", "largest", "maximum"; ORDER B  ASC for "lowest", "least", "smallest", "minimum") before using LIMIT.
5. Limit Rule: If the question implies a singular item (e.g., "highest revenue product"), always use LIMIT 1. For lists or plurals, use the specified limit or a reasonable default (e.g., 5 or 10). Never use LIMIT without ORDER B !
6. Ensure exact table and column names from the schema are used.
7. Output: SADECE/ONL  runnable executable DuckDB SQL. No explanations.

Question: {question}
SQL:"""

        return await self._call_deepseek(prompt)


    async def _llm_correct_duckdb(self, question: str, code: str, error: str, schema: Dict[str, Any]) -> str:
        schema_desc = json.dumps(schema, indent=2)
        prompt = f""" ou are an elite enterprise DuckDB SQL Error Correction expert.
Analyze the provided invalid DuckDB SQL query, database schemas, and error message, and return the corrected SQL query.

### Database Table Schemas:
{schema_desc}

### Erroneous SQL Query:
{code}

### Error Message:
{error}

### User Question:
{question}

### Correction Rules:
1. Only write read-only SELECT or WITH queries.
2. Do not use semicolons or markdown block wraps.
3. Ensure every referenced table and column exists in the schema. Do not invent columns.
4. Output: SADECE/ONL  valid corrected runnable DuckDB SQL. No explanation.

Corrected SQL query:"""
        return await self._call_deepseek(prompt)

    async def _generate_pandas_llm(self, question: str, meta: Dict[str, Any], examples: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> str:
        alias = meta["alias"]
        examples_desc = "\n".join([f"Soru: {e['question']}\nPython Kodu:\n{e['code']}" for e in examples])
        schema_desc = json.dumps(meta["schema"], ensure_ascii=False)
        dataset_names = list(meta.get("file_mappings", {alias: meta.get("file_path")}).keys())
        if isinstance(meta.get("schema"), dict):
            for key in meta["schema"].keys():
                if key not in dataset_names:
                    dataset_names.append(key)
        rel_desc = " ok"
        if relationships:
            source_map = meta.get("source_map", {})
            rel_lines = []
            for r in relationships:
                left_source = r.get("leftSourceId")
                right_source = r.get("rightSourceId")
                left_col = r.get("leftColumn") or ""
                right_col = r.get("rightColumn") or ""
                left_df = ""
                right_df = ""

                if "." in left_col:
                    table_name = left_col.split(".", 1)[0]
                    left_df = f"{left_source}__{table_name}"
                elif left_source in source_map and source_map[left_source]:
                    left_df = source_map[left_source][0]

                if "." in right_col:
                    table_name = right_col.split(".", 1)[0]
                    right_df = f"{right_source}__{table_name}"
                elif right_source in source_map and source_map[right_source]:
                    right_df = source_map[right_source][0]

                left_hint = f"{left_df}.{left_col}" if left_df else f"{left_source}.{left_col}"
                right_hint = f"{right_df}.{right_col}" if right_df else f"{right_source}.{right_col}"
                rel_lines.append(f"- {left_hint} = {right_hint} (join: {r.get('joinType', 'auto')})")
            rel_desc = "\n".join(rel_lines)
        
        prompt = f""" ou are a world-class Data Scientist and Visualization expert (VisualizerAgent).
Write a secure Python script utilizing Pandas and Plotly to analyze the active dataset and produce a stunning dark-theme chart.

### Dataset Details:
- Active DataFrames: {', '.join(dataset_names)}
- Columns & Types: {schema_desc}
- Relationships:
{rel_desc}

### Examples:
{examples_desc}

### Rules for Python Generation (VisualizerAgent):
1. Assign the final DataFrame, Series, or summary to the variable `result` (e.g., `result = df.groupby(...)`).
2. If visualization is requested, assign a Plotly Figure object to the variable `fig` (e.g., `fig = px.bar(...)`).
3. Apply this mandatory premium dark styling to the Plotly figure:
   - Template: `fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")`
   - Font & Title: `fig.update_layout(title=dict(text="Chart Title", font=dict(family="Inter, sans-serif", size=13, color="#e6edf3")), font=dict(family="Inter, sans-serif", color="#8b949e"))`
   - Gridlines: `fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#21262d")` and `fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#21262d")`
   - Margins: `fig.update_layout(margin=dict(t=40, r=10, l=40, b=40))`
4. Never read files (No `pd.read_csv` or `pd.read_excel`). DataFrames are pre-loaded in context.
5. If multiple DataFrames, join/merge them using Pandas. Prefer active relationships.
6. Strictly forbid network access, file writing, print() calls, and imports like os, sys, subprocess.
7. Output: SADECE/ONL  valid runnable Python code without markdown blocks.

User Question: {question}
Python Code:"""

        return await self._generate_pandas_llm_call(prompt)

    async def _generate_pandas_llm_call(self, prompt: str) -> str:
        return await self._call_deepseek(prompt)

    async def _llm_correct_sql(self, question: str, code: str, error: str, schema: Dict[str, Any]) -> str:
        schema_desc = json.dumps(schema, indent=2)
        prompt = f""" ou are an elite enterprise SQL Error Correction expert.
Analyze the provided SQL query, database schemas, and error message, and return the corrected SQL query.

### Database Schema:
{schema_desc}

### Erroneous SQL Query:
{code}

### Error Message:
{error}

### User Question:
{question}

### Correction Rules:
1. Only write read-only SELECT or WITH queries.
2. Do not use semicolons or markdown block wraps.
3. Ensure every referenced column and table exists in the schema. Do not invent columns.
4. Output: SADECE/ONL  valid corrected runnable SQL. No explanation.

Corrected SQL query:"""
        return await self._call_deepseek(prompt)

    async def _llm_correct_python(self, question: str, code: str, error: str, schema: Dict[str, Any]) -> str:
        schema_desc = json.dumps(schema, indent=2)
        prompt = f""" ou are an elite Python Data Science Debugging expert.
Analyze the erroneous Pandas/Plotly code, DataFrame schema, and sandbox error message, and return the corrected Python code.

### DataFrame Structure:
{schema_desc}

### Erroneous Python Code:
{code}

### Error Message:
{error}

### User Question:
{question}

### Correction Rules:
1. Assign final result to the variable `result`.
2. Assign the Plotly Figure to the variable `fig`.
3. Do not read files. DataFrames are pre-loaded in context.
4. Strictly ensure all referenced column names match the schema exactly.
5. Output: SADECE/ONL  valid corrected runnable Python code. No explanation.

Corrected Python Code:"""
        return await self._call_deepseek(prompt)

    async def _call_deepseek(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": " ou are a specialized code generation assistant. Output ONL  valid, runnable code without explanations or markdown formatting."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=30.0
            )
            response.raise_for_status()
            res_json = response.json()
            code_out = res_json["choices"][0]["message"]["content"].strip()
            if code_out.startswith("```"):
                lines = code_out.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                code_out = "\n".join(lines).strip()
            return code_out

    async def _call_llm_analyst(self, prompt: str) -> str:
        if not self.api_key:
            return ""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": " ou are a senior Business Intelligence Analyst and Data Science expert. Write a premium executive summary report interpreting the forecasting results (trends, growth rates, confidence intervals) and providing 3 actionable business recommendations. Output rich markdown in Turkish (or matching the user question's language)."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=30.0
                )
                response.raise_for_status()
                res_json = response.json()
                return res_json["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f"Tahmin analiz raporu oluşturulamadı: {str(e)}"

    async def _generate_forecast_narrative(self, question: str, df_forecast: pd.DataFrame, time_col: str, val_col: str) -> str:
        # Separate actual vs forecast rows
        df_actual = df_forecast[df_forecast["Tip"] == "Gerçek"]
        df_pred = df_forecast[df_forecast["Tip"] == "Tahmin"]
        
        # Calculate statistics
        actual_total = df_actual[val_col].sum()
        actual_avg = df_actual[val_col].mean()
        last_actual = df_actual[val_col].iloc[-1]
        
        pred_vals = df_pred[val_col].tolist()
        pred_dates = df_pred[time_col].tolist()
        
        # Exclude the connecting point if duplicate
        if len(pred_vals) > 1:
            forecast_only_vals = pred_vals[1:]
            forecast_only_dates = pred_dates[1:]
        else:
            forecast_only_vals = pred_vals
            forecast_only_dates = pred_dates
            
        forecast_avg = sum(forecast_only_vals) / len(forecast_only_vals) if forecast_only_vals else 0
        forecast_peak = max(forecast_only_vals) if forecast_only_vals else 0
        forecast_peak_date = forecast_only_dates[forecast_only_vals.index(forecast_peak)] if forecast_only_vals else "N/A"
        
        # Growth Rate
        first_pred = forecast_only_vals[0] if forecast_only_vals else last_actual
        last_pred = forecast_only_vals[-1] if forecast_only_vals else last_actual
        growth_rate = ((last_pred - last_actual) / last_actual * 100) if last_actual != 0 else 0
        
        # Formatting for prompt
        actual_summary = "\n".join([f"- {row[time_col]}: {row[val_col]:,.2f}" for _, row in df_actual.iterrows()])
        forecast_summary = "\n".join([f"- {row[time_col]}: {row[val_col]:,.2f} (Güven Sınırları: {row['Lower_CI']:,.2f} - {row['Upper_CI']:,.2f})" for _, row in df_forecast[df_forecast["Tip"] == "Tahmin"].iterrows()][1:])
        
        prompt = f"""User Question: {question}

### Historical Actual Data:
Columns: {time_col} (Date), {val_col} (Value)
{actual_summary}

Total Actual: {actual_total:,.2f}
Average Actual: {actual_avg:,.2f}
Last Actual Point ({df_actual[time_col].iloc[-1]}): {last_actual:,.2f}

### AI ML Ridge Forecast Results (Future):
Predicted Columns: {time_col} (Date), {val_col} (Value)
{forecast_summary}

Average Future Prediction: {forecast_avg:,.2f}
Predicted Peak Point ({forecast_peak_date}): {forecast_peak:,.2f}
Predicted Growth Rate compared to Last Actual: %{growth_rate:,.2f}

Generate a premium, detailed "Forecast Analysis Report" in Turkish (or matching user's language) following these instructions:
1. Introduction: Summarize the general direction and trend (increase, decrease, stable).
2. Analysis: Interpret the growth rate (%{growth_rate:,.2f}), peak prediction, and the 95% confidence intervals (what the width of the interval means).
3. Recommendations: Provide exactly 3 highly specific, actionable business recommendations for executive leadership.
4. Format using beautiful, structured markdown (headers, bolding, bullet points).
"""
        return await self._call_llm_analyst(prompt)

    def _generate_fallback_code(self, question: str, meta: Dict[str, Any], is_sql: bool) -> str:
        q = question.lower()
        alias = meta["alias"]
        schema = meta["schema"]
        if isinstance(schema, dict) and schema:
            if all(isinstance(v, dict) for v in schema.values()):
                first_alias = list(schema.keys())[0]
                alias = first_alias
                schema = schema[first_alias]
            else:
                first_dict = next((v for v in schema.values() if isinstance(v, dict)), None)
                if first_dict:
                    schema = first_dict
        
        # 1. SQL Query Fallback
        if is_sql:
            # Fallback table name and columns derived dynamically from schema
            table_name = alias
            col_list = []
            if isinstance(schema, dict):
                col_list = list(schema.keys())
            elif isinstance(schema, list):
                col_list = [str(c) for c in schema]
            
            # Safe select cols (limit to max 8 columns for readability)
            select_cols = col_list[:8] if col_list else ["*"]
            cols_str = ", ".join(select_cols)
            
            # Helper to find column matching keywords
            def find_col_sql(keywords: List[str]) -> Optional[str]:
                for col in col_list:
                    c_low = col.lower()
                    if any(kw in c_low for kw in keywords):
                        return col
                return None

            # Look for common column types in active schema
            c_text = find_col_sql(["ad", "soyad", "name", "sehir", "şehir", "kategori", "category", "urun", "ürün", "cinsiyet", "gender", "tip", "type"])
            c_num = find_col_sql(["ciro", "satis", "satış", "tutar", "adet", "sayi", "sayı", "hedef", "gerçekleşen", "churn", "oran", "rate", "tutar", "amount", "total"])
            
            if not c_text and col_list:
                c_text = col_list[0]
            if not c_num and len(col_list) > 1:
                c_num = col_list[1]
                
            if ("şehir" in q or "sehir" in q or "şehirler" in q or "sehirler" in q) and c_text:
                return f"SELECT {c_text}, COUNT(*) as kayit_sayisi FROM {table_name} GROUP B  {c_text} ORDER B  kayit_sayisi DESC"
            elif ("en çok" in q or "en cok" in q or "popüler" in q or "top" in q or "satan" in q or "yüksek" in q or "yuksek" in q) and c_text and c_num:
                limit = 5
                limit_match = re.search(r'\b(\d+)\b', q)
                if limit_match:
                    limit = int(limit_match.group(1))
                return f"SELECT {c_text}, SUM({c_num}) as toplam_deger FROM {table_name} GROUP B  {c_text} ORDER B  toplam_deger DESC LIMIT {limit}"
            elif ("kategori" in q or "grup" in q or "sınıf" in q or "sinif" in q) and c_text and c_num:
                return f"SELECT {c_text}, COUNT(*) as kayit_sayisi, SUM({c_num}) as toplam_deger FROM {table_name} GROUP B  {c_text} ORDER B  toplam_deger DESC"
            elif ("trend" in q or "tarih" in q or "zaman" in q or "aylık" in q or "aylik" in q or "yıllık" in q or "yillik" in q) and c_text and c_num:
                c_date = find_col_sql(["tarih", "date", "ay", "yil", "yıl", "month", "year", "time"]) or c_text
                return f"SELECT {c_date}, SUM({c_num}) as toplam_deger FROM {table_name} GROUP B  {c_date} ORDER B  {c_date} ASC"
            
            # Default fallback listing query dynamically targeting active schema table and columns
            return f"SELECT {cols_str} FROM {table_name} LIMIT 50"
            
        # 2. Python/Pandas Analysis Fallback
        else:
            col_list = list(schema.keys())
            
            def find_col(keywords: List[str]) -> Optional[str]:
                for col in col_list:
                    c_low = col.lower()
                    if any(kw in c_low for kw in keywords):
                        return col
                return None

            c_prod = find_col(["urun", "ürün", "product", "ad", "name"]) or col_list[0]
            c_rev = find_col(["ciro", "satis", "satış", "revenue", "tutar", "fiyat", "gerçekleşen", "hedef"]) or (col_list[1] if len(col_list) > 1 else col_list[0])
            c_cat = find_col(["kategori", "category", "grup", "group"])
            c_qty = find_col(["adet", "miktar", "quantity", "sayı", "sayi"])
            c_date = find_col(["tarih", "date", "ay", "yil", "yıl", "month", "year"])

            if "ürün" in q or "urun" in q or "top" in q or "en çok" in q:
                code = f"result = {alias}.groupby('{c_prod}')['{c_rev}'].sum().reset_index().sort_values(by='{c_rev}', ascending=False)\n"
                code += f"result = result.head(10)\n"
                code += f"fig = px.bar(result, x='{c_prod}', y='{c_rev}', title='Ürün Bazında Toplam Değer (En  üksek 10)', labels={{'{c_prod}': 'Ürün', '{c_rev}': 'Toplam Değer'}})\n"
                return code
            elif "kategori" in q or "grup" in q or "dağılım" in q or "dagilim" in q:
                group_col = c_cat if c_cat else c_prod
                code = f"result = {alias}.groupby('{group_col}')['{c_rev}'].sum().reset_index()\n"
                code += f"fig = px.pie(result, names='{group_col}', values='{c_rev}', title='Kategori/Grup Bazında Dağılım')\n"
                return code
            elif "trend" in q or "tarih" in q or "zaman" in q or "aylara göre" in q or "aylik" in q or "aylık" in q:
                time_col = c_date if c_date else col_list[0]
                code = f"result = {alias}.groupby('{time_col}')['{c_rev}'].sum().reset_index()\n"
                if c_qty:
                    code = f"result = {alias}.groupby('{time_col}')[['{c_rev}', '{c_qty}']].sum().reset_index()\n"
                code += f"fig = px.line(result, x='{time_col}', y='{c_rev}', title='Zaman Serisi Analizi', markers=True)\n"
                return code
            elif "karşılaştır" in q or "karsilastir" in q or "fark" in q:
                target_col = find_col(["hedef", "target"])
                actual_col = find_col(["gerçekleşen", "gerceklesen", "actual", "ciro", "satış", "satis"])
                time_col = c_date if c_date else col_list[0]
                
                if target_col and actual_col:
                    code = f"df = {alias}.copy()\n"
                    code += f"df['Fark'] = df['{actual_col}'] - df['{target_col}']\n"
                    code += f"result = df[[{repr(time_col) if c_date else repr(c_prod)}, '{target_col}', '{actual_col}', 'Fark']]\n"
                    code += f"fig = px.bar(result, x={repr(time_col) if c_date else repr(c_prod)}, y=['{actual_col}', '{target_col}'], barmode='group', title='Hedef ve Gerçekleşen Karşılaştırması')\n"
                    return code
            
            code = f"result = {alias}.groupby('{c_prod}')['{c_rev}'].sum().reset_index().head(20)\n"
            code += f"fig = px.bar(result, x='{c_prod}', y='{c_rev}', title='Genel Dağılım Analizi')\n"
            return code

    def _execute_local_sql(self, sql_query: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        db_type = meta.get("db_type", "sqlite")
        
        if db_type == "sqlite":
            conn = sqlite3.connect(meta["db_path"])
            cursor = conn.cursor()
            try:
                cursor.execute(sql_query)
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                serialized_rows = [list(r) for r in rows]
            finally:
                conn.close()
        else:
            from app.database.connectors import execute_safe_sql
            res = execute_safe_sql(db_type, meta.get("connection_details", {}), sql_query)
            columns = res["columns"]
            serialized_rows = res["rows"]
            
        data = {
            "columns": columns,
            "index": list(range(len(serialized_rows))),
            "rows": serialized_rows,
            "row_count": len(serialized_rows)
        }
        
        visualization = None
        try:
            import pandas as pd
            df = pd.DataFrame(serialized_rows, columns=columns)
            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col])
                except Exception:
                    pass
            import plotly.express as px
            
            if len(columns) >= 2:
                sql_low = sql_query.lower()
                # Suppress chart for listing/sample queries (LIMIT without aggregation, RANDOM, ORDER B  RANDOM, etc.)
                is_listing_query = (
                    ("limit" in sql_low and not any(kw in sql_low for kw in ["group by", "sum(", "count(", "avg(", "max(", "min("]))
                    or "random()" in sql_low or "rand()" in sql_low or "tablesample" in sql_low
                    or "select *" in sql_low.replace(" ", "")
                )
                is_aggregated = any(kw in sql_low for kw in ["group by", "sum(", "count(", "avg(", "max(", "min("])
                
                # Only create visualization for aggregated queries with enough rows
                if not is_listing_query and len(df) > 3 and is_aggregated:
                    num_cols = df.select_dtypes(include=['number']).columns
                    str_cols = df.select_dtypes(include=['object', 'string']).columns
                    
                    if len(num_cols) > 0 and len(str_cols) > 0:
                        x_col = str_cols[0]
                        y_col = num_cols[0]
                        is_trend = any("tarih" in col.lower() or "date" in col.lower() or "ay" in col.lower() for col in str_cols)
                        
                        if is_trend:
                            fig = px.line(df.head(100), x=x_col, y=y_col, title=f"Zaman Serisi Trendi: {y_col}", markers=True)
                        else:
                            fig = px.bar(df.head(15), x=x_col, y=y_col, title=f"{x_col} Bazında {y_col} Analizi")
                            
                        visualization = json.loads(fig.to_json())
        except Exception:
            pass
            
        return {
            "success": True,
            "data": data,
            "visualization": visualization
        }

    def _generate_agent_summary(self, question: str, result: Dict[str, Any], is_sql: bool) -> str:
        data = result.get("data")
        if not data:
            return "Sorgu başarıyla çalıştırıldı fakat herhangi bir veri satırı dönmedi."
            
        row_count = data.get("row_count", 0)
        cols = data.get("columns", [])
        has_viz = bool(result.get("visualization"))
        
        # Detect query type from question
        q_low = question.lower()
        is_listing_q = any(kw in q_low for kw in [
            "göster", "listele", "getir", "örnek", "sample", "random", "rastgele",
            "ilk", "first", "son", "last", "tüm", "all", "satır", "row", "kayıt", "record"
        ])
        
        if is_listing_q and not has_viz:
            summary = f"### 📋 Veri Listesi\n\n**{row_count} satır** veri başarıyla getirildi. Sonuçlar sağdaki interaktif tabloda görüntülenmektedir. "
        else:
            summary = f"### 📊 Analiz Sonucu\n\nSorgunuz başarıyla çalıştırıldı ve **{row_count} satır** veri bulundu. "
        
        rows = data.get("rows", [])
        if rows and len(cols) >= 2 and not is_listing_q:
            try:
                num_idx = -1
                for idx, col in enumerate(cols):
                    if col != "Değişken" and isinstance(rows[0][idx], (int, float)):
                        num_idx = idx
                        break
                
                if num_idx != -1:
                    vals = [r[num_idx] for r in rows if r[num_idx] is not None]
                    if vals:
                        total = sum(vals)
                        avg = total / len(vals)
                        formatted_total = f"{total:,.2f}" if isinstance(total, float) else f"{total:,}"
                        formatted_avg = f"{avg:,.2f}"
                        summary += f"Toplam **{cols[num_idx]}** değeri: **{formatted_total}** (Ortalama: **{formatted_avg}**).\n\n"
            except Exception:
                pass
                
        if "Durum" in cols:
            try:
                durum_idx = cols.index("Durum")
                anom_count = sum(1 for r in rows if r[durum_idx] == "Anomali")
                summary += f"🚨  apay zekâ analizörümüz veri setinde **{anom_count} adet anomali (aykırı değer)** tespit etti! Aykırılıklar grafikte parlak kırmızı noktalarla işaretlenmiştir.\n\n"
            except Exception:
                pass
        elif "Değişken" in cols:
            summary += "🔗 Sayısal sütunlar arasındaki Pearson korelasyon katsayıları hesaplanmıştır. İlişkiler interaktif bir Heatmap grafiği ile görselleştirilmiştir.\n\n"

        if has_viz:
            summary += "✨ Veriyi daha iyi anlamanız için bir **görselleştirme grafiği** oluşturulup panelinize eklendi.\n"
        
        if is_listing_q and not has_viz:
            summary += "Tabloyu filtrelebilir, Excel veya CSV olarak dışa aktarabilirsiniz."
        else:
            summary += "\nSonuçları yandaki etkileşimli tablodan veya grafik sekmesinden inceleyebilir, Excel ya da PDF olarak raporlayabilirsiniz."
        return summary

