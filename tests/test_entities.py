from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app import models
from app.nlp.entity_extractor import EntityExtractor
from app.routers.state import get_research_entities

SQLALCHEMY_DATABASE_URL = 'sqlite:///./test_entities.db'

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={'check_same_thread': False}
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=test_engine
)


def test_entity_extractor_detects_research_entities():
    extractor = EntityExtractor()
    entities = extractor.extract_with_mentions([
        {
            'text': (
                'Transformer methods improved accuracy on the benchmark dataset. '
                'The model outperforms prior baselines.'
            ),
            'mention': 'source-1',
        }
    ])

    names = {e['name'].lower() for e in entities}
    types = {e['entity_type'] for e in entities}

    assert 'method' in types or 'concept' in types
    assert 'metric' in types or 'accuracy' in names
    assert any('outperforms' in e['name'].lower()
               for e in entities if e['entity_type'] == 'finding')


def test_entities_endpoint_returns_extracted_entities():
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        research = models.Research(query='Entity test', status='completed')
        db.add(research)
        db.commit()
        db.refresh(research)

        db.add(models.ResearchSource(
            research_id=research.id,
            url='https://example.com/paper',
            title='Transformer Benchmark Study',
            content_snippet='Our transformer improves accuracy and reduces latency on a public dataset.',
            source_type='web',
            relevance_score=0.8,
        ))
        db.add(models.ResearchFinding(
            research_id=research.id,
            content='The proposed model outperforms baselines on F1 and accuracy.',
            source_ids=[],
            created_by='ai',
        ))
        db.commit()

        payload = get_research_entities(research.id, db)
        assert payload.research_id == research.id
        assert payload.total_entities >= 1
        assert len(payload.entities) >= 1
        first = payload.entities[0]
        assert first.name
        assert first.entity_type
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)
