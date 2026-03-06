from typing import Literal

from pydantic import BaseModel


class SyncRequest(BaseModel):
    server: Literal["en", "jp", "tw", "cn", "kr"]


class CountsResponse(BaseModel):
    songs: int
    events: int
    bands: int
