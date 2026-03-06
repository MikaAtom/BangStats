from typing import Any, Dict, List

from pydantic import BaseModel


class StatsResponse(BaseModel):
    summary: Dict[str, Any]
    top_songs: List[Dict[str, Any]]
    recent: List[Dict[str, Any]]
