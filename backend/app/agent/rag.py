"""
app/agent/rag.py

Self-RAG Katmanı:
1. Retrieve  — TF-IDF + Cosine Similarity ile semantik sorgu arama
2. Validate  — Üretilen kodun şema sütunlarıyla uyumunu kontrol et
3. Execute   — Sandbox'ta çalıştır
4. Correct   — Hata varsa LLM'e gönderip düzelт (max 3 deneme)
"""
import os
import re
import json
import math
import logging
import threading
from typing import List, Dict, Any, Optional, Tuple, Callable

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# 1. TF-IDF Vektör Hesaplama (scikit-learn olmadan saf Python implementasyonu)
# --------------------------------------------------------------------------- #

def turkish_lower(text: str) -> str:
    """Turkish-aware lowercasing to properly map I->ı and İ->i."""
    mapping = {
        'I': 'ı',
        'İ': 'i',
        'Ş': 'ş',
        'Ç': 'ç',
        'Ğ': 'ğ',
        'Ü': 'ü',
        'Ö': 'ö'
    }
    for upper, lower in mapping.items():
        text = text.replace(upper, lower)
    return text.lower()


def _tokenize(text: str) -> List[str]:
    """Tokenize Turkish text: lowercase + split on non-alphanum."""
    text = turkish_lower(text)
    tokens = re.findall(r'\b\w+\b', text)
    return tokens


