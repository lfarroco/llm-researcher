"""NLP module for knowledge extraction components.

This package contains extraction and summarization utilities used by
later research pipeline phases.
"""

from app.nlp.entity_extractor import EntityExtractor
from app.nlp.relation_extractor import RelationExtractor
from app.nlp.summarizer import Summarizer
from app.nlp.topic_modeler import TopicModeler

__all__ = [
    "EntityExtractor",
    "RelationExtractor",
    "Summarizer",
    "TopicModeler",
]
