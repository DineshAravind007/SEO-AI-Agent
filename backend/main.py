import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import audits, ai
from backend.database.connection import engine, Base
import backend.database.models  # registers models with Base before create_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SEO AI Agent API",
    description="API for the Website SEO Analysis & Recommendation Agent",
    version="1.0.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allow the Vite dev server origin by default.
# Set FRONTEND_ORIGIN env var to override (e.g. production domain).
_frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(audits.router)
app.include_router(ai.router)


@app.get("/api/health", tags=["health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
