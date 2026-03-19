from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder

from bangstats_server.api.schemas.reference import ReferenceChunkResponse, ReferenceCountsResponse
from bangstats_server.core.services.band import BandService
from bangstats_server.core.services.event import EventService
from bangstats_server.core.services.song import SongService

router = APIRouter()
song_service = SongService()
event_service = EventService()
band_service = BandService()


def _chunk_response(items: list[object]) -> ReferenceChunkResponse:
    encoded = [jsonable_encoder(item) for item in items]
    max_id = 0
    if encoded:
        max_id = max(int(item.get("id", 0) or 0) for item in encoded)
    return ReferenceChunkResponse(max_id=max_id, items=encoded)


@router.get("/reference/songs", response_model=ReferenceChunkResponse)
def get_songs_reference(
    since_id: int = Query(default=0, ge=0),
    limit: int = Query(default=5000, ge=1, le=20000),
):
    return _chunk_response(song_service.list_songs_since_id(since_id, limit=limit))


@router.get("/reference/events", response_model=ReferenceChunkResponse)
def get_events_reference(
    since_id: int = Query(default=0, ge=0),
    limit: int = Query(default=5000, ge=1, le=20000),
):
    return _chunk_response(event_service.list_events_since_id(since_id, limit=limit))


@router.get("/reference/bands", response_model=ReferenceChunkResponse)
def get_bands_reference(
    since_id: int = Query(default=0, ge=0),
    limit: int = Query(default=5000, ge=1, le=20000),
):
    return _chunk_response(band_service.list_bands_since_id(since_id, limit=limit))


@router.get("/reference/counts", response_model=ReferenceCountsResponse)
def get_reference_counts():
    return ReferenceCountsResponse(
        songs=len(song_service.get_all_songs()),
        events=len(event_service.get_all_events()),
        bands=len(band_service.get_all_bands()),
    )
