"""
Kharido FastAPI application.

Run with:
    uvicorn api.main:app --reload --port 8000

Endpoints
---------
POST   /search                        — run the pipeline, return top recommendation
GET    /search/{thread_id}/alternative — resume from checkpoint, reveal backup
GET    /preferences/{user_id}         — load preference profile
PATCH  /preferences/{user_id}         — update preference fields

V2 additions
------------
- GET /search/{thread_id}/stream — SSE stream of node progress events
- POST /search/{thread_id}/accept — explicit accept signal to PreferenceMemory
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.preferences import router as preferences_router
from api.routes.search import router as search_router

app = FastAPI(
    title="Kharido API",
    description="Agentic shopping assistant — one decisive recommendation from free-form queries",
    version="0.1.0",
)

# Allow the Next.js dev server to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router)
app.include_router(preferences_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}
