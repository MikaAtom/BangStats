from fastapi import APIRouter

from bangstats_server.api.schemas.sync import CountsResponse, SyncRequest
from bangstats_server.core.sync import get_db_counts, update_db

router = APIRouter()


@router.post("/sync", response_model=CountsResponse)
def sync_data(data: SyncRequest):
    songs, events, bands = update_db(data.server)
    return CountsResponse(songs=songs, events=events, bands=bands)


@router.get("/db/counts", response_model=CountsResponse)
def get_counts():
    songs, events, bands = get_db_counts()
    return CountsResponse(songs=songs, events=events, bands=bands)
