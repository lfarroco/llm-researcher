"""Relationship extraction utilities for research text."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class _RelationRule:
    relation: str
    pattern: re.Pattern[str]


class RelationExtractor:
    """Extract lightweight semantic relationships from short research claims.

    This implementation is intentionally rule-based so it works without large
    external models. It is designed as a practical baseline for Phase 10.
    """

    _SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
    _WS = re.compile(r"\s+")
    _LEADING_ARTICLES = re.compile(r"^(the|a|an|this|that|these|those)\s+", re.I)
    _TRAILING_PUNCT = re.compile(r"[\s,;:.]+$")

    _RELATION_RULES = [
        _RelationRule(
            relation="supports",
            pattern=re.compile(
                r"(?P<subject>[^.?!;,:]{2,120}?)\s+"
                r"(?:supports?|supported|backs?)\s+"
                r"(?P<object>[^.?!;,:]{2,120})",
                re.I,
            ),
        ),
        _RelationRule(
            relation="contradicts",
            pattern=re.compile(
                r"(?P<subject>[^.?!;,:]{2,120}?)\s+"
                r"(?:contradicts?|disputes?|challenges?)\s+"
                r"(?P<object>[^.?!;,:]{2,120})",
                re.I,
            ),
        ),
        _RelationRule(
            relation="causes",
            pattern=re.compile(
                r"(?P<subject>[^.?!;,:]{2,120}?)\s+"
                r"(?:causes?|leads\s+to|results\s+in)\s+"
                r"(?P<object>[^.?!;,:]{2,120})",
                re.I,
            ),
        ),
        _RelationRule(
            relation="correlates_with",
            pattern=re.compile(
                r"(?P<subject>[^.?!;,:]{2,120}?)\s+"
                r"(?:correlates?\s+with|is\s+associated\s+with|associates?\s+with)\s+"
                r"(?P<object>[^.?!;,:]{2,120})",
                re.I,
            ),
        ),
        _RelationRule(
            relation="improves",
            pattern=re.compile(
                r"(?P<subject>[^.?!;,:]{2,120}?)\s+"
                r"(?:improves?|increases?|boosts?)\s+"
                r"(?P<object>[^.?!;,:]{2,120})",
                re.I,
            ),
        ),
        _RelationRule(
            relation="reduces",
            pattern=re.compile(
                r"(?P<subject>[^.?!;,:]{2,120}?)\s+"
                r"(?:reduces?|decreases?|lowers?)\s+"
                r"(?P<object>[^.?!;,:]{2,120})",
                re.I,
            ),
        ),
    ]

    @classmethod
    def _normalize_span(cls, text: str) -> str:
        value = cls._WS.sub(" ", (text or "").strip())
        value = cls._LEADING_ARTICLES.sub("", value)
        value = cls._TRAILING_PUNCT.sub("", value)
        return value

    @staticmethod
    def _is_valid_span(value: str) -> bool:
        if len(value) < 2:
            return False
        lowered = value.lower()
        if lowered in {"it", "this", "that", "they", "we", "i"}:
            return False
        return True

    @classmethod
    def _split_sentences(cls, text: str) -> list[str]:
        text = cls._WS.sub(" ", (text or "").strip())
        if not text:
            return []
        return [s.strip() for s in cls._SENTENCE_SPLIT.split(text) if s.strip()]

    @staticmethod
    def _resolve_bucket_key(
        buckets: dict[tuple[str, str, str], dict[str, Any]],
        subject: str,
        relation: str,
        obj: str,
    ) -> tuple[str, str, str]:
        """Return the bucket key a relation should be aggregated into.

        Relations sharing the same subject and relation type whose objects
        overlap as a prefix/superstring (e.g. ``"hypothesis Y"`` and
        ``"hypothesis Y in replication"``) describe the same claim and are
        merged into one bucket, keeping the first-seen object as canonical.
        """
        subject_l = subject.lower()
        obj_l = obj.lower()
        exact_key = (subject_l, relation, obj_l)
        if exact_key in buckets:
            return exact_key
        for (subj_key, rel_key, obj_key) in buckets:
            if (
                subj_key == subject_l
                and rel_key == relation
                and (obj_l.startswith(obj_key) or obj_key.startswith(obj_l))
            ):
                return (subj_key, rel_key, obj_key)
        return exact_key

    def extract_with_mentions(
        self,
        documents: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Extract relation triples and aggregate mention provenance."""
        buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
        evidence_seen: dict[tuple[str, str, str], set[str]] = defaultdict(set)

        for doc in documents:
            raw_text = doc.get("text", "")
            mention = (doc.get("mention", "") or "research").strip()

            for sentence in self._split_sentences(raw_text):
                for rule in self._RELATION_RULES:
                    for match in rule.pattern.finditer(sentence):
                        subject = self._normalize_span(match.group("subject"))
                        obj = self._normalize_span(match.group("object"))
                        if not (self._is_valid_span(subject) and self._is_valid_span(obj)):
                            continue

                        key = self._resolve_bucket_key(
                            buckets, subject, rule.relation, obj
                        )
                        item = buckets.get(key)
                        if item is None:
                            item = {
                                "subject": subject,
                                "relation": rule.relation,
                                "object": obj,
                                "evidence": [],
                                "mentions": set(),
                            }
                            buckets[key] = item

                        item["mentions"].add(mention)
                        if sentence not in evidence_seen[key]:
                            item["evidence"].append(sentence[:240])
                            evidence_seen[key].add(sentence)

        results = []
        for item in buckets.values():
            mentions = sorted(item["mentions"])
            results.append({
                "subject": item["subject"],
                "relation": item["relation"],
                "object": item["object"],
                "evidence": item["evidence"],
                "mentions": mentions,
                "mention_count": len(mentions),
            })

        results.sort(
            key=lambda r: (
                -r["mention_count"],
                r["relation"],
                r["subject"].lower(),
                r["object"].lower(),
            )
        )
        return results

    def extract(self, text: str) -> list[dict[str, Any]]:
        """Extract relation triples from a single text string."""
        return self.extract_with_mentions([
            {"text": text, "mention": "text"}
        ])
