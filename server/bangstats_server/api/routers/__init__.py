from fastapi import APIRouter

from bangstats_server.api.routers import admin, events, scans, stats, sync, users

api_router = APIRouter()
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(sync.router, tags=["sync"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(scans.router, tags=["scans"])
api_router.include_router(stats.router, tags=["stats"])