def _compute_tf(tokens: List[str]) -> Dict[str, float]:
    freq = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    total = len(tokens) if tokens else 1
    return {t: c / total for t, c in freq.items()}


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    common = set(vec_a.keys()) & set(vec_b.keys())
    if not common:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common)
    norm_a = math.sqrt(sum(v**2 for v in vec_a.values()))
    norm_b = math.sqrt(sum(v**2 for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# --------------------------------------------------------------------------- #
# 2. Memory-Backed Semantic Retriever
# --------------------------------------------------------------------------- #

MEMORY_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "query_memory.json"
)

_SEED_EXAMPLES: List[Dict[str, Any]] = []  # No hardcoded seeds — fully dynamic, schema-driven


_memory_cache = None
_memory_lock = threading.RLock()  # Thread-safe bellek erişimi için re-entrant lock


def _load_memory() -> List[Dict[str, Any]]:
    global _memory_cache
    with _memory_lock:
        if _memory_cache is not None:
            return list(_memory_cache)  # Güvenli kopya döndür
        
        try:
            from app.database.manager import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM rag_memory")
            rows = cursor.fetchall()
            
            # Auto-migration from legacy JSON if it exists and DB is empty
            if not rows:
                legacy_data = None
                if os.path.exists(MEMORY_FILE_PATH):
                    try:
                        with open(MEMORY_FILE_PATH, 'r', encoding='utf-8') as f:
                            legacy_data = json.load(f)
                        logger.info("Migrating legacy RAG memory JSON file to SQLite database.")
                    except Exception as ex:
                        logger.warning(f"Could not load legacy RAG memory JSON: {ex}")
                
                # Use legacy data if found, otherwise start with empty memory (no hardcoded seeds)
                initial_data = legacy_data if legacy_data else []
                
                if initial_data:
                    conn.close()
                    _save_memory(initial_data)
                    _memory_cache = list(initial_data)
                else:
                    conn.close()
                    _memory_cache = []
                
                # Try to safely delete the legacy JSON file after successful migration
                if legacy_data and os.path.exists(MEMORY_FILE_PATH):
                    try:
                        os.remove(MEMORY_FILE_PATH)
                        logger.info("Legacy RAG memory JSON file successfully migrated and deleted.")
                    except Exception:
                        pass
                        
                return list(_memory_cache)
    
            memory = []
            for r in rows:
                memory.append({
                    "question": r["question"],
                    "intent": r["intent"],
                    "code": r["code"],
                    "source_id": r["source_id"],
                    "feedback": r["feedback"],
                    "execution_success": bool(r["execution_success"]),
                    "schema_snapshot": json.loads(r["schema_snapshot"]) if r["schema_snapshot"] else {},
                    "embedding": json.loads(r["embedding_json"]) if r["embedding_json"] else None
                })
            conn.close()
            _memory_cache = memory
            return list(_memory_cache)
        except Exception as e:
            logger.error(f"Failed to load RAG memory from SQLite: {e}")
            _memory_cache = list(_SEED_EXAMPLES)
            return list(_memory_cache)


def _save_memory(data: List[Dict[str, Any]]):
    global _memory_cache
    with _memory_lock:
        _memory_cache = list(data)
    try:
        from app.database.manager import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Save memory dynamically (using SQLite UPSERT)
        for item in data:
            cursor.execute("""
            INSERT INTO rag_memory (question, intent, code, source_id, feedback, execution_success, schema_snapshot, embedding_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(question) DO UPDATE SET
                intent = excluded.intent,
                code = excluded.code,
                source_id = excluded.source_id,
                feedback = excluded.feedback,
                execution_success = excluded.execution_success,
                schema_snapshot = excluded.schema_snapshot,
                embedding_json = excluded.embedding_json
            """, (
                item["question"],
                item["intent"],
                item["code"],
                item["source_id"],
                item["feedback"],
                1 if item.get("execution_success", True) else 0,
                json.dumps(item.get("schema_snapshot", {})),
                json.dumps(item.get("embedding")) if item.get("embedding") else None
            ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save RAG memory to SQLite: {e}")


_embedding_model = None

def _get_embedding_model():
    """Lazy initializer for fastembed to avoid overhead if not used or during startup."""
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model
    try:
        from fastembed import TextEmbedding
        logger.info("Initializing fastembed TextEmbedding model...")
        _embedding_model = TextEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        return _embedding_model
    except Exception as e:
        logger.warning(f"Could not initialize fastembed, falling back to TF-IDF: {e}")
        return None


def _vector_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two float vectors without dependencies."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a**2 for a in vec_a))
    norm_b = math.sqrt(sum(b**2 for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve_similar(
    question: str,
    source_id: str,
    active_schema: Optional[Dict[str, Any]] = None,
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """
    Semantic retrieval utilizing dense vector embeddings (via fastembed) if available,
    with a robust TF-IDF cosine similarity fallback.
    Includes Jaccard schema-overlap boosting and intent-keyword matching.
    """
    memory = _load_memory()
    if not memory:
        return []

    # Try fastembed vector search
    model = _get_embedding_model()
    use_vector = (model is not None)
    
    query_vector = None
    query_tf = None
    
    if use_vector:
        try:
            # Generate query embedding (fastembed returns a generator)
            query_vector = list(model.embed([question]))[0].tolist()
        except Exception as e:
            logger.warning(f"Failed to generate query embedding: {e}")
            use_vector = False
            
    if not use_vector:
        query_tf = _compute_tf(_tokenize(question))
    
    # Keyword groups for analytical intents — centralized from intent_keywords.py
    try:
        from app.core.intent_keywords import INTENT_KEYWORD_GROUPS
        _INTENT_KEYWORDS = INTENT_KEYWORD_GROUPS
    except ImportError:
        _INTENT_KEYWORDS = {
            "trend": ["trend", "tarih", "zaman", "ay", "yıl"],
            "top": ["en çok", "top", "limit"],
            "distribution": ["dağılım", "kategori", "pasta"],
        }
    
    # Parse active schema columns
    active_cols = set()
    if active_schema:
        for key, val in active_schema.items():
            if isinstance(val, list):
                active_cols.update(c.lower() for c in val)
            elif isinstance(val, dict):
                active_cols.update(c.lower() for c in val.keys())
            else:
                active_cols.add(str(key).lower())
                
    scored = []
    q_low = question.lower()
    memory_changed = False
    
    for item in memory:
        # Strict session/source isolation:
        # Cross-source memory items are strictly prohibited to prevent schema contamination.
        if item.get("source_id") != source_id:
            continue

        score = 0.0
        
        if use_vector:
            # Retrieve or calculate dense embedding for the cached question
            item_vector = item.get("embedding")
            if not item_vector:
                try:
                    item_vector = list(model.embed([item.get("question", "")]))[0].tolist()
                    item["embedding"] = item_vector
                    memory_changed = True
                except Exception as e:
                    logger.warning(f"Failed to generate item embedding: {e}")
            
            if item_vector and query_vector:
                score = _vector_cosine_similarity(query_vector, item_vector)
        else:
            item_tf = _compute_tf(_tokenize(item.get("question", "")))
            score = _cosine_similarity(query_tf, item_tf)
            
        # Boost positive/successful items
        if item.get("feedback") == "positive":
            score *= 1.3
        if item.get("execution_success", False):
            score *= 1.2
            
        # 1. Jaccard Schema-Overlap Boost
        if active_cols:
            mem_cols = set()
            mem_sch = item.get("schema_snapshot", {})
            if mem_sch:
                for key, val in mem_sch.items():
                    if isinstance(val, list):
                        mem_cols.update(c.lower() for c in val)
                    elif isinstance(val, dict):
                        mem_cols.update(c.lower() for c in val.keys())
                    else:
                        mem_cols.add(str(key).lower())
            
            if mem_cols:
                intersection = active_cols & mem_cols
                union = active_cols | mem_cols
                jaccard = len(intersection) / len(union) if union else 0.0
                score *= (1.0 + jaccard * 0.8)
                
        # 2. Multi-Intent Keyword Boost
        item_q_low = item.get("question", "").lower()
        for intent_grp, keywords in _INTENT_KEYWORDS.items():
            q_match = any(kw in q_low for kw in keywords)
            item_match = any(kw in item_q_low for kw in keywords)
            if q_match and item_match:
                score *= 1.3  # 30% boost for matching intent keywords
                break
            
        if score > 0.05:  # minimum threshold
            item_copy = dict(item)
            item_copy["score"] = score
            scored.append((score, item_copy))
            
    if memory_changed:
        _save_memory(memory)
        
    scored.sort(key=lambda x: x[0], reverse=True)

    # ── Schema Compatibility Filter ──────────────────────────────────────────
    # Discard RAG examples whose code references columns NOT in the active schema.
    # This prevents demo/old-dataset contamination when a new dataset is loaded.
    results = []
    for _, item in scored[:top_k * 2]:  # fetch 2x to have fallback after filtering
        if not active_cols:
            results.append(item)
            continue
        code = item.get("code", "")
        # Extract column names from the code (SQL or Python)
        code_cols = set()
        # Match SQL column references: SELECT col1, col2 or GROUP BY col
        for match in re.finditer(r'\b([a-zA-Z_ğüşöçİĞÜŞÖÇ][a-zA-Z0-9_ğüşöçİĞÜŞÖÇ]*)\b', code):
            col = match.group(1).lower()
            # Skip SQL keywords and common names
            if col in {'select', 'from', 'where', 'group', 'by', 'order', 'limit',
                        'and', 'or', 'as', 'on', 'join', 'left', 'right', 'inner',
                        'count', 'sum', 'avg', 'min', 'max', 'round', 'cast', 'null',
                        'desc', 'asc', 'having', 'union', 'all', 'distinct', 'not',
                        'in', 'is', 'like', 'between', 'case', 'when', 'then', 'else',
                        'end', 'coalesce', 'true', 'false', 'df', 'result', 'fig',
                        'px', 'pd', 'np', 'plt', 'go', 'import', 'def', 'return',
                        'print', 'for', 'if', 'else', 'elif', 'with', 'as', 'in',
                        'not', 'and', 'or', 'is', 'lambda', 'try', 'except', 'pass',
                        'none', 'true', 'false', 'self', 'class', 'yield', 'raise',
                        'from', 'import', 'global', 'nonlocal', 'assert', 'del',
                        'break', 'continue', 'finally', 'while'}:
                continue
            code_cols.add(col)
        # If at least 30% of code columns match active schema, keep the example
        if code_cols:
            overlap = code_cols & active_cols
            match_ratio = len(overlap) / len(code_cols) if code_cols else 0
            if match_ratio >= 0.3 or len(overlap) >= 2:
                results.append(item)
        else:
            results.append(item)  # can't determine, keep it
        if len(results) >= top_k:
            break

    return results[:top_k]


def add_to_memory(
    question: str,
    intent: str,
    code: str,
    source_id: str,
    feedback: str = "neutral",
    execution_success: bool = True,
    schema_snapshot: Optional[Dict[str, List[str]]] = None
):
    """Adds or updates a query in the memory store, calculating its embedding vector if possible."""
    memory = _load_memory()
    
    # Pre-generate embedding if model is loaded
    embedding = None
    model = _get_embedding_model()
    if model is not None:
        try:
            embedding = list(model.embed([question]))[0].tolist()
        except Exception as e:
            logger.warning(f"Could not pre-embed question in add_to_memory: {e}")

    # Update if same question exists
    for item in memory:
        if item.get("question", "").lower().strip() == question.lower().strip():
            item["code"] = code
            item["feedback"] = feedback
            item["execution_success"] = execution_success
            if schema_snapshot:
                item["schema_snapshot"] = schema_snapshot
            if embedding:
                item["embedding"] = embedding
            _save_memory(memory)
            return
    
    new_item = {
        "question": question,
        "intent": intent,
        "code": code,
        "source_id": source_id,
        "feedback": feedback,
        "execution_success": execution_success,
        "schema_snapshot": schema_snapshot or {}
    }
    if embedding:
        new_item["embedding"] = embedding
        
    memory.append(new_item)
    
    # Keep the 150 most relevant (prioritize positive feedback)
    memory.sort(key=lambda x: (
        1 if x.get("feedback") == "positive" else 0,
        1 if x.get("execution_success") else 0
    ), reverse=True)
    
    if len(memory) > 150:
        memory = memory[:150]
    
    _save_memory(memory)


def update_feedback(question: str, feedback: str):
    """Updates the feedback for an existing memory entry (thumbs_up / thumbs_down)."""
    memory = _load_memory()
    for item in memory:
        if item.get("question", "").lower().strip() == question.lower().strip():
            item["feedback"] = feedback
            _save_memory(memory)
            return


# --------------------------------------------------------------------------- #
# 3. Schema Validator
# --------------------------------------------------------------------------- #

def validate_columns_in_schema(code: str, schema: Dict[str, List[str]]) -> Tuple[bool, List[str]]:
    """
    Basic heuristic: checks if column names referenced in the code
    actually exist in the schema. Returns (is_valid, list_of_unknown_cols).
    """
    if not schema:
        return True, []
    
    all_known_cols = set()
    for cols in schema.values():
        if isinstance(cols, list):
            all_known_cols.update(c.lower() for c in cols)
        elif isinstance(cols, dict):
            all_known_cols.update(c.lower() for c in cols.keys())
    
    # Find string literals in the code (simple regex for quoted strings)
    str_literals = re.findall(r"'([^']+)'|\"([^\"]+)\"", code)
    referenced = set()
    for g1, g2 in str_literals:
        val = (g1 or g2).lower()
        if len(val) > 2 and ' ' not in val:  # likely a column name
            referenced.add(val)
    
    unknown = [col for col in referenced if col not in all_known_cols]
    
    # Filter out obvious non-column strings (like chart titles, etc.)
    unknown = [c for c in unknown if len(c) <= 50 and not any(
        kw in c for kw in ['select', 'from', 'where', 'group', 'order', 'join', 'http', 'px.', 'df.']
    )]
    
    return len(unknown) == 0, unknown


def perform_pre_execution_critique(code: str, schema: Dict[str, Any], intent: str) -> Tuple[bool, Optional[str]]:
    """
    Critically checks the code against schema structure before execution.
    Returns (is_valid, critique_message).
    """
    if not schema:
        return True, None
        
    if intent == "sql_query":
        # Check table references
        known_tables = [t.lower() for t in schema.keys()]
        # Extract tables in SQL from 'FROM table' or 'JOIN table'
        referenced_tables = re.findall(r"\b(?:from|join)\s+([a-zA-Z0-9_]+)", code, re.IGNORECASE)
        for ref_t in referenced_tables:
            if ref_t.lower() not in known_tables and ref_t.lower() not in ["satislar", "musteriler"]:
                return False, f"[Şema Eleştirisi] Kodda kullanılan '{ref_t}' tablosu veritabanı şemasında bulunamadı. Şemadaki tablolar: {', '.join(schema.keys())}"
                
        # Check column references in SQL
        all_known_cols = set()
        for t, cols in schema.items():
            if isinstance(cols, list):
                all_known_cols.update(c.lower() for c in cols)
            elif isinstance(cols, dict):
                all_known_cols.update(c.lower() for c in cols.keys())
                
        # Simple extraction of word tokens in SQL (excluding SQL keywords)
        sql_words = re.findall(r"\b([a-zA-Z0-9_]{3,})\b", code)
        sql_keywords = ["select", "from", "where", "group", "order", "having", "join", "left", "right", "inner", "outer", "on", "as", "with", "by", "limit", "desc", "asc", "count", "sum", "avg", "min", "max", "round", "null", "and", "or", "not", "is", "in", "like"]
        referenced_cols = [w for w in sql_words if w.lower() not in sql_keywords and not w.isdigit()]
        
        # Cross reference columns
        if all_known_cols:
            unknown_cols = []
            for col in referenced_cols:
                if col.lower() not in all_known_cols and col.lower() not in known_tables and col.lower() not in ["satislar", "musteriler", "musteri_id"]:
                    unknown_cols.append(col)
            if unknown_cols:
                return False, f"[Şema Eleştirisi] SQL sorgusunda kullanılan '{', '.join(unknown_cols)}' sütunları şemada bulunamadı. Şemadaki geçerli sütunlar: {', '.join(all_known_cols)}"
                
    else:  # Pandas/File Mode
        all_known_cols = set()
        for t, cols in schema.items():
            if isinstance(cols, list):
                all_known_cols.update(c.lower() for c in cols)
            elif isinstance(cols, dict):
                all_known_cols.update(c.lower() for c in cols.keys())
            else:
                all_known_cols.add(str(t).lower())

        referenced = set()
        df_names = {"df", "data"}
        for t in schema.keys():
            df_names.add(t.lower())

        df_pattern = "|".join(re.escape(name) for name in df_names)

        # 1. Subscript-style: df['column'] or satislar['tarih'] on valid df_names
        subscript_refs = re.findall(rf"\b({df_pattern})\[\s*['\"]([A-Za-z0-9_]+)['\"]\s*\]", code, re.IGNORECASE)
        for _, ref in subscript_refs:
            referenced.add(ref.lower())

        # 2. Attribute-style: df.column_name on valid df_names
        _PANDAS_METHODS = {
            "head", "tail", "info", "describe", "shape", "columns", "index", "dtypes",
            "values", "copy", "reset_index", "set_index", "sort_values", "drop",
            "rename", "fillna", "dropna", "isnull", "notnull", "apply", "map",
            "groupby", "merge", "join", "pivot", "melt", "agg", "aggregate",
            "sum", "mean", "min", "max", "count", "std", "var", "median",
            "corr", "cov", "plot", "to_csv", "to_excel", "select_dtypes",
            "iterrows", "itertuples", "items", "unique", "nunique", "value_counts",
            "str", "dt", "cat", "sparse", "loc", "iloc", "at", "iat",
            "empty", "size", "ndim", "T", "axes",
        }
        attr_refs = re.findall(rf"\b({df_pattern})\.([A-Za-z_]\w*)", code, re.IGNORECASE)
        for _, attr in attr_refs:
            if attr.lower() not in _PANDAS_METHODS and not attr.isdigit():
                referenced.add(attr.lower())

        # 3. groupby or agg parameters if they match known columns
        str_literals = re.findall(r"'([^']+)'|\"([^\"]+)\"", code)
        for g1, g2 in str_literals:
            val = (g1 or g2).lower()
            if val in all_known_cols:
                referenced.add(val)

        if all_known_cols:
            unknown_cols = [c for c in referenced if c not in all_known_cols]
            # Exclude table/df names & common names
            known_tables = [t.lower() for t in schema.keys()]
            unknown_cols = [c for c in unknown_cols if c not in known_tables and c not in ["satislar", "musteriler", "df", "data", "result"]]
            
            if unknown_cols:
                return False, (
                    f"[Şema Eleştirisi] Pandas kodunda kullanılan "
                    f"'{', '.join(unknown_cols)}' sütunları/özellikleri "
                    f"dataframe şemasında yer almıyor. "
                    f"Şemadaki mevcut sütunlar: {', '.join(all_known_cols)}"
                )

    return True, None


# --------------------------------------------------------------------------- #
# 4. Self-Correct Loop
# --------------------------------------------------------------------------- #

async def self_correct_loop(
    question: str,
    initial_code: str,
    schema: Dict[str, Any],
    intent: str,
    execute_fn: Callable,  # async fn(code) -> (success, result_or_error)
    llm_correct_fn: Optional[Callable] = None,  # async fn(question, code, error, schema) -> str
    max_attempts: int = 3,
    ws_callback: Optional[Callable] = None
) -> Tuple[bool, str, Any]:
    """
    Executes code in sandbox with automatic self-correction.
    
    Returns: (success, final_code, result_or_error)
    """
    async def notify(msg: str):
        if ws_callback:
            await ws_callback({"type": "status", "message": msg})
            
    async def update_code(code_str: str):
        if ws_callback:
            await ws_callback({"type": "code", "language": "sql" if intent == "sql_query" else "python", "code": code_str})
    
    current_code = initial_code
    last_error = None
    
    for attempt in range(1, max_attempts + 1):
        # On attempt 1, run pre-execution structural critique
        if attempt == 1:
            is_valid, critique_msg = perform_pre_execution_critique(current_code, schema, intent)
            if not is_valid:
                await notify(f"Yapısal şema doğrulaması başarısız: {critique_msg}")
                if llm_correct_fn:
                    await notify("Şema eleştirisi değerlendiriliyor, kod LLM tarafından düzeltiliyor...")
                    try:
                        corrected = await llm_correct_fn(question, current_code, f"Şema Doğrulama Hatası:\n{critique_msg}", schema)
                        if corrected and corrected.strip():
                            current_code = corrected.strip()
                            await update_code(current_code)
                            await notify("Şema eleştirisi doğrultusunda düzeltilmiş kod üretildi. Sandbox'ta çalıştırılıyor...")
                    except Exception as e:
                        logger.error(f"Pre-execution LLM correction failed: {e}")
        
        if attempt > 1:
            await notify(f"Otomatik düzeltme denemesi {attempt}/{max_attempts}...")
        
        success, result_or_error = await execute_fn(current_code)
        
        if success:
            await notify(f"Kod {'ilk denemede' if attempt == 1 else f'{attempt}. denemede'} başarıyla çalıştırıldı.")
            return True, current_code, result_or_error
        
        last_error = result_or_error
        logger.warning(f"Attempt {attempt} failed: {str(last_error)[:200]}")
        
        if attempt < max_attempts and llm_correct_fn:
            await notify(f"Hata analiz ediliyor, LLM tarafından düzeltme kodu üretiliyor...")
            try:
                corrected = await llm_correct_fn(question, current_code, str(last_error), schema)
                if corrected and corrected.strip():
                    current_code = corrected.strip()
                    await update_code(current_code)
                    await notify(f"Düzeltilmiş kod üretildi, tekrar deneniyor...")
                    continue
            except Exception as e:
                logger.error(f"LLM correction failed on attempt {attempt}: {e}")
                # Try local smart correction if LLM is unreachable or rate-limited
                try:
                    # If last_error is structured with unknown/allowed, attempt fuzzy replacements
                    if isinstance(last_error, dict) and last_error.get('unknown'):
                        import difflib as _difflib
                        corrections_local = {}
                        allowed = [a.lower() for a in last_error.get('allowed', [])]
                        allowed_map = {a.lower(): a for a in last_error.get('allowed', [])}
                        for u in last_error.get('unknown', []):
                            candidates = _difflib.get_close_matches(u, allowed, n=1, cutoff=0.6)
                            if candidates:
                                corrections_local[u] = allowed_map[candidates[0]]
                        if corrections_local:
                            corrected_local = current_code
                            for src, tgt in corrections_local.items():
                                try:
                                    corrected_local = re.sub(rf"\b{re.escape(src)}\b", tgt, corrected_local, flags=re.IGNORECASE)
                                except Exception:
                                    pass
                            current_code = corrected_local
                            await notify("🛠️ LLM erişilemez: yerel otomatik düzeltme uygulandı, tekrar deneniyor...")
                            continue
                except Exception:
                    pass
        
        elif attempt < max_attempts:
            # No LLM correction fn → apply simple rule-based fixes
            current_code = _apply_rule_based_fixes(current_code, str(last_error))
            if current_code != initial_code:
                await notify("🛠️ Kural tabanlı otomatik düzeltme uygulandı, tekrar deneniyor...")
    
    await notify(f"⚠️ {max_attempts} deneme sonunda kod çalıştırılamadı.")
    return False, current_code, last_error


def _apply_rule_based_fixes(code: str, error_msg: str) -> str:
    """Apply simple heuristic fixes based on common errors."""
    fixed = code
    
    # KeyError: 'ColumnName' → try to neutralize with .get()
    key_match = re.search(r"KeyError: ['\"]([^'\"]+)['\"]", error_msg)
    if key_match:
        col = key_match.group(1)
        # Replace df['col'] with df.get(col, None) — simplistic fix
        fixed = fixed.replace(f"['{col}']", f".get('{col}', None)")
        fixed = fixed.replace(f'["{col}"]', f'.get("{col}", None)')
    
    # AttributeError → usually accessing wrong attribute
    if "AttributeError" in error_msg:
        # Try to add .dropna() before groupby
        fixed = fixed.replace(".groupby(", ".dropna().groupby(")

    # If error mentions unknown tables, attempt fuzzy match replacements
    m = re.search(r"Seçili kaynaklarda bulunmayan tablolar sorguda referans edilmiş: \[?([^\]]+)\]?", error_msg)
    if m:
        unknowns = [s.strip().strip('\"\'') for s in m.group(1).split(',')]
        # naive allowed table candidates: try to find similar words in the code's context
        import difflib as _difflib
        # build a small candidate set from words in code (could be table aliases seen earlier)
        tokens = set(re.findall(r"[A-Za-z0-9_]+", code))
        for u in unknowns:
            candidates = _difflib.get_close_matches(u, list(tokens), n=1, cutoff=0.6)
            if candidates:
                try:
                    fixed = re.sub(rf"\b{re.escape(u)}\b", candidates[0], fixed, flags=re.IGNORECASE)
                except Exception:
                    pass
    
    return fixed
