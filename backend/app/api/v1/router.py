from fastapi import APIRouter

from app.api.v1 import academic, audit, auth, biometrics, health, recognition, sessions, structure, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(academic.router)
api_router.include_router(audit.router)
api_router.include_router(structure.router)
api_router.include_router(sessions.router)
api_router.include_router(biometrics.router)
api_router.include_router(recognition.router)
