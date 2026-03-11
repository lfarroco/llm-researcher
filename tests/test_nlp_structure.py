"""Tests for NLP module scaffolding."""

from app.nlp import EntityExtractor, RelationExtractor, Summarizer, TopicModeler


def test_nlp_modules_importable():
    """NLP module exports should be importable."""
    assert EntityExtractor is not None
    assert RelationExtractor is not None
    assert Summarizer is not None
    assert TopicModeler is not None


def test_nlp_scaffold_methods_are_safe_defaults():
    """Scaffold implementations should execute without errors."""
    assert EntityExtractor().extract("test") == []
    assert RelationExtractor().extract("test") == []
    assert Summarizer().summarize("hello") == "hello"
    assert TopicModeler().extract_topics(["doc"]) == []
