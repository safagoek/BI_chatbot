import json
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

def _get_embedding_model():
    """Import the shared embedding model from rag.py"""
    try:
        from app.agent.rag import _get_embedding_model as get_rag_model
        return get_rag_model()
    except Exception as e:
        logger.warning(f"Could not load embedding model for semantic cache: {e}")
        return None

def _vector_cosine_similarity(vec_a: list, vec_b: list) -> float:
    from app.agent.rag import _vector_cosine_similarity as cosine_sim
    return cosine_sim(vec_a, vec_b)

def check_cache(question: str, source_id: str, similarity_threshold: float = 0.95) -> Optional[Tuple[str, str]]:
    """
    Checks if the given question has a highly similar cached answer for the same source.
    Returns (intent, code) if found, else None.
    """
    model = _get_embedding_model()
    if not model:
        return None

    try:
        # Generate query embedding
        query_vector = list(model.embed([question]))[0].tolist()
    except Exception as e:
        logger.warning(f"Semantic Cache vector generation failed: {e}")
        return None

    try:
        from app.database.manager import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT question, intent, code, embedding_json FROM semantic_cache WHERE source_id = ?", (source_id,))
        rows = cursor.fetchall()
        conn.close()

        best_score = 0.0
        best_match = None

        for row in rows:
            if not row["embedding_json"]:
                continue
            
            try:
                item_vector = json.loads(row["embedding_json"])
                score = _vector_cosine_similarity(query_vector, item_vector)
                
                # Check for exact string match first, which guarantees 1.0 similarity practically
                if row["question"].lower().strip() == question.lower().strip():
                    score = 1.0

                if score > best_score:
                    best_score = score
                    best_match = row
            except Exception:
                continue

        if best_match and best_score >= similarity_threshold:
            logger.info(f"[Semantic Cache] HIT: {best_score:.3f} similarity for question: '{question}'")
            return best_match["intent"], best_match["code"]

        return None
    except Exception as e:
        logger.error(f"Semantic cache check error: {e}")
        return None

def add_to_cache(question: str, intent: str, code: str, source_id: str) -> bool:
    """
    Adds a successful query execution to the semantic cache.
    """
    model = _get_embedding_model()
    if not model:
        return False

    try:
        query_vector = list(model.embed([question]))[0].tolist()
    except Exception as e:
        logger.warning(f"Semantic Cache vector generation failed during save: {e}")
        return False

    try:
        from app.database.manager import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO semantic_cache (question, intent, code, source_id, embedding_json)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(question) DO UPDATE SET
            intent = excluded.intent,
            code = excluded.code,
            source_id = excluded.source_id,
            embedding_json = excluded.embedding_json,
            created_at = CURRENT_TIMESTAMP
        """, (
            question.strip(),
            intent,
            code,
            source_id,
            json.dumps(query_vector)
        ))
        conn.commit()
        conn.close()
        logger.info(f"[Semantic Cache] Added to cache: '{question}'")
        return True
    except Exception as e:
        logger.error(f"Semantic cache save error: {e}")
        return False
