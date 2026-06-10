import pytest
from app.agent.rag import (
    retrieve_similar,
    add_to_memory,
    update_feedback,
    perform_pre_execution_critique,
    _tokenize,
    _compute_tf,
    _cosine_similarity
)

def test_tokenize_turkish():
    tokens = _tokenize("Ürün Bazında Toplam SATIŞ Cirosu Nedir?")
    assert "ürün" in tokens
    assert "bazında" in tokens
    assert "satış" in tokens
    assert "cirosu" in tokens

def test_compute_tf():
    tokens = ["elma", "armut", "elma"]
    tf = _compute_tf(tokens)
    assert tf["elma"] == 2.0 / 3.0
    assert tf["armut"] == 1.0 / 3.0

def test_cosine_similarity():
    vec_a = {"elma": 1.0, "armut": 0.5}
    vec_b = {"elma": 0.8, "armut": 0.4}
    sim = _cosine_similarity(vec_a, vec_b)
    assert sim > 0.99  # Identical directions

    vec_c = {"muz": 1.0}
    assert _cosine_similarity(vec_a, vec_c) == 0.0

def test_rag_retrieval_and_feedback():
    # Insert a test entry
    test_question = "Bu test sorusudur"
    test_code = "result = df.describe()"
    test_source = "test_source_id"
    test_schema = {"satislar": ["urun_adi", "ciro"]}

    add_to_memory(
        question=test_question,
        intent="file_analysis",
        code=test_code,
        source_id=test_source,
        feedback="neutral",
        execution_success=True,
        schema_snapshot=test_schema
    )

    # Retrieve similar
    results = retrieve_similar(
        question="test sorusu nedir",
        source_id=test_source,
        active_schema=test_schema,
        top_k=1
    )
    assert len(results) > 0
    assert results[0]["question"] == test_question
    assert results[0]["code"] == test_code

    # Test source isolation (should not retrieve for a different source)
    isolated_results = retrieve_similar(
        question="test sorusu nedir",
        source_id="other_source_id",
        active_schema=test_schema,
        top_k=1
    )
    assert len(isolated_results) == 0

    # Test feedback update
    update_feedback(test_question, "positive")
    
    # Reload and check
    results_updated = retrieve_similar(
        question="test sorusu nedir",
        source_id=test_source,
        active_schema=test_schema,
        top_k=1
    )
    assert results_updated[0]["feedback"] == "positive"
