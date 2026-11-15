"""API router aggregation — single mount point for all admin endpoints."""

from fastapi import APIRouter

from app.api.routes import audit, chat, models, rag, settings, teams

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(rag.router, prefix="/rag", tags=["rag"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])