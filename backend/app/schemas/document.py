from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentCreate(BaseModel):
    name: str
    content_type: str
    source: str | None = None


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    content_type: str
    source: str | None
    created_at: datetime


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    ord: int
    text: str
