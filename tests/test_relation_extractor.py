"""Tests for relation extraction heuristics."""

from app.nlp.relation_extractor import RelationExtractor


def test_relation_extractor_extracts_core_relation_types():
    extractor = RelationExtractor()
    relations = extractor.extract(
        "Transformer fine-tuning improves accuracy. "
        "High noise causes instability. "
        "Study A contradicts Study B."
    )

    triples = {(r["subject"].lower(), r["relation"], r["object"].lower()) for r in relations}

    assert ("transformer fine-tuning", "improves", "accuracy") in triples
    assert ("high noise", "causes", "instability") in triples
    assert ("study a", "contradicts", "study b") in triples


def test_relation_extractor_aggregates_mentions_for_same_relation():
    extractor = RelationExtractor()
    relations = extractor.extract_with_mentions([
        {
            "text": "Model X supports hypothesis Y.",
            "mention": "source-1",
        },
        {
            "text": "Model X supports hypothesis Y in replication.",
            "mention": "source-2",
        },
    ])

    supports = [r for r in relations if r["relation"] == "supports"]
    assert len(supports) == 1
    item = supports[0]
    assert item["subject"].lower() == "model x"
    assert item["object"].lower().startswith("hypothesis y")
    assert item["mention_count"] == 2
    assert item["mentions"] == ["source-1", "source-2"]


def test_relation_extractor_keeps_safe_default_for_non_relational_text():
    extractor = RelationExtractor()
    assert extractor.extract("hello world") == []
