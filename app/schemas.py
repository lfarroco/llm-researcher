from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class ResearchCreate(BaseModel):
    query: str


class ResearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query: str
    result: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
