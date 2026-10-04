import os
import json
import logging
import datetime
from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
from backend.database.models import GSCCredentials

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']

def _get_client_config():
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/gsc/auth/callback")
    if not client_id or not client_secret:
        return None, None
        
    config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri]
        }
    }
    return config, redirect_uri

def is_gsc_configured():
    config, _ = _get_client_config()
    return config is not None

def get_auth_url():
    config, redirect_uri = _get_client_config()
    if not config:
        raise ValueError("Google OAuth credentials are not configured in environment.")
        
    flow = Flow.from_client_config(
        config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    
    # Generate URL, specify offline access to get a refresh token
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    
    return auth_url, state

def handle_callback(state: str, code: str, url: str, db: Session, user_id: str = "default_user"):
    config, redirect_uri = _get_client_config()
    if not config:
        raise ValueError("Google OAuth credentials are not configured.")
        
    flow = Flow.from_client_config(
        config,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        state=state
    )
    
    flow.fetch_token(authorization_response=url)
    credentials = flow.credentials
    
    # Store in database securely (server-side only)
    db_cred = db.query(GSCCredentials).filter(GSCCredentials.user_id == user_id).first()
    if not db_cred:
        db_cred = GSCCredentials(user_id=user_id)
        db.add(db_cred)
        
    db_cred.credentials_json = credentials.to_json()
    db.commit()

def _get_valid_credentials(db: Session, user_id: str = "default_user"):
    db_cred = db.query(GSCCredentials).filter(GSCCredentials.user_id == user_id).first()
    if not db_cred or not db_cred.credentials_json:
        return None
        
    try:
        creds = Credentials.from_json(db_cred.credentials_json)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            db_cred.credentials_json = creds.to_json()
            db.commit()
        return creds
    except Exception as e:
        logger.error(f"Error refreshing or parsing GSC credentials: {e}")
        return None

def is_user_connected(db: Session, user_id: str = "default_user"):
    return _get_valid_credentials(db, user_id) is not None

def get_sites(db: Session, user_id: str = "default_user"):
    creds = _get_valid_credentials(db, user_id)
    if not creds:
        raise ValueError("Not connected to GSC")
        
    try:
        service = build('searchconsole', 'v1', credentials=creds)
        site_list = service.sites().list().execute()
        sites = site_list.get('siteEntry', [])
        return [{"siteUrl": s.get("siteUrl"), "permissionLevel": s.get("permissionLevel")} for s in sites]
    except HttpError as e:
        logger.error(f"GSC API Error: {e}")
        raise ValueError("Failed to fetch sites from Google Search Console.")

def get_performance(db: Session, site_url: str, start_date: str, end_date: str, user_id: str = "default_user"):
    creds = _get_valid_credentials(db, user_id)
    if not creds:
        raise ValueError("Not connected to GSC")
        
    service = build('searchconsole', 'v1', credentials=creds)
    
    # We will make 3 requests: Overall metrics, Top queries, Top pages
    # To avoid rate limits or slow requests in an MVP, we could combine, but dimensions are grouped.
    
    try:
        # 1. Overall
        req_overall = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["date"]
        }
        res_overall = service.searchanalytics().query(siteUrl=site_url, body=req_overall).execute()
        rows_overall = res_overall.get('rows', [])
        
        total_clicks = sum(r.get('clicks', 0) for r in rows_overall)
        total_impressions = sum(r.get('impressions', 0) for r in rows_overall)
        avg_ctr = (total_clicks / total_impressions) if total_impressions > 0 else 0
        
        # Calculate weighted average position
        total_position_weight = sum(r.get('position', 0) * r.get('impressions', 0) for r in rows_overall)
        avg_position = (total_position_weight / total_impressions) if total_impressions > 0 else 0
        
        # 2. Top Queries
        req_queries = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["query"],
            "rowLimit": 20
        }
        res_queries = service.searchanalytics().query(siteUrl=site_url, body=req_queries).execute()
        top_queries = [{
            "query": r['keys'][0],
            "clicks": r.get('clicks', 0),
            "impressions": r.get('impressions', 0),
            "ctr": r.get('ctr', 0),
            "position": r.get('position', 0)
        } for r in res_queries.get('rows', [])]
        
        # 3. Top Pages
        req_pages = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["page"],
            "rowLimit": 20
        }
        res_pages = service.searchanalytics().query(siteUrl=site_url, body=req_pages).execute()
        top_pages = [{
            "page": r['keys'][0],
            "clicks": r.get('clicks', 0),
            "impressions": r.get('impressions', 0),
            "ctr": r.get('ctr', 0),
            "position": r.get('position', 0)
        } for r in res_pages.get('rows', [])]
        
        return {
            "summary": {
                "clicks": total_clicks,
                "impressions": total_impressions,
                "ctr": avg_ctr,
                "position": avg_position
            },
            "queries": top_queries,
            "pages": top_pages
        }
        
    except HttpError as e:
        logger.error(f"GSC API Error during performance fetch: {e}")
        raise ValueError(f"Failed to fetch performance data for {site_url}.")
