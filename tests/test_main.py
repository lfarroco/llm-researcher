import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.database import Base, get_db
import app.database as db_module
import app.rate_limiter as rate_limiter_module


def override_get_db():
    db = db_module.SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def client():
    # Create all tables on the SAME engine the app uses (app.database.engine).
    # Under CI (DATABASE_URL=sqlite:///:memory:) that engine is a shared
    # in-memory DB, so SessionLocal users (background worker, settings proxy)
    # see the same tables as the endpoints.
    Base.metadata.create_all(bind=db_module.engine)
    # Reset rate limiters between tests to prevent cross-test interference
    rate_limiter_module._research_rate_limiter = rate_limiter_module.RateLimiter(
        requests_per_minute=10, burst_size=100
    )
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=db_module.engine)


def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "llm-researcher"}


def test_create_research(client):
    with patch("app.routers.research.process_research"):
        response = client.post(
            "/research", json={"query": "What is machine learning?"})
    assert response.status_code == 201
    data = response.json()
    assert data["query"] == "What is machine learning?"
    assert data["status"] == "pending"
    assert "id" in data


def test_list_research(client):
    with patch("app.routers.research.process_research"):
        client.post("/research", json={"query": "Test query 1"})
        client.post("/research", json={"query": "Test query 2"})
    response = client.get("/research")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_get_research(client):
    with patch("app.routers.research.process_research"):
        create_response = client.post(
            "/research", json={"query": "Specific query"})
    research_id = create_response.json()["id"]
    response = client.get(f"/research/{research_id}")
    assert response.status_code == 200
    assert response.json()["query"] == "Specific query"


def test_get_research_not_found(client):
    response = client.get("/research/9999")
    assert response.status_code == 404
