"""
Hacklytics 2026 — FastAPI backend entry point.

Run from the project root (Hacklytics_2026/):
    python -m uvicorn backend.app.main:app --reload --port 8000

Or from inside backend/:
    python -m uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import dashboard, map as map_router, chatbot

app = FastAPI(
    title="Hacklytics 2026 — Tariff Impact API",
    description=(
        "Backend API for tariff probability data and financial market graphs. "
        "Powers the Dashboard and Map pages."
    ),
    version="1.0.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow all origins for local development. Restrict origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(dashboard.router)
app.include_router(map_router.router)
app.include_router(chatbot.router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Simple liveness probe — returns 200 OK when the server is running."""
    return {"status": "ok"}
