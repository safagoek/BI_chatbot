import os
import json
import logging
import re
from typing import Dict, Any, List, Optional, TypedDict
import pandas as pd
from langgraph.graph import StateGraph, END

from app.agent.supervisor import SupervisorAgent
from app.agent.semantic_cache import check_cache, add_to_cache
from app.agent.graph_rag import build_schema_knowledge_graph
from app.database.connectors import discover_relationships
from app.core.sql_sanitizer import sanitize_and_validate_sql
from app.core.duckdb_engine import execute_duckdb_query
from app.agent.rag import retrieve_similar, add_to_memory

from app.core.intent_keywords import (
    FORECAST_KEYWORDS, ANOMALY_KEYWORDS,
    CORRELATION_KEYWORDS, CLUSTERING_KEYWORDS, LISTING_KEYWORDS
)

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    question: str
    active_source_id: str
    source_ids: List[str]
    relationships: List[Dict[str, Any]]
    ws_callback: Any
    
    source_meta: Dict[str, Any]
    intent: str
    is_sql: bool
    is_ml: bool
    
    kg_context: str
    rag_examples: List[Dict[str, Any]]
    
    generated_code: str
    code_language: str
    final_response: str
    
    data: Optional[Dict[str, Any]]
    visualization: Optional[Dict[str, Any]]
    
    error: Optional[str]
    retries: int
    success: bool
    
    use_cache: bool
    bypass_execution: bool

