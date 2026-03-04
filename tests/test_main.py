import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.main import app
from app.database import Base, get_db
import app.database as db_module

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def client():
    # Patch the engine used by the startup event to use SQLite
    original_engine = db_module.engine
    db_module.engine = test_engine
    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=test_engine)
    db_module.engine = original_engine


def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "llm-researcher"}


def test_create_research(client):
    with patch("app.main.process_research"):
        response = client.post("/research", json={"query": "What is machine learning?"})
    assert response.status_code == 201
    data = response.json()
    assert data["query"] == "What is machine learning?"
    assert data["status"] == "pending"
    assert "id" in data


def test_list_research(client):
    with patch("app.main.process_research"):
        client.post("/research", json={"query": "Test query 1"})
        client.post("/research", json={"query": "Test query 2"})
    response = client.get("/research")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_research(client):
    with patch("app.main.process_research"):
        create_response = client.post("/research", json={"query": "Specific query"})
    research_id = create_response.json()["id"]
    response = client.get(f"/research/{research_id}")
    assert response.status_code == 200
    assert response.json()["query"] == "Specific query"


def test_get_research_not_found(client):
    response = client.get("/research/9999")
    assert response.status_code == 404
