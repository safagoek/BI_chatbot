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
from app.agent import parsing, prompts
from app.database.manager import get_data_sources, get_uploaded_files
from app.core.logger import logger

class SupervisorAgent:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        try:
            from app.database.manager import get_llm_config
            db_config = get_llm_config()
        except Exception:
            db_config = {}

        self.api_key = api_key or db_config.get("apiKey") or os.getenv("DEEPSEEK_API_KEY")
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

        async def send_token(delta: str):
            # Streaming narratif yanıt: token parçaları frontend'de canlı yazılır
            if ws_callback and delta:
                await ws_callback({"type": "token", "delta": delta})

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
        is_ml = False

        # Exact command mappings for Autocomplete commands, then Legacy/Alias mappings
        slash_match = parsing.match_slash_command(cleaned_question)
        slash_command = None
        if slash_match:
            slash_command = next(
                (c for c in parsing.SLASH_COMMAND_TABLE
                 if cleaned_question.startswith(c[0] + " ") or cleaned_question == c[0]),
                None,
            )
            slash_command = slash_command[0] if slash_command else None
            forced_intent, cleaned_question, is_ml, route_label = slash_match
            await send_status(f"[RouterAgent] Yönlendirme algılandı: {route_label}")

        if forced_intent:
            intent = forced_intent
            is_sql = (intent == "sql_query")
            user_question = cleaned_question
        else:
            q_low = user_question.lower().strip()
            # Conceptual question heuristic — intent_keywords.py'den merkezi listeler
            if parsing.is_conceptual_question(q_low):
                intent = "conceptual"
                is_sql = False
                await send_status("[RouterAgent] Kavramsal/Bilgi sorgusu algılandı: CONCEPTUAL (Kavramsal Açıklama)")
            else:
                intent, is_ml = parsing.route_heuristic_intent(q_low, source_meta["type"] == "file")
                if intent == "file_analysis":
                    is_sql = False
                    await send_status("[RouterAgent] Sorgu rotası başarıyla belirlendi: FILE_ANALYSIS (Python/Pandas & ML)")
                else:
                    is_sql = True
                    await send_status("[RouterAgent] Sorgu rotası başarıyla belirlendi: SQL_QUERY")

        # /ask → kaynak tipine göre normal analiz akışı (sonuç metin özetlenir)
        if intent == "ask":
            intent = "sql_query" if source_meta["type"] == "database" else "file_analysis"
            is_sql = (intent == "sql_query")

        # /help → gerçek komut rehberi (LLM'e gerek yok, tek kaynak)
        if intent == "help":
            await send_status("[HelpAgent] Kullanım rehberi hazırlanıyor...")
            return {
                "success": True,
                "generated_code": "",
                "data": None,
                "visualization": None,
                "final_response": prompts.build_help_text(),
                "auto_corrections": None
            }

        # /explain → şema + örnek verilerle veri kümesi açıklaması (her iki yol aynı)
        if intent == "explain":
            await send_status("[ExplainAgent] Veri kümesi şeması ve analiz önerileri hazırlanıyor...")
            schema_str = json.dumps(source_meta.get("schema", {}), ensure_ascii=False)
            samples_desc = self._get_data_samples(source_meta)
            prompt = prompts.build_explain_prompt(schema_str, samples_desc or "")
            if self.api_key:
                try:
                    answer_text = await self._stream_analyst(prompt, send_token)
                except Exception as e:
                    answer_text = "### Veri Kümesi Açıklaması\n\n" + schema_str + f"\n\n*(LLM hatası: {str(e)})*"
            else:
                answer_text = "### Veri Kümesi Açıklaması\n\n" + schema_str
            return {
                "success": True,
                "generated_code": "",
                "data": None,
                "visualization": None,
                "final_response": answer_text,
                "auto_corrections": None
            }

        # Step 1.5: Conceptual Query Bypass
        if intent == "conceptual":
            await send_status("[ConceptualAgent] Konsept ve analitik açıklama raporu hazırlanıyor...")
            schema_str = json.dumps(source_meta.get("schema", {}), ensure_ascii=False)
            prompt = prompts.build_conceptual_prompt(schema_str, user_question)
            if self.api_key:
                try:
                    answer_text = await self._stream_analyst(prompt, send_token)
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
            prompt = prompts.build_report_prompt(schema_str)
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
                    generated_code = await self._generate_pandas_llm(user_question, source_meta, rag_examples, relationships or [], is_ml=is_ml)
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

        # Detect prediction, anomaly, and correlation intents.
        # Slash komutları bayrakları ZORLAR — kalan metindeki kelime şansına değil.
        q_low = user_question.lower()
        flags = parsing.detect_analysis_intents(q_low)
        for k, v in (parsing.command_flags(slash_command) if slash_command else {}).items():
            flags[k] = flags[k] or v
        if slash_command in ("/table", "/sqlquery"):
            flags["is_listing"] = True  # tablo komutu grafik üretmez
        is_forecast = flags["is_forecast"]
        is_anomaly = flags["is_anomaly"]
        is_correlation = flags["is_correlation"]
        is_clustering = flags["is_clustering"]
        # Detect listing/sample intent — these should return a table, NOT a chart
        is_listing = flags["is_listing"]

        # Komut yönergesini Coder'a ilet (ör. /pivot, /clean için net talimat)
        directive = parsing.command_directive(slash_command) if slash_command else None
        if directive:
            user_question = f"{user_question}\n\n(Yönerge: {directive})"

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

                            from app.core.visualizer import build_forecast_chart
                            result_data["visualization"] = build_forecast_chart(df_forecast, time_col, val_col)
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

                            from app.core.visualizer import build_anomaly_chart
                            result_data["visualization"] = build_anomaly_chart(df_anom, val_col)
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

                            from app.core.visualizer import build_correlation_heatmap
                            result_data["visualization"] = build_correlation_heatmap(df_corr)
                    except Exception:
                        pass
                # If is_clustering is requested, run KMeans clustering
                elif is_clustering and result_data.get("success") and result_data.get("data") and len(result_data["data"].get("rows", [])) >= 2:
                    try:
                        from app.core.clustering import run_kmeans_clustering
                        df_raw = pd.DataFrame(result_data["data"]["rows"], columns=result_data["data"]["columns"])
                        
                        n_clusters = parsing.extract_cluster_count(q_low)                                
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

                        from app.core.visualizer import build_clustering_chart
                        result_data["visualization"] = build_clustering_chart(df_clustered)
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

                from app.core.table_resolver import resolve_unknown_tables
                code_to_exec, corrections, ambiguous, unknown = resolve_unknown_tables(code_to_exec, allowed_tables)

                if unknown and not corrections:
                    # Belirsiz/bilinmeyen tablolar varsa ve hiç kesin düzeltme yoksa hata döndür
                    return False, {
                        "error": (
                            f"Sorgudaki tablo isimleri belirsiz veya bulunamadı: {ambiguous}. "
                            f"Lütfen şu tablolardan birini kullanın: {sorted(list(allowed_tables))}"
                        ),
                        "unknown": unknown,
                        "ambiguous": ambiguous,
                        "allowed": sorted(list(allowed_tables))
                    }

                if corrections:
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
                db_path = None
                if db_match["connection_details"] and "database_path" in db_match["connection_details"]:
                    resolved = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                        db_match["connection_details"]["database_path"]
                    )
                    if os.path.exists(resolved):
                        db_path = resolved
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

    def _get_data_samples(self, meta: Dict[str, Any]) -> str:
        """Fetch a small 3-row sample of the tables in markdown format to guide code/SQL structure."""
        samples = []
        
        # 1. Resolve files
        file_mappings = {}
        if meta.get("file_mappings"):
            file_mappings = dict(meta.get("file_mappings"))
        elif meta.get("type") == "file" and meta.get("file_path"):
            file_mappings = {meta["alias"]: meta["file_path"]}
            
        # 2. Resolve database sources
        db_sources_list = []
        if meta.get("db_sources"):
            db_sources_list = meta.get("db_sources")
        elif meta.get("type") == "database":
            db_sources_list = [meta]
            
        # Try to read samples from files
        for name, fpath in file_mappings.items():
            try:
                if fpath and os.path.exists(fpath):
                    if fpath.endswith('.csv'):
                        df = pd.read_csv(fpath, nrows=3)
                    else:
                        df = pd.read_excel(fpath, nrows=3)
                    samples.append(f"### Table '{name}' Sample (First 3 rows):\n{df.to_markdown(index=False)}")
            except Exception:
                pass
                
        # Try to read samples from DB sources (if no files loaded yet)
        if not samples and db_sources_list:
            from app.database.connectors import execute_safe_sql
            for db in db_sources_list:
                db_id = db["id"]
                db_type = db.get("db_type", "sqlite")
                schema = db.get("schema", {})
                for table_name in schema.keys():
                    if not table_name:
                        continue
                    if db_type in ("mysql", "mariadb"):
                        safe_table = f"`{table_name}`"
                    else:
                        safe_table = f"\"{table_name}\""
                    sql = f"SELECT * FROM {safe_table} LIMIT 3"
                    try:
                        res = execute_safe_sql(db_type, db.get("connection_details", {}), sql)
                        columns = res.get("columns", [])
                        rows = res.get("rows", [])
                        if columns and rows:
                            df = pd.DataFrame(rows, columns=columns)
                            samples.append(f"### Table '{db_id}__{table_name}' Sample (First 3 rows):\n{df.to_markdown(index=False)}")
                    except Exception:
                        pass
                        
        if samples:
            return "#### Actual Data Samples:\n" + "\n\n".join(samples)
        return ""

    async def _generate_sql_llm(self, question: str, meta: Dict[str, Any], examples: List[Dict[str, Any]]) -> str:
        samples_desc = self._get_data_samples(meta)
        semantic_desc = self._build_semantic_context(meta.get("id") or meta.get("alias"))
        prompt = prompts.build_sql_generation_prompt(question, meta, examples, samples_desc, semantic_desc)
        return await self._call_deepseek(prompt)

    async def _generate_duckdb_sql_llm(self, question: str, meta: Dict[str, Any], examples: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> str:
        samples_desc = self._get_data_samples(meta)
        semantic_desc = self._build_semantic_context(meta.get("id") or meta.get("alias"))
        prompt = prompts.build_duckdb_sql_generation_prompt(question, meta, examples, relationships, samples_desc, semantic_desc)
        return await self._call_deepseek(prompt)

    async def _llm_correct_duckdb(self, question: str, code: str, error: str, schema: Dict[str, Any]) -> str:
        prompt = prompts.build_duckdb_correction_prompt(question, code, error, schema)
        return await self._call_deepseek(prompt)

    async def _generate_pandas_llm(self, question: str, meta: Dict[str, Any], examples: List[Dict[str, Any]], relationships: List[Dict[str, Any]], is_ml: bool = False) -> str:
        samples_desc = self._get_data_samples(meta)
        prompt = prompts.build_pandas_generation_prompt(question, meta, examples, relationships, is_ml=is_ml, samples_desc=samples_desc)
        return await self._call_deepseek(prompt)

    async def _llm_correct_sql(self, question: str, code: str, error: str, schema: Dict[str, Any]) -> str:
        prompt = prompts.build_sql_correction_prompt(question, code, error, schema)
        return await self._call_deepseek(prompt)

    async def _llm_correct_python(self, question: str, code: str, error: str, schema: Dict[str, Any]) -> str:
        prompt = prompts.build_python_correction_prompt(question, code, error, schema)
        return await self._call_deepseek(prompt)

    async def _stream_analyst(self, prompt: str, on_delta=None) -> str:
        """OpenAI-uyumlu streaming analiz yanıtı. Token parçalarını on_delta ile
        canlı iletir; stream desteklenmezse/hata olursa non-stream'e düşer."""
        if not self.api_key:
            return ""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a senior Business Intelligence consultant. Output rich markdown."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "stream": True,
        }
        collected: list = []
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST", f"{self.base_url}/chat/completions",
                    headers=headers, json=data, timeout=120.0,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        payload = line[len("data:"):].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            chunk = json.loads(payload)
                        except Exception:
                            continue
                        choices = chunk.get("choices") or [{}]
                        delta = (choices[0].get("delta") or {}).get("content") or ""
                        if delta:
                            collected.append(delta)
                            if on_delta:
                                result = on_delta(delta)
                                if hasattr(result, "__await__"):
                                    await result
            text = "".join(collected).strip()
            return text if text else await self._call_llm_analyst(prompt)
        except Exception:
            return await self._call_llm_analyst(prompt)

    async def _call_deepseek(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a specialized code generation assistant. Output ONLY valid, runnable code without explanations or markdown formatting."},
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
                {"role": "system", "content": "You are a senior Business Intelligence Analyst and Data Science expert. Write a premium executive summary report interpreting the forecasting results (trends, growth rates, confidence intervals) and providing 3 actionable business recommendations. Output rich markdown in Turkish (or matching the user question's language)."},
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
        prompt = prompts.build_forecast_narrative_prompt(question, df_forecast, time_col, val_col)
        return await self._call_llm_analyst(prompt)

    def _generate_fallback_code(self, question: str, meta: Dict[str, Any], is_sql: bool) -> str:
        q = question.lower()
        alias = meta["alias"]
        schema = meta["schema"]
        if isinstance(schema, dict) and schema:
            # Check if it's a multi-table database schema (values are lists of columns)
            if meta.get("type") == "database" or all(isinstance(v, list) for v in schema.values()):
                first_table = list(schema.keys())[0]
                alias = first_table
                schema = schema[first_table]
            elif all(isinstance(v, dict) for v in schema.values()):
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
                return f"SELECT {c_text}, COUNT(*) as kayit_sayisi FROM {table_name} GROUP BY {c_text} ORDER BY kayit_sayisi DESC"
            elif ("en çok" in q or "en cok" in q or "popüler" in q or "populer" in q or "top" in q or "satan" in q or "yüksek" in q or "yuksek" in q) and c_text and c_num:
                limit = 5
                limit_match = re.search(r'\b(\d+)\b', q)
                if limit_match:
                    limit = int(limit_match.group(1))
                return f"SELECT {c_text}, SUM({c_num}) as toplam_deger FROM {table_name} GROUP BY {c_text} ORDER BY toplam_deger DESC LIMIT {limit}"
            elif ("kategori" in q or "grup" in q or "sınıf" in q or "sinif" in q) and c_text and c_num:
                return f"SELECT {c_text}, COUNT(*) as kayit_sayisi, SUM({c_num}) as toplam_deger FROM {table_name} GROUP BY {c_text} ORDER BY toplam_deger DESC"
            elif ("trend" in q or "tarih" in q or "zaman" in q or "aylık" in q or "aylik" in q or "yıllık" in q or "yillik" in q) and c_text and c_num:
                c_date = find_col_sql(["tarih", "date", "ay", "yil", "yıl", "month", "year", "time"]) or c_text
                return f"SELECT {c_date}, SUM({c_num}) as toplam_deger FROM {table_name} GROUP BY {c_date} ORDER BY {c_date} ASC"
            
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
                code += f"fig = px.bar(result, x='{c_prod}', y='{c_rev}', title='Ürün Bazında Toplam Değer (En Yüksek 10)', labels={{'{c_prod}': 'Ürün', '{c_rev}': 'Toplam Değer'}})\n"
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
                # Suppress chart for listing/sample queries (LIMIT without aggregation, RANDOM, ORDER BY RANDOM, etc.)
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
        return prompts.build_agent_summary(question, result, is_sql)

