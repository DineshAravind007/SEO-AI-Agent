import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from backend.api import audits, ai, competitors, keywords, gsc, monitoring, auth, notifications, performance
from backend.database.connection import engine, Base
import backend.database.models  # registers models with Base before create_all
from backend.database.migration import run_migrations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Create all tables on startup & run non-destructive schema migrations
Base.metadata.create_all(bind=engine)
run_migrations()

app = FastAPI(
    title="SEO AI Agent API",
    description="API for the Website SEO Analysis & Recommendation Agent",
    version="1.0.0",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "super-secret-default-key-change-in-prod")
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allow the Vite dev server origin by default.
# Set FRONTEND_ORIGIN env var to override (e.g. production domain).
_frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth.router)
app.include_router(audits.router)
app.include_router(ai.router)
app.include_router(competitors.router)
app.include_router(keywords.router)
app.include_router(gsc.router)
app.include_router(monitoring.router)
app.include_router(notifications.router)
app.include_router(performance.router)

@app.get("/api/health", tags=["health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
