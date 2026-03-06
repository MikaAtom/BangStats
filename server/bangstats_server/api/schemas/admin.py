from pydantic import BaseModel


class FlushRequest(BaseModel):
    remote_cache: bool = False
    scan_cache: bool = False
    db: bool = False


class FlushResponse(BaseModel):
    backup_root: str
    moved: list[str]
    skipped: list[str]
