from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from app.database import Base, get_db
import app.database as db_module
from app import models
from app.schemas import ResearchCreate, ResearchResponse
from app.researcher import run_research


@asynccontextmanager
async def lifespan(application: FastAPI):
    Base.metadata.create_all(bind=db_module.engine)
    yield


app = FastAPI(
    title="LLM Researcher",
    description="An autonomous researcher agent powered by LangChain and FastAPI",
    version="1.0.0",
    lifespan=lifespan,
)


def process_research(research_id: int, query: str):
    db = next(get_db())
    try:
        research = db.query(models.Research).filter(models.Research.id == research_id).first()
        if not research:
            return
        try:
            result = run_research(query)
            research.result = result
            research.status = "completed"
        except Exception as e:
            research.result = str(e)
            research.status = "failed"
        db.commit()
    finally:
        db.close()


@app.get("/", tags=["health"])
def health_check():
    return {"status": "ok", "service": "llm-researcher"}


@app.post("/research", response_model=ResearchResponse, status_code=201, tags=["research"])
def create_research(
    payload: ResearchCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    research = models.Research(query=payload.query, status="pending")
    db.add(research)
    db.commit()
    db.refresh(research)
    background_tasks.add_task(process_research, research.id, research.query)
    return research


@app.get("/research", response_model=List[ResearchResponse], tags=["research"])
def list_research(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    return db.query(models.Research).offset(skip).limit(limit).all()


@app.get("/research/{research_id}", response_model=ResearchResponse, tags=["research"])
def get_research(research_id: int, db: Session = Depends(get_db)):
    research = db.query(models.Research).filter(models.Research.id == research_id).first()
    if not research:
        raise HTTPException(status_code=404, detail="Research not found")
    return research
