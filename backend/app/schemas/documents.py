from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = None

class ProjectOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime

class DocumentOut(BaseModel):
    id: UUID
    project_id: UUID
    filename: str
    file_type: str | None
    processing_status: str
    created_at: datetime
    chunk_count: int = 0

class SearchRequest(BaseModel):
    project_id: UUID
    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=15)
