import logging
from fastapi import FastAPI
from backend.api import audits
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

app.include_router(audits.router)


@app.get("/api/health", tags=["health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
