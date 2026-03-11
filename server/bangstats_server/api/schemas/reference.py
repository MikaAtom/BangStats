from typing import Any

from pydantic import BaseModel, Field


class ReferenceChunkResponse(BaseModel):
    max_id: int = 0
    items: list[dict[str, Any]] = Field(default_factory=list)


class ReferenceCountsResponse(BaseModel):
    songs: int
    events: int
    bands: int
