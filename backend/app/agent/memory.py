import os
import json
from typing import List, Dict, Any, Optional

MEMORY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "query_memory.json")

def load_memory() -> List[Dict[str, Any]]:
    if not os.path.exists(MEMORY_FILE):
        # No hardcoded seeds — fully dynamic, schema-driven
        return []
        
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def save_memory(memory_data: List[Dict[str, Any]]):
    try:
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(memory_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def add_successful_query(question: str, intent: str, code: str, source_id: str):
    memory = load_memory()
    # Check if identical question already exists
    for m in memory:
        if m["question"].lower() == question.lower():
            m["code"] = code
            save_memory(memory)
            return
            
    memory.append({
        "question": question,
        "intent": intent,
        "code": code,
        "source_id": source_id
    })
    # Keep last 100 queries
    if len(memory) > 100:
        memory = memory[-100:]
    save_memory(memory)

def find_similar_queries(question: str, source_id: str, limit: int = 2) -> List[Dict[str, Any]]:
    """Simple term-overlap semantic search as local RAG."""
    memory = load_memory()
    query_words = set(question.lower().split())
    
    matches = []
    for item in memory:
        if item.get("source_id") != source_id:
            continue
        item_words = set(item["question"].lower().split())
        overlap = len(query_words.intersection(item_words))
        if overlap > 0:
            matches.append((overlap, item))
            
    # Sort by overlap score descending
    matches.sort(key=lambda x: x[0], reverse=True)
    return [item for score, item in matches[:limit]]
