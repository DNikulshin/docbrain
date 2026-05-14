from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class SearchHit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    chunk_id: UUID
    ord: int
    text: str
    distance: float
