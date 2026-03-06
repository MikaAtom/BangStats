from typing import Dict, Optional
from sqlmodel import Field, SQLModel, JSON


class Band(SQLModel, table=True):
    """Band model representing a in-game band in the database."""

    id: Optional[int] = Field(default=None, primary_key=True)
    internal_band_id: int = Field(index=True)
    name: Dict[str, str] = Field(sa_type=JSON)