class GraphSupervisorAgent(SupervisorAgent):
    """
    Modern LangGraph orchestrator fully compatible with SupervisorAgent features.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        super().__init__(api_key, base_url, model)
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("router", self.node_router)
        workflow.add_node("cache_check", self.node_cache_check)
        workflow.add_node("coder", self.node_coder)
        workflow.add_node("executor", self.node_executor)
        workflow.add_node("visualizer", self.node_visualizer)
        workflow.add_node("critique", self.node_critique)

        workflow.set_entry_point("router")

        workflow.add_conditional_edges("router", self.edge_after_router, {"bypass": END, "continue": "cache_check"})
        workflow.add_conditional_edges("cache_check", self.edge_after_cache, {"cached": "executor", "generate": "coder"})
        workflow.add_edge("coder", "executor")
        workflow.add_conditional_edges("executor", self.edge_after_executor, {"success": "visualizer", "error": "critique", "max_retries": END})
        workflow.add_edge("critique", "executor")
        workflow.add_edge("visualizer", END)

        return workflow.compile()

    async def process_query(self, user_question: str, active_source_id: str, source_ids: Optional[List[str]] = None, relationships: Optional[List[Dict[str, Any]]] = None, ws_callback=None) -> Dict[str, Any]:
        initial_state = AgentState(
            question=user_question, active_source_id=active_source_id, source_ids=source_ids or [],
            relationships=relationships or [], ws_callback=ws_callback, source_meta={}, intent="",
            is_sql=False, is_ml=False, kg_context="", rag_examples=[], generated_code="", code_language="",
            final_response="", data=None, visualization=None, error=None, retries=0, success=False,
            use_cache=False, bypass_execution=False
        )

        try:
            final_state = await self.graph.ainvoke(initial_state)
            return {
                "success": final_state["success"], "generated_code": final_state.get("generated_code", ""),
                "data": final_state.get("data"), "visualization": final_state.get("visualization"),
                "final_response": final_state.get("final_response", ""),
                "error": final_state.get("error"),
                "auto_corrections": None
            }
        except Exception as e:
            logger.error(f"Graph execution failed: {e}")
            return {
                "success": False, "error": str(e), "generated_code": "",
                "final_response": f"Graf mimarisi yürütme hatası: {str(e)}", "auto_corrections": None
            }

    async def notify(self, state: AgentState, msg: str):
        if state.get("ws_callback"):
            await state["ws_callback"]({"type": "status", "message": msg})

    async def node_router(self, state: AgentState) -> AgentState:
        await self.notify(state, "[RouterNode] Kullanıcı sorusu ve veri kaynağı şeması analiz ediliyor...")
        resolved = self._resolve_sources(state["active_source_id"], state["source_ids"], bool(state["source_ids"]))
        source_meta = resolved.get("meta")
        if not source_meta:
            state["bypass_execution"] = True
            state["final_response"] = "Veri kaynağı bulunamadı."
            return state
            
        state["source_meta"] = source_meta
        q_low = state["question"].lower()
        
        # Slash Command Routing
        state["is_ml"] = False
        
        if q_low.startswith("/explain") or q_low.startswith("/konsept"):
            state["intent"] = "conceptual"
            state["bypass_execution"] = True
            
            schema_info = json.dumps(source_meta.get("schema", {}), ensure_ascii=False)
            prompt = f"Sen bir Kıdemli Veri Analistisin. Aşağıdaki veritabanı/veri dosyası şemasını kullanıcıya güzel ve anlaşılır bir dille (Türkçe) açıkla. Hangi tablolar ve kolonlar var, bu veri ne işe yarayabilir özetle.\n\nŞema:\n{schema_info}"
            
            try:
                state["final_response"] = await self._call_deepseek(prompt)
            except Exception as e:
                state["final_response"] = f"### Şema Açıklaması\n\n{schema_info}"
            return state
        elif q_low.startswith("/help"):
            state["intent"] = "help"
            state["bypass_execution"] = True
            state["final_response"] = "### 📖 Kullanım Kılavuzu\n- `/graph`: Görsel çizdirir.\n- `/ask`: Veritabanında arama yapar ve metin olarak açıklar.\n- `/ml`, `/forecast`: Tahmin modelleri çalıştırır.\n- `/table`: Tablo formatında sonuç döndürür.\n- `/explain`: Veri kaynağının şemasını açıklar."
            return state
            
        elif q_low.startswith("/ask"):
            state["intent"] = "ask"
        elif q_low.startswith("/graph"):
            state["intent"] = "graph"
        elif q_low.startswith("/table") or q_low.startswith("/sqlquery"):
            state["intent"] = "table"
        elif any(q_low.startswith(cmd) for cmd in ["/ml", "/forecast", "/corr", "/clean", "/pivot", "/pythonscript"]):
            state["intent"] = "ml_task"
            state["is_ml"] = True
        else:
            state["intent"] = "auto"
            state["is_ml"] = any(kw in q_low for kw in FORECAST_KEYWORDS + ANOMALY_KEYWORDS + CLUSTERING_KEYWORDS)

        # Determine if SQL or Pandas
        if state["intent"] == "ml_task":
            state["is_sql"] = False
        else:
            if source_meta["type"] == "database":
                state["is_sql"] = True
            elif source_meta.get("db_sources") and len(source_meta["db_sources"]) > 0:
                state["is_sql"] = True
            else:
                state["is_sql"] = False
            
        if source_meta["type"] == "database" and "connection_details" in source_meta:
            try:
                db_type = source_meta.get("db_type")
                rels = discover_relationships(db_type, source_meta["connection_details"])
                if rels:
                    kg_text = build_schema_knowledge_graph(source_meta["schema"], rels)
                    state["kg_context"] = kg_text
                    await self.notify(state, "[GraphRAG] Veritabanı ilişkileri (Foreign Keys) tespit edildi ve bağlam grafiğine eklendi.")
            except Exception as e:
                logger.warning(f"Graph RAG extraction failed: {e}")
        return state

    def edge_after_router(self, state: AgentState) -> str:
        return "bypass" if state.get("bypass_execution") else "continue"

    async def node_cache_check(self, state: AgentState) -> AgentState:
        source_meta = state["source_meta"]
        rag_key = source_meta.get("rag_key") or state["active_source_id"]
        cached = check_cache(state["question"], rag_key, similarity_threshold=0.95)
        if cached:
            intent, code = cached
            state["intent"] = intent
            state["generated_code"] = code
            state["use_cache"] = True
            await self.notify(state, "[SemanticCache] Semantic Cache Hit! Önceki başarılı kod saniyeler içinde geri getirildi.")
        return state
        
    def edge_after_cache(self, state: AgentState) -> str:
        return "cached" if state.get("use_cache") else "generate"

    async def node_coder(self, state: AgentState) -> AgentState:
        await self.notify(state, f"[CoderNode] LLM ile {'SQL' if state['is_sql'] else 'Pandas/Python'} kod üretimi başlatılıyor...")
        rag_key = state["source_meta"].get("rag_key") or state["active_source_id"]
        
        # Pull RAG examples
        state["rag_examples"] = retrieve_similar(state["question"], rag_key, active_schema=state["source_meta"].get("schema"))
        if state.get("kg_context"):
            state["source_meta"]["_kg_context"] = state["kg_context"]

        try:
            if state["is_sql"]:
                is_direct_db = state["source_meta"].get("type") == "database"
                if is_direct_db:
                    code = await self._generate_sql_llm(state["question"], state["source_meta"], state["rag_examples"])
                else:
                    code = await self._generate_duckdb_sql_llm(state["question"], state["source_meta"], state["rag_examples"], state["relationships"])
            else:
                code = await self._generate_pandas_llm(state["question"], state["source_meta"], state["rag_examples"], state["relationships"], state["is_ml"])
            
            # DuckDB Auto-Correction
            is_direct_db = state["source_meta"].get("type") == "database"
            if state["is_sql"] and not is_direct_db and state["source_meta"].get("db_sources"):
                file_table_names = set()
                if isinstance(state["source_meta"].get("file_mappings"), dict):
                    file_table_names.update([k.lower() for k in state["source_meta"].get("file_mappings").keys()])
                if state["source_meta"].get("alias") and state["source_meta"].get("type") == "file":
                    file_table_names.add(state["source_meta"].get("alias").lower())

                for db in state["source_meta"]["db_sources"]:
                    db_id = db["id"]
                    for table_name in db.get("schema", {}).keys():
                        if table_name.lower() in file_table_names:
                            continue
                        registered_name = f"{db_id}__{table_name}"
                        if registered_name not in code:
                            pattern = re.compile(rf'\b{re.escape(table_name)}\b', re.IGNORECASE)
                            code = pattern.sub(registered_name, code)
                            
            state["generated_code"] = code
        except Exception as e:
            logger.warning(f"Coder LLM fail: {e}")
            state["generated_code"] = self._generate_fallback_code(state["question"], state["source_meta"], state["is_sql"])
            
        if state.get("ws_callback"):
            await state["ws_callback"]({"type": "code", "language": "sql" if state["is_sql"] else "python", "code": state["generated_code"]})
        return state

    async def node_executor(self, state: AgentState) -> AgentState:
        await self.notify(state, "[ExecutorNode] Kod çalıştırılıyor...")
        success = False
        res = None
        
        if state["is_sql"]:
            try:
                is_direct_db = state["source_meta"].get("type") == "database"
                if is_direct_db:
                    db_type = state["source_meta"].get("db_type")
                    safe_sql = sanitize_and_validate_sql(state["generated_code"], db_type=db_type)
                    res = self._execute_local_sql(safe_sql, state["source_meta"])
                else:
                    file_mappings = state["source_meta"].get("file_mappings", {})
                    if not file_mappings and state["source_meta"].get("type") == "file" and state["source_meta"].get("file_path"):
                        file_mappings = {state["source_meta"]["alias"]: state["source_meta"]["file_path"]}
                    db_sources = state["source_meta"].get("db_sources")
                    temp_dir = None
                    if db_sources:
                        db_files, _, temp_dir = self._materialize_db_sources(db_sources, max_rows=50000)
                        file_mappings = {**file_mappings, **db_files}
                    try:
                        res = execute_duckdb_query(state["generated_code"], file_mappings)
                    finally:
                        if temp_dir and os.path.exists(temp_dir):
                            import shutil
                            shutil.rmtree(temp_dir, ignore_errors=True)

                if isinstance(res, dict):
                    if "error" in res:
                        state["error"] = res["error"]
                        success = False
                    elif res.get("success") is False:
                        state["error"] = res.get("error", "SQL Çalıştırma Hatası")
                        success = False
                    else:
                        success = True
                else:
                    state["error"] = "Bilinmeyen SQL hatası"
            except Exception as e:
                state["error"] = str(e)
        else:
            try:
                file_mappings = state["source_meta"].get("file_mappings", {})
                if not file_mappings and state["source_meta"].get("type") == "file" and state["source_meta"].get("file_path"):
                    file_mappings = {state["source_meta"]["alias"]: state["source_meta"]["file_path"]}
                db_sources = state["source_meta"].get("db_sources")
                if not db_sources and state["source_meta"].get("type") == "database":
                    db_sources = [state["source_meta"]]
                temp_dir = None
                if db_sources:
                    db_files, _, temp_dir = self._materialize_db_sources(db_sources, max_rows=50000)
                    file_mappings = {**file_mappings, **db_files}
                try:
                    res = self.sandbox.run_pandas_code(state["generated_code"], file_mappings)
                finally:
                    if temp_dir and os.path.exists(temp_dir):
                        import shutil
                        shutil.rmtree(temp_dir, ignore_errors=True)

                if "error" in res and res["error"]:
                    state["error"] = res["error"]
                else:
                    success = True
            except Exception as e:
                state["error"] = str(e)

        state["success"] = success
        if success:
            state["data"] = res.get("data") if state["is_sql"] else res
            state = self._apply_ml_postprocessing(state)
            
            if not state.get("use_cache"):
                rag_key = state["source_meta"].get("rag_key") or state["active_source_id"]
                add_to_cache(state["question"], state["intent"], state["generated_code"], rag_key)
                add_to_memory(state["question"], state["intent"], state["generated_code"], rag_key, "neutral", True, state["source_meta"].get("schema"))
        
        return state

    def _apply_ml_postprocessing(self, state: AgentState) -> AgentState:
        q_low = state["question"].lower()
        if not state.get("data") or len(state["data"].get("rows", [])) < 2:
            return state

        try:
            if any(kw in q_low for kw in FORECAST_KEYWORDS):
                from app.core.predictor import run_time_series_forecast
                import plotly.express as px
                import plotly.graph_objects as go
                
                df_raw = pd.DataFrame(state["data"]["rows"], columns=state["data"]["columns"])
                for col in df_raw.columns:
                    try: df_raw[col] = pd.to_numeric(df_raw[col])
                    except: pass
                    
                num_cols = df_raw.select_dtypes(include=['number']).columns
                str_cols = df_raw.select_dtypes(include=['object', 'string']).columns
                if len(num_cols) > 0 and len(str_cols) > 0:
                    time_col = None
                    for col in str_cols:
                        if any(kw in col.lower() for kw in ["tarih", "date", "ay", "year", "month", "gün", "day"]):
                            time_col = col; break
                    if not time_col: time_col = str_cols[0]
                    val_col = num_cols[0]
                    
                    df_forecast = run_time_series_forecast(df_raw, time_col, val_col, periods=6)
                    serialized_rows = [[None if pd.isna(item) else item for item in row.values] for _, row in df_forecast.iterrows()]
                    state["data"] = {"columns": list(df_forecast.columns), "index": list(range(len(serialized_rows))), "rows": serialized_rows, "row_count": len(serialized_rows)}
                    
                    fig = px.line(df_forecast, x=time_col, y=val_col, color="Tip", line_dash="Tip", title="Yapay Zekâ Tahmin ve Projeksiyon Modeli", color_discrete_map={"Gerçek": "#7c3aed", "Tahmin": "#a78bfa"})
                    df_pred = df_forecast[df_forecast["Tip"] == "Tahmin"]
                    if len(df_pred) > 0 and "Lower_CI" in df_forecast.columns:
                        x_ci = list(df_pred[time_col]) + list(df_pred[time_col])[::-1]
                        y_ci = list(df_pred["Upper_CI"]) + list(df_pred["Lower_CI"])[::-1]
                        fig.add_trace(go.Scatter(x=x_ci, y=y_ci, fill='toself', fillcolor='rgba(124, 58, 237, 0.12)', line=dict(color='rgba(255,255,255,0)'), hoverinfo="skip", showlegend=True, name="95% Güven Aralığı"))
                    
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    state["visualization"] = json.loads(fig.to_json())

            elif any(kw in q_low for kw in ANOMALY_KEYWORDS):
                from app.core.anomaly import detect_anomalies
                import plotly.express as px
                import plotly.graph_objects as go
                
                df_raw = pd.DataFrame(state["data"]["rows"], columns=state["data"]["columns"])
                for col in df_raw.columns:
                    try: df_raw[col] = pd.to_numeric(df_raw[col])
                    except: pass
                    
                num_cols = df_raw.select_dtypes(include=['number']).columns
                if len(num_cols) > 0:
                    val_col = num_cols[0]
                    df_anom = detect_anomalies(df_raw, val_col, method="isolation_forest")
                    serialized_rows = [[None if pd.isna(item) else item for item in row.values] for _, row in df_anom.iterrows()]
                    state["data"] = {"columns": list(df_anom.columns), "index": list(range(len(serialized_rows))), "rows": serialized_rows, "row_count": len(serialized_rows)}
                    
                    str_cols = df_anom.select_dtypes(include=['object', 'string']).columns
                    x_col = str_cols[0] if len(str_cols) > 0 else state["data"]["columns"][0]
                    is_trend = any("tarih" in col.lower() or "date" in col.lower() for col in str_cols)
                    if is_trend:
                        fig = px.line(df_anom, x=x_col, y=val_col, title=f"Otomatik Anomali Tespiti ({val_col})")
                        fig.update_traces(line=dict(color="#2f81f7", width=2))
                    else:
                        fig = px.bar(df_anom, x=x_col, y=val_col, title=f"Anomali Tespiti ({val_col})")
                        fig.update_traces(marker_color="#2f81f7")
                        
                    df_outliers = df_anom[df_anom['Durum'] == 'Anomali']
                    if not df_outliers.empty:
                        fig.add_trace(go.Scatter(x=df_outliers[x_col], y=df_outliers[val_col], mode='markers', marker=dict(color='#f85149', size=11, symbol='circle', line=dict(color='#ffffff', width=1)), name='Anomali'))
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    state["visualization"] = json.loads(fig.to_json())
                    
            elif any(kw in q_low for kw in CORRELATION_KEYWORDS):
                from app.core.correlation import compute_correlation
                import plotly.express as px
                
                df_raw = pd.DataFrame(state["data"]["rows"], columns=state["data"]["columns"])
                for col in df_raw.columns:
                    try: df_raw[col] = pd.to_numeric(df_raw[col])
                    except: pass
                df_corr = compute_correlation(df_raw)
                if not df_corr.empty:
                    serialized_rows = [[None if pd.isna(item) else item for item in row.values] for _, row in df_corr.iterrows()]
                    state["data"] = {"columns": list(df_corr.columns), "index": list(range(len(serialized_rows))), "rows": serialized_rows, "row_count": len(serialized_rows)}
                    
                    corr_only = df_corr.drop(columns=['Değişken'])
                    fig = px.imshow(corr_only.values.tolist(), x=corr_only.columns.tolist(), y=df_corr['Değişken'].tolist(), text_auto=".2f", aspect="auto", color_continuous_scale="RdBu", zmin=-1, zmax=1, title="Pearson Korelasyon Matrisi")
                    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    state["visualization"] = json.loads(fig.to_json())
                    
            elif any(kw in q_low for kw in CLUSTERING_KEYWORDS):
                from app.core.clustering import run_kmeans_clustering
                import plotly.express as px
                
                df_raw = pd.DataFrame(state["data"]["rows"], columns=state["data"]["columns"])
                n_clusters = 3
                match = re.search(r'(\d+)\s*(küme|segment|cluster)', q_low)
                if match:
                    try: n_clusters = int(match.group(1))
                    except: pass
                df_clustered = run_kmeans_clustering(df_raw, n_clusters=n_clusters)
                serialized_rows = [[None if pd.isna(item) else item for item in row.values] for _, row in df_clustered.iterrows()]
                state["data"] = {"columns": list(df_clustered.columns), "index": list(range(len(serialized_rows))), "rows": serialized_rows, "row_count": len(serialized_rows)}
                
                num_cols = df_clustered.select_dtypes(include=['number']).columns.tolist()
                num_cols = [c for c in num_cols if not any(id_kw in c.lower() for id_kw in ["id", "key", "index", "kod", "no", "pca"])]
                if 'PCA1' in df_clustered.columns and 'PCA2' in df_clustered.columns:
                    fig = px.scatter(df_clustered, x='PCA1', y='PCA2', color='Küme', title="K-Means Kümeleme (PCA Projeksiyonu)")
                elif len(num_cols) >= 2:
                     fig = px.scatter(df_clustered, x=num_cols[0], y=num_cols[1], color='Küme', title="K-Means Kümeleme Analizi")
                else:
                     str_cols = df_clustered.select_dtypes(include=['object', 'string']).columns.tolist()
                     x_col = str_cols[0] if len(str_cols) > 0 else state["data"]["columns"][0]
                     y_col = num_cols[0] if len(num_cols) > 0 else state["data"]["columns"][-1]
                     fig = px.scatter(df_clustered, x=x_col, y=y_col, color='Küme', title="K-Means Kümeleme Analizi")
                     
                fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                state["visualization"] = json.loads(fig.to_json())
                
        except Exception as e:
            logger.warning(f"ML Post-processing error: {e}")
        return state

    def edge_after_executor(self, state: AgentState) -> str:
        if state["success"]:
            return "success"
        if state["retries"] >= 2:
            state["final_response"] = f"Kod çalıştırılamadı.\n\nHata: {state['error']}"
            return "max_retries"
        return "error"

    async def node_critique(self, state: AgentState) -> AgentState:
        state["retries"] += 1
        await self.notify(state, f"[CritiqueNode] Hata tespit edildi. LLM ile otonom düzeltme uygulanıyor (Deneme {state['retries']}/2)...")
        
        schema_str = json.dumps(state["source_meta"].get("schema", {}), ensure_ascii=False)
        prompt = f"""You are a senior data engineer fixing a broken code block.
