from typing import Optional, Any, Dict
from sqlmodel import Field, SQLModel, JSON


class Event(SQLModel, table=True):
    """Event model representing an in-game event."""

    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(index=True, unique=True)
    event_type: str
    event_name: Dict[str, Optional[str]] = Field(sa_type=JSON)
    event_start_at: Dict[str, Optional[str]] = Field(sa_type=JSON)
    event_end_at: Dict[str, Optional[str]] = Field(sa_type=JSON)
    misc: Dict[str, Any] = Field(sa_type=JSON)
