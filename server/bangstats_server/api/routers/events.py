from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder

from bangstats_server.core.services.event import EventService

router = APIRouter()


@router.get("/events/current")
def get_current_event(server: str = Query("en")):
    event_service = EventService()
    event = event_service.get_current_event(language=server)
    if event is None:
        return None
    return jsonable_encoder(event)