The following {'SQL' if state['is_sql'] else 'Python/Pandas'} code threw an error during execution.
Please fix the code and return ONLY the corrected code without markdown wrappers. Do not include any explanations.

Active Schema:
{schema_str}

Original Code:
{state['generated_code']}

Error Received:
{state['error']}

Fix the code immediately using the correct table and column names from the schema:"""

        try:
            if self.api_key:
                fixed_code = await self._call_deepseek(prompt)
                state["generated_code"] = fixed_code.replace("```sql", "").replace("```python", "").replace("```", "").strip()
            else:
                state["generated_code"] = f"-- Otomatik düzeltme denemesi\n-- Önceki hata: {state['error']}\n" + state['generated_code']
        except Exception as e:
            logger.error(f"Critique LLM failed: {e}")
            
        if state.get("ws_callback"):
            await state["ws_callback"]({"type": "code", "language": "sql" if state["is_sql"] else "python", "code": state["generated_code"]})
            
        return state

    async def node_visualizer(self, state: AgentState) -> AgentState:
        await self.notify(state, "[VisualizerNode] Sonuçlar derleniyor...")
        
        if state["intent"] == "ask" and state.get("data"):
            try:
                import json
                data_json = json.dumps(state["data"], ensure_ascii=False)[:3000]
                prompt = f"Sen bir Kıdemli Veri Analistisin. Kullanıcının '{state['question']}' sorusuna veri tabanından aşağıdaki sonuçlar döndü. Bu sonuçları kullanarak kullanıcıya açıklayıcı, net ve profesyonel bir metinsel cevap yaz. Tablo olarak değil, okunaklı bir rapor şeklinde yanıtla.\n\nVeri Sonucu:\n{data_json}"
                response = await self._call_deepseek(prompt)
                state["final_response"] = response
            except Exception as e:
                logger.error(f"Ask LLM summarization failed: {e}")
                state["final_response"] = self._generate_agent_summary(state["question"], {"data": state["data"]}, state["is_sql"])
        else:
            state["final_response"] = self._generate_agent_summary(state["question"], {"data": state["data"]}, state["is_sql"])
            
        return state
