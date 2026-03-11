"""Entity extraction utilities for research text."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


class EntityExtractor:
    """Extract entities relevant to research workflows.

    Uses spaCy when available, with a lightweight fallback when it is not.
    """

    _METHOD_KEYWORDS = {
        "transformer", "cnn", "rnn", "llm", "fine-tuning", "quantization",
        "retrieval-augmented generation", "rag", "prompting", "distillation",
        "reinforcement learning", "bayesian", "regression", "clustering",
    }
    _MATERIAL_KEYWORDS = {
        "dataset", "corpus", "benchmark", "imagenet", "cifar", "mnist",
        "wikipedia", "pubmed", "arxiv", "synthetic data", "knowledge graph",
    }
    _METRIC_KEYWORDS = {
        "accuracy", "precision", "recall", "f1", "auc", "latency", "throughput",
        "loss", "perplexity", "bleu", "rouge", "mae", "rmse", "mse",
    }
    _FINDING_CUES = {
        "improves", "improved", "outperforms", "outperformed", "reduces", "reduced", "increases", "increased", "decreases", "decreased", "correlates",
        "supports", "contradicts", "causes", "associated",
    }

    def __init__(self, model_name: str = "en_core_web_sm"):
        self._nlp = None
        self._ruler_added = False
        try:
            import spacy
            from spacy.language import Language

            try:
                self._nlp = spacy.load(model_name)
            except Exception:
                # Keep extraction functional even when model weights are absent.
                self._nlp = spacy.blank("en")
                if "sentencizer" not in self._nlp.pipe_names:
                    self._nlp.add_pipe("sentencizer")

            self._add_entity_ruler(self._nlp)
        except Exception:
            self._nlp = None

    def _add_entity_ruler(self, nlp: Any):
        if self._ruler_added:
            return
        if "entity_ruler" in nlp.pipe_names:
            ruler = nlp.get_pipe("entity_ruler")
        else:
            ruler = nlp.add_pipe(
                "entity_ruler", before="ner" if "ner" in nlp.pipe_names else None)

        patterns = []

        def to_pattern(term: str) -> list[dict[str, str]]:
            return [{"LOWER": token} for token in term.split()]

        for term in self._METHOD_KEYWORDS:
            patterns.append({"label": "METHOD", "pattern": to_pattern(term)})
        for term in self._MATERIAL_KEYWORDS:
            patterns.append({"label": "MATERIAL", "pattern": to_pattern(term)})
        for term in self._METRIC_KEYWORDS:
            patterns.append({"label": "METRIC", "pattern": to_pattern(term)})

        ruler.add_patterns(patterns)
        self._ruler_added = True

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _label_to_type(self, label: str) -> str:
        mapping = {
            "METHOD": "method",
            "MATERIAL": "material",
            "METRIC": "metric",
            "ORG": "concept",
            "PERSON": "concept",
            "PRODUCT": "concept",
            "WORK_OF_ART": "concept",
            "GPE": "concept",
        }
        return mapping.get(label, "concept")

    def extract_with_mentions(
        self,
        documents: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Extract entities from documents and preserve where they appear."""
        buckets: dict[tuple[str, str], set[str]] = defaultdict(set)

        for doc in documents:
            text = self._normalize(doc.get("text", ""))
            mention = self._normalize(doc.get("mention", "")) or "research"
            if not text:
                continue

            # Rule-based findings from claim-like statements.
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                lowered = sentence.lower()
                if any(cue in lowered for cue in self._FINDING_CUES):
                    key = (self._normalize(sentence[:160]), "finding")
                    if key[0]:
                        buckets[key].add(mention)

            if self._nlp is None:
                self._fallback_keyword_extract(text, mention, buckets)
                continue

            spacy_doc = self._nlp(text)
            for ent in getattr(spacy_doc, "ents", []):
                name = self._normalize(ent.text)
                if len(name) < 3:
                    continue
                entity_type = self._label_to_type(ent.label_)
                buckets[(name, entity_type)].add(mention)

        items = []
        for (name, entity_type), mentions in buckets.items():
            mention_list = sorted(list(mentions))
            items.append({
                "name": name,
                "entity_type": entity_type,
                "mentions": mention_list,
                "mention_count": len(mention_list),
            })

        items.sort(key=lambda x: (-x["mention_count"],
                   x["entity_type"], x["name"].lower()))
        return items

    def _fallback_keyword_extract(
        self,
        text: str,
        mention: str,
        buckets: dict[tuple[str, str], set[str]],
    ):
        lowered = text.lower()
        for term in self._METHOD_KEYWORDS:
            if term in lowered:
                buckets[(term, "method")].add(mention)
        for term in self._MATERIAL_KEYWORDS:
            if term in lowered:
                buckets[(term, "material")].add(mention)
        for term in self._METRIC_KEYWORDS:
            if term in lowered:
                buckets[(term, "metric")].add(mention)

    def extract(self, text: str):
        """Extract entities from a single text input."""
        return self.extract_with_mentions([
            {"text": text, "mention": "text"}
        ])
