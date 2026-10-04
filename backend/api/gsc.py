from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import os
import secrets

from backend.database.connection import get_db
from backend.services.gsc_service import (
    is_gsc_configured,
    get_auth_url,
    handle_callback,
    is_user_connected,
    get_sites,
    get_performance
)

router = APIRouter(prefix="/api/gsc", tags=["gsc"])

class GSCStatusResponse(BaseModel):
    configured: bool
    connected: bool

class GSCSite(BaseModel):
    siteUrl: str
    permissionLevel: str

class GSCPerformanceRequest(BaseModel):
    site_url: str
    start_date: str
    end_date: str

@router.get("/status", response_model=GSCStatusResponse)
def get_status(db: Session = Depends(get_db)):
    configured = is_gsc_configured()
    connected = False
    if configured:
        connected = is_user_connected(db, "default_user")
    return GSCStatusResponse(configured=configured, connected=connected)

@router.get("/auth/login")
def login(request: Request):
    if not is_gsc_configured():
        raise HTTPException(status_code=400, detail="GSC is not configured.")
    
    try:
        url, state = get_auth_url()
        request.session['oauth_state'] = state
        return RedirectResponse(url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/callback")
def auth_callback(request: Request, state: str, code: str, db: Session = Depends(get_db)):
    session_state = request.session.get('oauth_state')
    if not session_state or session_state != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state. Potential CSRF attack.")
    
    # We clear the state from session
    request.session.pop('oauth_state', None)
    
    try:
        # Pass the full URL to the callback handler for flow validation
        handle_callback(state, code, str(request.url), db, "default_user")
        # Redirect back to the frontend GSC page
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(f"{frontend_url}/gsc")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")

@router.get("/sites", response_model=List[GSCSite])
def list_sites(db: Session = Depends(get_db)):
    if not is_user_connected(db, "default_user"):
        raise HTTPException(status_code=401, detail="Not connected to GSC.")
    try:
        return get_sites(db, "default_user")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/performance")
def fetch_performance(req: GSCPerformanceRequest, db: Session = Depends(get_db)):
    if not is_user_connected(db, "default_user"):
        raise HTTPException(status_code=401, detail="Not connected to GSC.")
    try:
        return get_performance(db, req.site_url, req.start_date, req.end_date, "default_user")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
