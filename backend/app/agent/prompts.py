"""Prompt-building helpers for SupervisorAgent.

All functions here are pure module-level builders. They contain the exact
prompt texts that were previously inlined in supervisor.py — extracted
character-for-character, no behavior change.
"""
import json
from typing import Dict, Any, List

from app.core.logger import logger


def build_conceptual_prompt(schema_json: str, user_question: str) -> str:
    return f"""You are a senior Business Intelligence and Data Science consultant. Answer the user's conceptual, theoretical, or informational question.
Format your answer professionally, focusing purely on data analytics and data science perspectives.
If the question is related to the dataset schema, connect it directly to the active dataset columns with concrete examples.

Active Dataset Schema:
{schema_json}

User Question:
{user_question}

Instructions:
- Avoid generic conversational introductions or filler text (e.g., "Sure, I can help", "As an AI..."). Start directly with the analysis.
- Output high-quality, rich markdown formatting using bolding, bullet points, tables, and headers.
- Respond in Turkish (or match the language of the user question).

Answer:"""


def build_report_prompt(schema_json: str) -> str:
    return f"""You are an elite enterprise Data Architect and BI Analyst. Compile a comprehensive Executive Summary and Analytical Roadmap Report about the active database source.

Active Source Schema:
{schema_json}

Instructions:
- Provide a clear, professional analysis of what queries (SQL, DuckDB) and predictive modeling (ML, forecasting, anomaly detection) are feasible using this specific schema.
- Interpret the column types and suggest practical analytical use-cases.
- Format the response using clean markdown with tables, headers, and bulleted lists.
- Respond in Turkish (or match the language of the user question).

Report:"""


def build_dialect_note(db_type: str) -> str:
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
    return dialect


def build_sql_intent_hint(question: str) -> str:
    q_low = question.lower()
    is_listing = any(kw in q_low for kw in ["göster", "listele", "getir", "örnek", "sample", "random", "rastgele", "ilk", "first", "son", "last"])
    is_agg = any(kw in q_low for kw in ["toplam", "sum", "ortalama", "avg", "say", "count", "max", "min", "en çok", "en az", "grupla", "group"])

    if is_listing and not is_agg:
        return "Not: Bu bir listeleme/örnek sorgusudur. LIMIT kullan (genellikle 5-20 arası), GROUP BY veya aggregation KULLANMA."
    elif is_agg:
        return "Not: Bu bir analiz/aggregasyon sorgusudur. SUM/COUNT/AVG/MAX/MIN ve GROUP BY kullan."
    else:
        return "Not: Sorguyu amaca uygun yaz; gerekirse LIMIT ekle."


