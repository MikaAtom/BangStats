from fastapi import APIRouter, Depends

from bangstats_server.api.dependencies import get_current_user
from bangstats_server.api.routers import admin, auth, events, reference, scans, stats, sync, users, webui
from bangstats_server.core.config import BANGSTATS_ENV

api_router = APIRouter()
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"], dependencies=[Depends(get_current_user)])
api_router.include_router(sync.router, tags=["sync"], dependencies=[Depends(get_current_user)])
api_router.include_router(events.router, tags=["events"], dependencies=[Depends(get_current_user)])
api_router.include_router(scans.router, tags=["scans"], dependencies=[Depends(get_current_user)])
api_router.include_router(stats.router, tags=["stats"], dependencies=[Depends(get_current_user)])
api_router.include_router(webui.router, tags=["webui"], dependencies=[Depends(get_current_user)])
api_router.include_router(
    reference.router,
    tags=["reference"],
    dependencies=[Depends(get_current_user)],
)
if BANGSTATS_ENV == "dev":
    from bangstats_server.api.routers import dev

    api_router.include_router(dev.router, tags=["dev"], dependencies=[Depends(get_current_user)])
