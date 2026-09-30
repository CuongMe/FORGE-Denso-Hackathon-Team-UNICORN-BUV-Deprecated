from app.query_cache import build_cache_key


def test_cache_key_changes_when_prompt_or_corpus_changes():
    first = build_cache_key("What is torque?", None, "corpus-1", "prompt-1", "rag")

    assert first == build_cache_key("What is torque?", None, "corpus-1", "prompt-1", "rag")
    assert first != build_cache_key("What is torque?", None, "corpus-2", "prompt-1", "rag")
    assert first != build_cache_key("What is torque?", None, "corpus-1", "prompt-2", "rag")