def filter_rag_examples(examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Dynamically scale RAG examples based on similarity score
    filtered_examples = [e for e in examples if e.get("score", 1.0) >= 0.25]
    if not filtered_examples and examples:
        filtered_examples = [examples[0]]
    return filtered_examples


def build_sql_generation_prompt(
    question: str,
    meta: Dict[str, Any],
    examples: List[Dict[str, Any]],
    samples_desc: str,
    semantic_desc: str,
) -> str:
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

    # Expose a 3-row sample of tables dynamically to help LLM structure queries correctly
    if samples_desc:
        schema_str += "\n\n" + samples_desc

    db_type = meta.get("db_type", "sqlite")
    dialect = build_dialect_note(db_type)

    intent_hint = build_sql_intent_hint(question)

    filtered_examples = filter_rag_examples(examples)
    examples_str = "\n".join([f"S: {e['question']}\nSQL: {e['code']}" for e in filtered_examples[:3]]) or "Yok"

    prompt = f"""You are a senior SQL Expert. Write a read-only SQL query based on the following schema.{dialect}

## Schema
{schema_str}
{semantic_desc}

## Examples
{examples_str}

## Instructions & Rules:
1. Use SELECT or WITH only. DML/DDL (UPDATE/DELETE/INSERT/DROP/ALTER) is strictly forbidden.
2. Never add semicolons or wrap output in code blocks (e.g. ```sql). Return raw query string.
3. {intent_hint}
4. Superlatives Rule: Always order by the metric (ORDER BY DESC for "highest", "most", "largest", "maximum"; ORDER BY ASC for "lowest", "least", "smallest", "minimum") before using LIMIT.
5. Limit Rule: If the question implies a singular item (e.g., "highest revenue product"), always use LIMIT 1. For lists or plurals, use the specified limit or a reasonable default (e.g., 5 or 10). Never use LIMIT without ORDER BY!
6. CRITICAL RULE: The ONLY valid table names are the ones listed in the Schema section above (e.g., {', '.join(schema.keys())[:50]}...). DO NOT use the database connection name or context name as a table name!
7. CRITICAL: Examples above are for STYLE REFERENCE ONLY. Use ONLY column names from the Schema section. NEVER copy column names from examples if they don't exist in the Schema.
8. Output: SADECE/ONLY runnable executable SQL. No explanations.

Question: {question}
SQL:"""
    return prompt


def build_relationship_desc_duckdb(relationships: List[Dict[str, Any]], source_map: Dict[str, List[str]]) -> str:
    rel_lines = []
    for r in relationships:
        ls, rs = r.get("leftSourceId", ""), r.get("rightSourceId", "")
        lc, rc = r.get("leftColumn", ""), r.get("rightColumn", "")
        ldf = f"{ls}__{lc.split('.')[0]}" if "." in lc else (source_map.get(ls, [""])[0] if source_map.get(ls) else ls)
        rdf = f"{rs}__{rc.split('.')[0]}" if "." in rc else (source_map.get(rs, [""])[0] if source_map.get(rs) else rs)
        rel_lines.append(f"  {ldf}.{lc} = {rdf}.{rc} ({r.get('joinType', 'auto')} join)")
    return "\n".join(rel_lines)


def build_relationship_desc_pandas(relationships: List[Dict[str, Any]], source_map: Dict[str, List[str]]) -> str:
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
    return "\n".join(rel_lines)


def build_duckdb_intent_hint(question: str) -> str:
    q_low = question.lower()
    is_listing = any(kw in q_low for kw in ["göster", "listele", "getir", "örnek", "sample", "random", "rastgele", "ilk", "first", "son", "last", "tüm", "all"])
    is_agg = any(kw in q_low for kw in ["toplam", "sum", "ortalama", "avg", "say", "count", "max", "min", "en çok", "en az", "grupla", "group", "däğilşim", "dağılım"])

    if is_listing and not is_agg:
        intent_hint = "Listeleme/örnek sorgusu — LIMIT kullan (5-20 satır), GROUP BY / aggregation KULLANMA."
        if "random" in q_low or "rastgele" in q_low:
            intent_hint += " Rastgele sıralıyor ise ORDER BY RANDOM() kullan."
    elif is_agg:
        intent_hint = "Analiz/aggregasyon sorgusu — GROUP BY, SUM/COUNT/AVG/MAX/MIN kullan. LIMIT gerekmedikçe ekleme."
    else:
        intent_hint = "Uygun bir SELECT sorgusu yaz; ihtiyaç duyulursa LIMIT ekle."
    return intent_hint


def build_duckdb_sql_generation_prompt(
    question: str,
    meta: Dict[str, Any],
    examples: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    samples_desc: str,
    semantic_desc: str,
) -> str:
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

    # Expose a 3-row sample of tables dynamically to help LLM structure queries correctly
    if samples_desc:
        schema_str += "\n\n" + samples_desc

    # Relationships
    rel_desc = "Yok"
    if relationships:
        source_map = meta.get("source_map", {})
        rel_desc = build_relationship_desc_duckdb(relationships, source_map)

    filtered_examples = filter_rag_examples(examples)
    examples_str = "\n".join([f"S: {e['question']}\nSQL: {e['code']}" for e in filtered_examples[:3]]) or "Yok"

    # Intent-aware hint
    intent_hint = build_duckdb_intent_hint(question)

    prompt = f"""You are a senior DuckDB SQL Expert. Write a read-only DuckDB SQL query based on the following tables and schema.

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
4. Superlatives Rule: Always order by the metric (ORDER BY DESC for "highest", "most", "largest", "maximum"; ORDER BY ASC for "lowest", "least", "smallest", "minimum") before using LIMIT.
5. Limit Rule: If the question implies a singular item (e.g., "highest revenue product"), always use LIMIT 1. For lists or plurals, use the specified limit or a reasonable default (e.g., 5 or 10). Never use LIMIT without ORDER BY!
6. CRITICAL: Use ONLY table and column names from the Schema section above. Examples are for STYLE REFERENCE ONLY — never copy column names from examples.
7. Output: SADECE/ONLY runnable executable DuckDB SQL. No explanations.

Question: {question}
SQL:"""
    return prompt


def build_pandas_generation_prompt(
    question: str,
    meta: Dict[str, Any],
    examples: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    is_ml: bool = False,
    samples_desc: str = "",
) -> str:
    alias = meta["alias"]

    filtered_examples = filter_rag_examples(examples)
    examples_desc = "\n".join([f"Soru: {e['question']}\nPython Kodu:\n{e['code']}" for e in filtered_examples])

    # Dinamik olarak schema'daki tablo isimlerini Sandbox DF isimleriyle eşleştir
    schema_dict = {}
    if meta.get("type") == "database":
        for k, v in meta.get("schema", {}).items():
            schema_dict[f"{meta['id']}__{k}"] = v
        dataset_names = list(schema_dict.keys())
    else:
        schema_dict = meta.get("schema", {})
        if meta.get("type") == "duckdb" or meta.get("file_mappings"):
            dataset_names = list(meta.get("file_mappings", {}).keys())
        else:
            dataset_names = [alias]

    schema_desc = json.dumps(schema_dict, ensure_ascii=False)

    # Expose a 3-row sample of tables dynamically to help LLM structure code correctly
    if samples_desc:
        schema_desc += "\n\n" + samples_desc

    rel_desc = "yok"
    if relationships:
        source_map = meta.get("source_map", {})
        rel_desc = build_relationship_desc_pandas(relationships, source_map)

    if is_ml:
        prompt = f"""You are a world-class Machine Learning Engineer & Data Scientist (PredictiveAnalyticsAgent).
Write a secure Python script using Pandas, Plotly, and scikit-learn (or numpy/statsmodels) to perform actual predictive modeling, forecasting, clustering, or advanced regression analysis as requested by the user.

### Dataset Details:
- Active DataFrames: {', '.join(dataset_names)}
- Columns & Types: {schema_desc}
- Relationships:
{rel_desc}

### Examples:
{examples_desc}

### Rules for Python Generation (ML Mode):
0. **CRITICAL — SCHEMA FIRST:** Examples above are for STYLE REFERENCE ONLY. Use ONLY column names from the "Columns & Types" section. NEVER copy column names from examples if they don't exist in the active schema.
1. Data Preprocessing & Security:
   - Handle date columns correctly: convert to datetime (`pd.to_datetime`), sort chronological, and aggregate if doing time series.
   - Impute missing values safely using median/mean or fillna(0) to prevent fit errors.
   - **CRITICAL RULE:** The variable(s) {dataset_names} ALREADY EXIST in the global environment as pandas DataFrames containing the real data! DO NOT mock, recreate, or initialize them. NEVER write `pd.DataFrame(columns=...)`. Start your code directly by referencing `{dataset_names[0]}` or `df = {dataset_names[0]}.copy()`.
   - Do NOT try to read or write files (e.g. no `pd.read_csv`, `to_csv`). Use the preloaded DataFrames directly.
   - Forbid network access, system commands, print() calls, and imports like `os`, `sys`, `subprocess`.

2. Predictive & ML Modeling:
   - Time Series/Forecasting: Aggregate data to daily/weekly/monthly level. Create a sequential index (e.g., days since start) for training models like LinearRegression or Ridge. Forecast future steps (e.g. next 30 days), generate future dates, and calculate metrics like R² score or MSE.
   - Customer Segmentation/Clustering: Clean numerical columns, scale them (e.g. `X_scaled = (X - X.min()) / (X.max() - X.min() + 1e-9)`), fit a KMeans model. Add cluster labels.
   - Anomaly Detection: Fit an `IsolationForest` or use statistical Z-Score threshold. Tag outlier points.

3. Standardized Output Structure:
   - Assign the final prediction table/records or segment lists to the variable `result` (a list of dictionaries, a DataFrame, or a dictionary containing a list of records under a key like `'forecast_table'` or `'predictions'`, and metrics under other keys).
   - Example:
     ```python
     result = {{
         'forecast_table': forecast_df.to_dict(orient='records'),
         'model_r2': r2_score_value,
         'mean_squared_error': mse_value
     }}
     ```
   - Always calculate and include performance metrics (like R², Silhouette Score, or Outlier Count) in the `result` dictionary.

4. Premium Plotly Visualization (Assign to `fig`):
   - Plot historical data points along with fitted regression/forecast lines or cluster groups.
   - Apply these styling rules:
     - Dark background: `fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")`
     - Typography: Use "Inter, sans-serif" font. Font color `#8b949e`.
     - Title: `fig.update_layout(title=dict(text="Descriptive Title", font=dict(family="Inter, sans-serif", size=13, color="#e6edf3")))`
     - Gridlines: Grid color `#21262d`.
     - Margins: `fig.update_layout(margin=dict(t=40, r=10, l=40, b=40))`
     - Color Palette: Actual/Historical: `#58a6ff` (Blue) or `#7c3aed` (Purple). Forecast/Future: `#10b981` (Neon Green). Anomalies: `#ef4444` (Bright Red) with size=10 markers.

User Question: {question}
Python Code:"""
    else:
        prompt = f"""You are a world-class Data Scientist and Visualization expert (VisualizerAgent).
Write a secure Python script utilizing Pandas and Plotly to analyze the active dataset and produce a stunning dark-theme chart.

### Dataset Details:
- Active DataFrames: {', '.join(dataset_names)}
- Columns & Types: {schema_desc}
- Relationships:
{rel_desc}

### Examples:
{examples_desc}

### Rules for Python Generation (VisualizerAgent):
0. **CRITICAL — SCHEMA FIRST:** Examples above are for STYLE REFERENCE ONLY. Use ONLY column names from the "Columns & Types" section. NEVER copy column names from examples if they don't exist in the active schema.
1. Assign the final DataFrame, Series, or summary to the variable `result` (e.g., `result = df.groupby(...)`).
2. If visualization is requested, assign a Plotly Figure object to the variable `fig` (e.g., `fig = px.bar(...)`).
3. Apply this mandatory premium dark styling to the Plotly figure:
   - Template: `fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")`
   - Font & Title: `fig.update_layout(title=dict(text="Chart Title", font=dict(family="Inter, sans-serif", size=13, color="#e6edf3")), font=dict(family="Inter, sans-serif", color="#8b949e"))`
   - Gridlines: `fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="#21262d")` and `fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="#21262d")`
   - Margins: `fig.update_layout(margin=dict(t=40, r=10, l=40, b=40))`
4. **CRITICAL RULE:** The variable(s) {dataset_names} ALREADY EXIST in the global environment! DO NOT mock, recreate, or initialize them. NEVER write `pd.DataFrame(columns=...)`. Start your code directly by referencing `{dataset_names[0]}`. Never read files (No `pd.read_csv`).
5. If multiple DataFrames, join/merge them using Pandas. Prefer active relationships.
6. Strictly forbid network access, file writing, print() calls, and imports like os, sys, subprocess.
7. Output: SADECE/ONLY valid runnable Python code without markdown blocks.

User Question: {question}
Python Code:"""

    return prompt


def build_duckdb_correction_prompt(question: str, code: str, error: str, schema: Dict[str, Any]) -> str:
    schema_desc = json.dumps(schema, indent=2)
    prompt = f"""You are an elite enterprise DuckDB SQL Error Correction expert.
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
4. Output: SADECE/ONLY valid corrected runnable DuckDB SQL. No explanation.

Corrected SQL query:"""
    return prompt


def build_sql_correction_prompt(question: str, code: str, error: str, schema: Dict[str, Any]) -> str:
    schema_desc = json.dumps(schema, indent=2)
    prompt = f"""You are an elite enterprise SQL Error Correction expert.
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
4. Output: SADECE/ONLY valid corrected runnable SQL. No explanation.

Corrected SQL query:"""
    return prompt


def build_python_correction_prompt(question: str, code: str, error: str, schema: Dict[str, Any]) -> str:
    schema_desc = json.dumps(schema, indent=2)
    prompt = f"""You are an elite Python Data Science Debugging expert.
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
5. Output: SADECE/ONLY valid corrected runnable Python code. No explanation.

Corrected Python Code:"""
    return prompt


def build_forecast_narrative_prompt(question: str, df_forecast, time_col: str, val_col: str) -> str:
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
    return prompt


def build_agent_summary(question: str, result: Dict[str, Any], is_sql: bool) -> str:
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
        except Exception as _e:
            logger.debug(f"_generate_agent_summary numeric summary skipped: {_e}")

    if "Durum" in cols:
        try:
            durum_idx = cols.index("Durum")
            anom_count = sum(1 for r in rows if r[durum_idx] == "Anomali")
            summary += f"🚨 Yapay zekâ analizörümüz veri setinde **{anom_count} adet anomali (aykırı değer)** tespit etti! Aykırılıklar grafikte parlak kırmızı noktalarla işaretlenmiştir.\n\n"
        except Exception as _e:
            logger.debug(f"_generate_agent_summary anomaly count skipped: {_e}")
    elif "Değişken" in cols:
        summary += "🔗 Sayısal sütunlar arasındaki Pearson korelasyon katsayıları hesaplanmıştır. İlişkiler interaktif bir Heatmap grafiği ile görselleştirilmiştir.\n\n"

    metrics = result.get("metrics")
    if metrics:
        summary += "\n📈 **Yapay Zeka / Tahminleyici Model Metrikleri:**\n"
        for k, v in metrics.items():
            if isinstance(v, float):
                summary += f"- **{k}**: {v:.4f}\n"
            else:
                summary += f"- **{k}**: {v}\n"
        summary += "\n"

    if has_viz:
        summary += "✨ Veriyi daha iyi anlamanız için bir **görselleştirme grafiği** oluşturulup panelinize eklendi.\n"

    if is_listing_q and not has_viz:
        summary += "Tabloyu filtrelebilir, Excel veya CSV olarak dışa aktarabilirsiniz."
    else:
        summary += "\nSonuçları yandaki etkileşimli tablodan veya grafik sekmesinden inceleyebilir, Excel ya da PDF olarak raporlayabilirsiniz."
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# /help ve /explain — iki yönlendirme yolunun (Supervisor / LangGraph) paylaştığı
# tek doğruluk kaynağı. Komut listesi SLASH_COMMAND_TABLE ile senkron tutulur.
# ─────────────────────────────────────────────────────────────────────────────

HELP_COMMANDS = [
    ("/graph", "Etkileşimli Plotly grafiği çizer — örn. `/graph aylık satış trendi`"),
    ("/ask", "Soruyu çalıştırıp sonucu metin olarak açıklar — örn. `/ask bu veri kümesinde neler var?`"),
    ("/ml", "Python ML sandbox'ında modelleme/segmentasyon koşturur — örn. `/ml müşteri segmentasyonu`"),
    ("/table", "Sonucu temiz tablo olarak listeler (grafik üretmez) — örn. `/table özet istatistikler`"),
    ("/sqlquery", "DuckDB/veritabanında doğrudan SQL çalıştırır — örn. `/sqlquery SELECT * FROM satislar LIMIT 10`"),
    ("/pythonscript", "Özel Python/Pandas betiği çalıştırır — örn. `/pythonscript df.describe()`"),
    ("/explain", "Aktif veri kümesinin şemasını ve potansiyel analizleri açıklar — örn. `/explain`"),
    ("/forecast", "Zaman serisi tahmini ve trend projeksiyonu yapar — örn. `/forecast aylık satış`"),
    ("/clean", "Eksik veri, tekrar ve aykırı değer analizi yapar — örn. `/clean`"),
    ("/pivot", "Dinamik pivot analizi (index × kolon × değer) — örn. `/pivot bölge x ürün x satış`"),
    ("/corr", "Sayısal kolonlar arası korelasyon matrisi üretir — örn. `/corr`"),
    ("/help", "Bu kullanım rehberini gösterir"),
]


def build_help_text() -> str:
    """`/help` komutunun yanıtı — komut tablosuyla senkron tek kaynak."""
    lines = ["### 📖 Kullanım Rehberi", "", "Slash komutları analiz rotasını doğrudan belirler:"]
    for cmd, desc in HELP_COMMANDS:
        lines.append(f"- **`{cmd}`** — {desc}")
    lines += [
        "",
        "**İpuçları:**",
        "- Komut sonrası sorununuzu normal cümleyle yazabilirsiniz (örn. `/forecast önümüzdeki çeyrek ciro`).",
        "- Kümeleme sayısını soruda belirtebilirsiniz: `müşterileri 5 kümeye ayır`.",
        "- Birden fazla kaynak seçip hibrit JOIN yapabilirsiniz.",
    ]
    return "\n".join(lines)


def build_explain_prompt(schema_json: str, samples_desc: str = "") -> str:
    """`/explain` komutu — şema + veri örnekleriyle zenginleştirilmiş açıklama.
    Her iki yönlendirme yolu da bunu kullanır."""
    samples_block = f"\n\nÖrnek Veriler:\n{samples_desc}" if samples_desc else ""
    return f"""You are a senior Business Intelligence consultant. Explain the ACTIVE dataset to the user in Turkish.
Cover:
1. Tables and their columns (with inferred meaning/business context).
2. Data types and notable observations (categorical vs numeric, likely date columns).
3. Which analyses this dataset is suitable for (concrete example questions the user could ask).

Format with rich markdown (headers, bullets, a compact table for the schema).
Do NOT invent columns that are not in the schema.

Active Dataset Schema:
{schema_json}{samples_block}

Explanation:"""
