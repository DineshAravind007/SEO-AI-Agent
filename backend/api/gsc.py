from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import os
import secrets

from backend.database.connection import get_db
from backend.database.models import User
from backend.security.auth import get_current_user, decode_access_token
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
def get_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    configured = is_gsc_configured()
    connected = False
    if configured:
        connected = is_user_connected(db, str(current_user.id))
    return GSCStatusResponse(configured=configured, connected=connected)

@router.get("/auth/login")
def login(request: Request, token: Optional[str] = Query(None)):
    if not is_gsc_configured():
        raise HTTPException(status_code=400, detail="GSC is not configured.")
    
    # Associate user if token provided via query or Authorization header
    user_id = "default_user"
    auth_header = request.headers.get("Authorization")
    tok = token
    if not tok and auth_header and auth_header.startswith("Bearer "):
        tok = auth_header.split(" ", 1)[1]
    
    if tok:
        try:
            payload = decode_access_token(tok)
            if payload.get("sub"):
                user_id = str(payload.get("sub"))
        except Exception:
            pass

    try:
        url, state = get_auth_url()
        request.session['oauth_state'] = state
        request.session['gsc_user_id'] = user_id
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
    target_user_id = request.session.pop('gsc_user_id', "default_user")
    
    try:
        # Pass the full URL to the callback handler for flow validation
        handle_callback(state, code, str(request.url), db, target_user_id)
        # Redirect back to the frontend GSC page
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
        return RedirectResponse(f"{frontend_url}/gsc")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")

@router.get("/sites", response_model=List[GSCSite])
def list_sites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = str(current_user.id)
    if not is_user_connected(db, user_id):
        raise HTTPException(status_code=401, detail="Not connected to GSC.")
    try:
        return get_sites(db, user_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/performance")
def fetch_performance(
    req: GSCPerformanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = str(current_user.id)
    if not is_user_connected(db, user_id):
        raise HTTPException(status_code=401, detail="Not connected to GSC.")
    try:
        return get_performance(db, req.site_url, req.start_date, req.end_date, user_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
