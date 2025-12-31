"""
Integration management routes for Google Workspace services.
Handles enabling/disabling integrations and OAuth flows.
"""

from fastapi import APIRouter, HTTPException, Request, Cookie, Query
from fastapi.responses import JSONResponse, RedirectResponse
from typing import Dict, Any, Optional
from pathlib import Path
import secrets
import json
import logging
import os

from src.utils.google_auth import AuthManager, OAuthAuth
from src.utils.config_loader import get_config, get_onec_config, save_onec_config, OneCConfig
from src.utils.audit import get_audit_logger
from src.api.session_manager import get_session_manager

logger = logging.getLogger(__name__)


def get_base_url() -> str:
    """
    Get base URL for the application.
    In production, uses Railway domain from environment variable.
    In development, uses localhost.
    """
    # Check for Railway public domain first
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if railway_domain:
        # Railway provides domain without protocol
        return f"https://{railway_domain}"
    
    # Check for explicit API base URL
    api_base_url = os.getenv("API_BASE_URL")
    if api_base_url:
        return api_base_url.rstrip('/')
    
    # Check if we're in production (use config redirect URI as fallback)
    app_env = os.getenv("APP_ENV", "dev").lower()
    if app_env == "production":
        # Try to get from config
        try:
            config = get_config()
            redirect_uri = config.google_auth.oauth_redirect_uri
            # Extract base URL from redirect URI (remove /auth/callback)
            if redirect_uri and redirect_uri != "http://localhost:8000/auth/callback":
                base = redirect_uri.replace("/auth/callback", "").replace("/api/integrations/google-workspace/callback", "")
                if base:
                    return base
        except Exception:
            pass
        # Fallback for production
        return "http://localhost:8000"
    
    # Development default
    return "http://localhost:8000"


def get_frontend_url() -> str:
    """
    Get frontend URL for redirects.
    In production, uses Railway domain (frontend served from same domain).
    In development, uses localhost:5173.
    """
    base_url = get_base_url()
    # In production, frontend is served from the same domain
    app_env = os.getenv("APP_ENV", "dev").lower()
    if app_env == "production":
        return base_url
    # In development, frontend runs on separate port
    return "http://localhost:5173"

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

# Store OAuth state for CSRF protection (integration-specific)
integration_oauth_states: Dict[str, Dict[str, str]] = {}  # session_id -> {integration: state}

# Token paths - получаем из конфига динамически
class DynamicPath:
    """Wrapper для Path, который вычисляет путь динамически из конфига."""
    def __init__(self, token_name: str, is_config: bool = False):
        self.token_name = token_name
        self.is_config = is_config
    
    def _get_path(self) -> Path:
        """Получить актуальный путь из конфига."""
        config = get_config()
        if self.is_config:
            return config.config_dir / self.token_name
        return config.tokens_dir / self.token_name
    
    @property
    def parent(self) -> Path:
        """Получить родительскую директорию."""
        return self._get_path().parent
    
    def exists(self) -> bool:
        return self._get_path().exists()
    
    def unlink(self, missing_ok: bool = False) -> None:
        return self._get_path().unlink(missing_ok=missing_ok)
    
    def __str__(self) -> str:
        return str(self._get_path())
    
    def __fspath__(self) -> str:
        return str(self._get_path())
    
    def open(self, mode='r', **kwargs):
        return self._get_path().open(mode, **kwargs)
    
    def __truediv__(self, other):
        return self._get_path() / other
    
    def parent(self):
        return self._get_path().parent
    
    def read_text(self, encoding=None, errors=None):
        return self._get_path().read_text(encoding=encoding, errors=errors)
    
    def write_text(self, data, encoding=None, errors=None):
        return self._get_path().write_text(data, encoding=encoding, errors=errors)
    
    def read_bytes(self):
        return self._get_path().read_bytes()
    
    def write_bytes(self, data):
        return self._get_path().write_bytes(data)

# Для обратной совместимости - используем DynamicPath
CALENDAR_TOKEN_PATH = DynamicPath("google_calendar_token.json")
GMAIL_TOKEN_PATH = DynamicPath("gmail_token.json")
SHEETS_TOKEN_PATH = DynamicPath("google_sheets_token.json")
WORKSPACE_TOKEN_PATH = DynamicPath("google_workspace_token.json")
WORKSPACE_CONFIG_PATH = DynamicPath("workspace_config.json", is_config=True)

# Gmail API scopes
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.labels",
]

# Google Sheets API scopes
SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# Google Workspace API scopes
WORKSPACE_SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
]


@router.get("/status")
async def get_integrations_status(request: Request):
    """
    Get status of all integrations.
    
    Returns:
        Dictionary with integration statuses
    """
    session_id = request.cookies.get("session_id")
    
    status = {
        "google_calendar": {
            "enabled": False,
            "authenticated": False,
            "token_exists": CALENDAR_TOKEN_PATH.exists()
        },
        "gmail": {
            "enabled": False,
            "authenticated": False,
            "token_exists": GMAIL_TOKEN_PATH.exists()
        },
        "google_sheets": {
            "enabled": False,
            "authenticated": False,
            "token_exists": SHEETS_TOKEN_PATH.exists()
        },
        "google_workspace": {
            "enabled": False,
            "authenticated": False,
            "token_exists": WORKSPACE_TOKEN_PATH.exists(),
            "folder_configured": False
        }
    }
    
    # Check if calendar token exists and is valid
    if CALENDAR_TOKEN_PATH.exists():
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GoogleRequest
            
            creds = Credentials.from_authorized_user_file(
                str(CALENDAR_TOKEN_PATH),
                ["https://www.googleapis.com/auth/calendar"]
            )
            
            # Check if token is valid (not expired or can be refreshed)
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(GoogleRequest())
                    # Save refreshed token
                    with open(CALENDAR_TOKEN_PATH, 'w') as token:
                        token.write(creds.to_json())
                except Exception:
                    pass
            
            status["google_calendar"]["authenticated"] = creds.valid
            status["google_calendar"]["enabled"] = creds.valid
        except Exception as e:
            logger.warning(f"Failed to validate calendar token: {e}")
            status["google_calendar"]["authenticated"] = False
    
    # Check if Gmail token exists and is valid
    if GMAIL_TOKEN_PATH.exists():
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GoogleRequest
            
            creds = Credentials.from_authorized_user_file(
                str(GMAIL_TOKEN_PATH),
                GMAIL_SCOPES
            )
            
            # Check if token is valid (not expired or can be refreshed)
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(GoogleRequest())
                    # Save refreshed token
                    with open(GMAIL_TOKEN_PATH, 'w') as token:
                        token.write(creds.to_json())
                except Exception:
                    pass
            
            status["gmail"]["authenticated"] = creds.valid
            status["gmail"]["enabled"] = creds.valid
        except Exception as e:
            logger.warning(f"Failed to validate Gmail token: {e}")
            status["gmail"]["authenticated"] = False
    
    # Check if Sheets token exists and is valid
    if SHEETS_TOKEN_PATH.exists():
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GoogleRequest
            
            creds = Credentials.from_authorized_user_file(
                str(SHEETS_TOKEN_PATH),
                SHEETS_SCOPES
            )
            
            # Check if token is valid (not expired or can be refreshed)
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(GoogleRequest())
                    # Save refreshed token
                    with open(SHEETS_TOKEN_PATH, 'w') as token:
                        token.write(creds.to_json())
                except Exception:
                    pass
            
            status["google_sheets"]["authenticated"] = creds.valid
            status["google_sheets"]["enabled"] = creds.valid
        except Exception as e:
            logger.warning(f"Failed to validate Sheets token: {e}")
            status["google_sheets"]["authenticated"] = False
    
    # Check if Workspace token exists and is valid
    if WORKSPACE_TOKEN_PATH.exists():
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GoogleRequest
            
            creds = Credentials.from_authorized_user_file(
                str(WORKSPACE_TOKEN_PATH),
                WORKSPACE_SCOPES
            )
            
            # Check if token is valid (not expired or can be refreshed)
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(GoogleRequest())
                    # Save refreshed token
                    with open(WORKSPACE_TOKEN_PATH, 'w') as token:
                        token.write(creds.to_json())
                except Exception:
                    pass
            
            status["google_workspace"]["authenticated"] = creds.valid
            status["google_workspace"]["enabled"] = creds.valid
            
            # Check if folder is configured
            if WORKSPACE_CONFIG_PATH.exists():
                try:
                    config_text = WORKSPACE_CONFIG_PATH.read_text()
                    config = json.loads(config_text)
                    status["google_workspace"]["folder_configured"] = bool(config.get("folder_id"))
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Failed to validate Workspace token: {e}")
            status["google_workspace"]["authenticated"] = False
    
    return status


@router.get("/google-calendar/status")
async def get_calendar_status():
    """
    Get Google Calendar integration status.
    
    Returns:
        Status information about Calendar integration
    """
    token_exists = CALENDAR_TOKEN_PATH.exists()
    authenticated = False
    
    if token_exists:
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            
            creds = Credentials.from_authorized_user_file(
                str(CALENDAR_TOKEN_PATH),
                ["https://www.googleapis.com/auth/calendar"]
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(CALENDAR_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            
            authenticated = creds.valid
        except Exception as e:
            logger.warning(f"Failed to validate calendar token: {e}")
    
    return {
        "enabled": authenticated,
        "authenticated": authenticated,
        "token_exists": token_exists
    }


@router.post("/google-calendar/enable")
async def enable_calendar_integration(request: Request):
    """
    Enable Google Calendar integration.
    If not authenticated, initiates OAuth flow.
    
    Returns:
        - If authenticated: success status
        - If not authenticated: OAuth authorization URL
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = get_session_manager().create_session()
    
    # Check if already authenticated
    if CALENDAR_TOKEN_PATH.exists():
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            
            creds = Credentials.from_authorized_user_file(
                str(CALENDAR_TOKEN_PATH),
                ["https://www.googleapis.com/auth/calendar"]
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(CALENDAR_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            
            if creds.valid:
                # Already authenticated
                audit_logger = get_audit_logger()
                audit_logger.log_user_interaction(
                    "calendar_integration_enabled",
                    "Google Calendar integration enabled",
                    session_id=session_id
                )
                
                return {
                    "status": "enabled",
                    "authenticated": True,
                    "message": "Google Calendar integration is already enabled"
                }
        except Exception as e:
            logger.warning(f"Token exists but invalid: {e}")
    
    # Need to authenticate - initiate OAuth flow
    try:
        config = get_config()
        # Use Calendar-specific redirect URI
        base_url = get_base_url()
        calendar_redirect_uri = f"{base_url}/api/integrations/google-calendar/callback"
        oauth_auth = OAuthAuth(
            client_id=config.google_auth.oauth_client_id,
            client_secret=config.google_auth.oauth_client_secret,
            redirect_uri=calendar_redirect_uri,
            scopes=["https://www.googleapis.com/auth/calendar"],
            token_path=CALENDAR_TOKEN_PATH
        )
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        if session_id not in integration_oauth_states:
            integration_oauth_states[session_id] = {}
        integration_oauth_states[session_id]["google_calendar"] = state
        
        # Get authorization URL
        auth_url = oauth_auth.get_authorization_url(state)
        
        return {
            "status": "oauth_required",
            "authenticated": False,
            "auth_url": auth_url,
            "message": "OAuth authorization required"
        }
        
    except Exception as e:
        logger.error(f"Failed to initiate OAuth flow: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate OAuth flow: {str(e)}"
        )


@router.get("/google-calendar/callback")
async def calendar_oauth_callback(
    code: str,
    state: str,
    request: Request,
    error: Optional[str] = None
):
    """
    OAuth callback for Google Calendar integration.
    Exchanges authorization code for access token and saves it.
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error: {error}"
        )
    
    if not code:
        raise HTTPException(
            status_code=400,
            detail="Authorization code is missing"
        )
    
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Session not found"
        )
    
    # Verify state
    stored_state = None
    if session_id in integration_oauth_states:
        stored_state = integration_oauth_states[session_id].get("google_calendar")
    
    if not stored_state or stored_state != state:
        raise HTTPException(
            status_code=400,
            detail="Invalid state parameter"
        )
    
    try:
        config = get_config()
        # Use Calendar-specific redirect URI
        base_url = get_base_url()
        calendar_redirect_uri = f"{base_url}/api/integrations/google-calendar/callback"
        oauth_auth = OAuthAuth(
            client_id=config.google_auth.oauth_client_id,
            client_secret=config.google_auth.oauth_client_secret,
            redirect_uri=calendar_redirect_uri,
            scopes=["https://www.googleapis.com/auth/calendar"],
            token_path=CALENDAR_TOKEN_PATH
        )
        
        # Exchange code for token
        credentials = oauth_auth.exchange_code_for_token(code)
        
        # Clean up state
        if session_id in integration_oauth_states:
            integration_oauth_states[session_id].pop("google_calendar", None)
        
        # Log authentication
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "calendar_oauth_completed",
            "Google Calendar OAuth completed successfully",
            session_id=session_id
        )
        
        # Redirect to frontend with success
        frontend_url = get_frontend_url()
        return RedirectResponse(
            url=f"{frontend_url}/?calendar_auth=success",
            status_code=302
        )
        
    except Exception as e:
        logger.error(f"Failed to complete OAuth flow: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete OAuth flow: {str(e)}"
        )


@router.post("/google-calendar/disable")
async def disable_calendar_integration(request: Request):
    """
    Disable Google Calendar integration.
    Removes the OAuth token.
    """
    session_id = request.cookies.get("session_id")
    
    try:
        # Remove token file
        if CALENDAR_TOKEN_PATH.exists():
            CALENDAR_TOKEN_PATH.unlink()
        
        # Log action
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "calendar_integration_disabled",
            "Google Calendar integration disabled",
            session_id=session_id
        )
        
        return {
            "status": "disabled",
            "message": "Google Calendar integration has been disabled"
        }
        
    except Exception as e:
        logger.error(f"Failed to disable calendar integration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disable integration: {str(e)}"
        )


# ========== GMAIL INTEGRATION ROUTES ==========

@router.get("/gmail/status")
async def get_gmail_status():
    """
    Get Gmail integration status.
    
    Returns:
        Status information about Gmail integration
    """
    token_exists = GMAIL_TOKEN_PATH.exists()
    authenticated = False
    email_address = None
    
    if token_exists:
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GoogleRequest
            
            creds = Credentials.from_authorized_user_file(
                str(GMAIL_TOKEN_PATH),
                GMAIL_SCOPES
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                with open(GMAIL_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            
            authenticated = creds.valid
            
            # Get user email if authenticated
            if authenticated:
                from googleapiclient.discovery import build
                service = build('gmail', 'v1', credentials=creds)
                profile = service.users().getProfile(userId='me').execute()
                email_address = profile.get('emailAddress')
                
        except Exception as e:
            logger.warning(f"Failed to validate Gmail token: {e}")
    
    return {
        "enabled": authenticated,
        "authenticated": authenticated,
        "token_exists": token_exists,
        "email": email_address
    }


@router.post("/gmail/enable")
async def enable_gmail_integration(request: Request):
    """
    Enable Gmail integration.
    If not authenticated, initiates OAuth flow.
    
    Returns:
        - If authenticated: success status
        - If not authenticated: OAuth authorization URL
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = get_session_manager().create_session()
    
    # Check if already authenticated
    if GMAIL_TOKEN_PATH.exists():
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GoogleRequest
            
            creds = Credentials.from_authorized_user_file(
                str(GMAIL_TOKEN_PATH),
                GMAIL_SCOPES
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                with open(GMAIL_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            
            if creds.valid:
                # Get user email
                from googleapiclient.discovery import build
                service = build('gmail', 'v1', credentials=creds)
                profile = service.users().getProfile(userId='me').execute()
                email_address = profile.get('emailAddress')
                
                # Already authenticated
                audit_logger = get_audit_logger()
                audit_logger.log_user_interaction(
                    "gmail_integration_enabled",
                    f"Gmail integration enabled for {email_address}",
                    session_id=session_id
                )
                
                return {
                    "status": "enabled",
                    "authenticated": True,
                    "email": email_address,
                    "message": "Gmail integration is already enabled"
                }
        except Exception as e:
            logger.warning(f"Gmail token exists but invalid: {e}")
    
    # Need to authenticate - initiate OAuth flow
    try:
        config = get_config()
        # Use Gmail-specific redirect URI
        base_url = get_base_url()
        gmail_redirect_uri = f"{base_url}/api/integrations/gmail/callback"
        oauth_auth = OAuthAuth(
            client_id=config.google_auth.oauth_client_id,
            client_secret=config.google_auth.oauth_client_secret,
            redirect_uri=gmail_redirect_uri,
            scopes=GMAIL_SCOPES,
            token_path=GMAIL_TOKEN_PATH
        )
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        if session_id not in integration_oauth_states:
            integration_oauth_states[session_id] = {}
        integration_oauth_states[session_id]["gmail"] = state
        
        # Get authorization URL
        auth_url = oauth_auth.get_authorization_url(state)
        
        response = JSONResponse({
            "status": "oauth_required",
            "authenticated": False,
            "auth_url": auth_url,
            "message": "OAuth authorization required for Gmail"
        })
        response.set_cookie("session_id", session_id, httponly=True)
        return response
        
    except Exception as e:
        logger.error(f"Failed to initiate Gmail OAuth flow: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate OAuth flow: {str(e)}"
        )


@router.get("/gmail/callback")
async def gmail_oauth_callback(
    code: str,
    state: str,
    request: Request,
    error: Optional[str] = None
):
    """
    OAuth callback for Gmail integration.
    Exchanges authorization code for access token and saves it.
    """
    if error:
        # Redirect to frontend with error
        frontend_url = get_frontend_url()
        return RedirectResponse(
            url=f"{frontend_url}/?gmail_auth=error&error={error}",
            status_code=302
        )
    
    if not code:
        raise HTTPException(
            status_code=400,
            detail="Authorization code is missing"
        )
    
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Session not found"
        )
    
    # Verify state
    stored_state = None
    if session_id in integration_oauth_states:
        stored_state = integration_oauth_states[session_id].get("gmail")
    
    if not stored_state or stored_state != state:
        raise HTTPException(
            status_code=400,
            detail="Invalid state parameter"
        )
    
    try:
        config = get_config()
        # Use Gmail-specific redirect URI
        base_url = get_base_url()
        gmail_redirect_uri = f"{base_url}/api/integrations/gmail/callback"
        oauth_auth = OAuthAuth(
            client_id=config.google_auth.oauth_client_id,
            client_secret=config.google_auth.oauth_client_secret,
            redirect_uri=gmail_redirect_uri,
            scopes=GMAIL_SCOPES,
            token_path=GMAIL_TOKEN_PATH
        )
        
        # Exchange code for token
        credentials = oauth_auth.exchange_code_for_token(code)
        
        # Clean up state
        if session_id in integration_oauth_states:
            integration_oauth_states[session_id].pop("gmail", None)
        
        # Get user email
        from googleapiclient.discovery import build
        service = build('gmail', 'v1', credentials=credentials)
        profile = service.users().getProfile(userId='me').execute()
        email_address = profile.get('emailAddress')
        
        # Log authentication
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "gmail_oauth_completed",
            f"Gmail OAuth completed for {email_address}",
            session_id=session_id
        )
        
        # Redirect to frontend with success
        frontend_url = get_frontend_url()
        return RedirectResponse(
            url=f"{frontend_url}/?gmail_auth=success",
            status_code=302
        )
        
    except Exception as e:
        logger.error(f"Failed to complete Gmail OAuth flow: {e}")
        frontend_url = get_frontend_url()
        return RedirectResponse(
            url=f"{frontend_url}/?gmail_auth=error&error={str(e)}",
            status_code=302
        )


@router.post("/gmail/disable")
async def disable_gmail_integration(request: Request):
    """
    Disable Gmail integration.
    Removes the OAuth token.
    """
    session_id = request.cookies.get("session_id")
    
    try:
        # Remove token file
        if GMAIL_TOKEN_PATH.exists():
            GMAIL_TOKEN_PATH.unlink()
        
        # Log action
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "gmail_integration_disabled",
            "Gmail integration disabled",
            session_id=session_id
        )
        
        return {
            "status": "disabled",
            "message": "Gmail integration has been disabled"
        }
        
    except Exception as e:
        logger.error(f"Failed to disable Gmail integration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disable integration: {str(e)}"
        )


# ========== GOOGLE SHEETS INTEGRATION ROUTES ==========

@router.get("/google-sheets/status")
async def get_sheets_status():
    """
    Get Google Sheets integration status.
    
    Returns:
        Status information about Sheets integration
    """
    token_exists = SHEETS_TOKEN_PATH.exists()
    authenticated = False
    
    if token_exists:
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GoogleRequest
            
            creds = Credentials.from_authorized_user_file(
                str(SHEETS_TOKEN_PATH),
                SHEETS_SCOPES
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                with open(SHEETS_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            
            authenticated = creds.valid
                
        except Exception as e:
            logger.warning(f"Failed to validate Sheets token: {e}")
    
    return {
        "enabled": authenticated,
        "authenticated": authenticated,
        "token_exists": token_exists
    }


@router.get("/google-sheets/enable")
async def enable_sheets_integration_get(request: Request):
    """
    Enable Google Sheets integration via GET (for browser access).
    Redirects to OAuth authorization URL if not authenticated.
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = get_session_manager().create_session()
    
    # Check if already authenticated
    if SHEETS_TOKEN_PATH.exists():
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GoogleRequest
            
            creds = Credentials.from_authorized_user_file(
                str(SHEETS_TOKEN_PATH),
                SHEETS_SCOPES
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                with open(SHEETS_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            
            if creds.valid:
                # Already authenticated - redirect to frontend with success
                frontend_url = get_frontend_url()
                return RedirectResponse(
                    url=f"{frontend_url}/?sheets_auth=already_enabled",
                    status_code=302
                )
        except Exception as e:
            logger.warning(f"Sheets token exists but invalid: {e}")
    
    # Need to authenticate - initiate OAuth flow
    try:
        config = get_config()
        base_url = get_base_url()
        sheets_redirect_uri = f"{base_url}/api/integrations/google-sheets/callback"
        oauth_auth = OAuthAuth(
            client_id=config.google_auth.oauth_client_id,
            client_secret=config.google_auth.oauth_client_secret,
            redirect_uri=sheets_redirect_uri,
            scopes=SHEETS_SCOPES,
            token_path=SHEETS_TOKEN_PATH
        )
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        if session_id not in integration_oauth_states:
            integration_oauth_states[session_id] = {}
        integration_oauth_states[session_id]["google_sheets"] = state
        
        # Get authorization URL and redirect directly
        auth_url = oauth_auth.get_authorization_url(state)
        # #region debug log
        import json
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"test","hypothesisId":"A","location":"integration_routes.py:GET_enable","message":"Sheets OAuth URL generated (GET)","data":{"auth_url":auth_url,"redirect_uri":sheets_redirect_uri},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        
        response = RedirectResponse(url=auth_url, status_code=302)
        response.set_cookie("session_id", session_id, httponly=True)
        return response
        
    except Exception as e:
        logger.error(f"Failed to initiate Google Sheets OAuth flow: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate OAuth flow: {str(e)}"
        )


@router.post("/google-sheets/enable")
async def enable_sheets_integration(request: Request):
    """
    Enable Google Sheets integration.
    If not authenticated, initiates OAuth flow.
    
    Returns:
        - If authenticated: success status
        - If not authenticated: OAuth authorization URL
    """
    # #region debug log
    import json
    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
        f.write(json.dumps({"sessionId":"debug-session","runId":"test","hypothesisId":"A","location":"integration_routes.py:872","message":"enable_sheets_integration called","data":{"token_exists":SHEETS_TOKEN_PATH.exists(),"token_path":str(SHEETS_TOKEN_PATH)},"timestamp":int(__import__('time').time()*1000)})+'\n')
    # #endregion
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = get_session_manager().create_session()
    
    # Check if already authenticated
    if SHEETS_TOKEN_PATH.exists():
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GoogleRequest
            
            creds = Credentials.from_authorized_user_file(
                str(SHEETS_TOKEN_PATH),
                SHEETS_SCOPES
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                with open(SHEETS_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            
            if creds.valid:
                # Already authenticated
                audit_logger = get_audit_logger()
                audit_logger.log_user_interaction(
                    "sheets_integration_enabled",
                    "Google Sheets integration enabled",
                    session_id=session_id
                )
                
                return {
                    "status": "enabled",
                    "authenticated": True,
                    "message": "Google Sheets integration is already enabled"
                }
        except Exception as e:
            logger.warning(f"Sheets token exists but invalid: {e}")
    
    # Need to authenticate - initiate OAuth flow
    try:
        config = get_config()
        # Use Sheets-specific redirect URI
        base_url = get_base_url()
        sheets_redirect_uri = f"{base_url}/api/integrations/google-sheets/callback"
        oauth_auth = OAuthAuth(
            client_id=config.google_auth.oauth_client_id,
            client_secret=config.google_auth.oauth_client_secret,
            redirect_uri=sheets_redirect_uri,
            scopes=SHEETS_SCOPES,
            token_path=SHEETS_TOKEN_PATH
        )
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        if session_id not in integration_oauth_states:
            integration_oauth_states[session_id] = {}
        integration_oauth_states[session_id]["google_sheets"] = state
        
        # Get authorization URL
        auth_url = oauth_auth.get_authorization_url(state)
        # #region debug log
        import json
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"test","hypothesisId":"A","location":"integration_routes.py:940","message":"Sheets OAuth URL generated","data":{"auth_url":auth_url,"redirect_uri":sheets_redirect_uri},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        
        response = JSONResponse({
            "status": "oauth_required",
            "authenticated": False,
            "auth_url": auth_url,
            "message": "OAuth authorization required for Google Sheets"
        })
        response.set_cookie("session_id", session_id, httponly=True)
        return response
        
    except Exception as e:
        logger.error(f"Failed to initiate Google Sheets OAuth flow: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate OAuth flow: {str(e)}"
        )


@router.get("/google-sheets/callback")
async def sheets_oauth_callback(
    code: str,
    state: str,
    request: Request,
    error: Optional[str] = None
):
    """
    OAuth callback for Google Sheets integration.
    Exchanges authorization code for access token and saves it.
    """
    if error:
        # Redirect to frontend with error
        frontend_url = get_frontend_url()
        return RedirectResponse(
            url=f"{frontend_url}/?sheets_auth=error&error={error}",
            status_code=302
        )
    
    if not code:
        raise HTTPException(
            status_code=400,
            detail="Authorization code is missing"
        )
    
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Session not found"
        )
    
    # Verify state
    stored_state = None
    if session_id in integration_oauth_states:
        stored_state = integration_oauth_states[session_id].get("google_sheets")
    
    if not stored_state or stored_state != state:
        raise HTTPException(
            status_code=400,
            detail="Invalid state parameter"
        )
    
    try:
        config = get_config()
        # Use Sheets-specific redirect URI
        base_url = get_base_url()
        sheets_redirect_uri = f"{base_url}/api/integrations/google-sheets/callback"
        oauth_auth = OAuthAuth(
            client_id=config.google_auth.oauth_client_id,
            client_secret=config.google_auth.oauth_client_secret,
            redirect_uri=sheets_redirect_uri,
            scopes=SHEETS_SCOPES,
            token_path=SHEETS_TOKEN_PATH
        )
        
        # Exchange code for token
        credentials = oauth_auth.exchange_code_for_token(code)
        # #region debug log
        import json
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"test","hypothesisId":"A","location":"integration_routes.py:1016","message":"Sheets token created","data":{"token_path":str(SHEETS_TOKEN_PATH),"token_exists":SHEETS_TOKEN_PATH.exists()},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        
        # Clean up state
        if session_id in integration_oauth_states:
            integration_oauth_states[session_id].pop("google_sheets", None)
        
        # Log authentication
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "sheets_oauth_completed",
            "Google Sheets OAuth completed successfully",
            session_id=session_id
        )
        
        # Redirect to frontend with success
        frontend_url = get_frontend_url()
        return RedirectResponse(
            url=f"{frontend_url}/?sheets_auth=success",
            status_code=302
        )
        
    except Exception as e:
        logger.error(f"Failed to complete Google Sheets OAuth flow: {e}")
        frontend_url = get_frontend_url()
        return RedirectResponse(
            url=f"{frontend_url}/?sheets_auth=error&error={str(e)}",
            status_code=302
        )


@router.post("/google-sheets/disable")
async def disable_sheets_integration(request: Request):
    """
    Disable Google Sheets integration.
    Removes the OAuth token.
    """
    session_id = request.cookies.get("session_id")
    
    try:
        # Remove token file
        if SHEETS_TOKEN_PATH.exists():
            SHEETS_TOKEN_PATH.unlink()
        
        # Log action
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "sheets_integration_disabled",
            "Google Sheets integration disabled",
            session_id=session_id
        )
        
        return {
            "status": "disabled",
            "message": "Google Sheets integration has been disabled"
        }
        
    except Exception as e:
        logger.error(f"Failed to disable Google Sheets integration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disable integration: {str(e)}"
        )


# ========== GOOGLE WORKSPACE INTEGRATION ROUTES ==========

@router.get("/google-workspace/status")
async def get_workspace_status():
    """
    Get Google Workspace integration status.
    
    Returns:
        Status information about Workspace integration
    """
    token_exists = WORKSPACE_TOKEN_PATH.exists()
    authenticated = False
    folder_configured = False
    folder_info = None
    
    if token_exists:
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GoogleRequest
            
            creds = Credentials.from_authorized_user_file(
                str(WORKSPACE_TOKEN_PATH),
                WORKSPACE_SCOPES
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                with open(WORKSPACE_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            
            authenticated = creds.valid
            
            # Check folder configuration
            if WORKSPACE_CONFIG_PATH.exists():
                try:
                    config_text = WORKSPACE_CONFIG_PATH.read_text()
                    config = json.loads(config_text)
                    folder_id = config.get("folder_id")
                    folder_configured = bool(folder_id)
                    if folder_id:
                        folder_info = {
                            "id": folder_id,
                            "name": config.get("folder_name"),
                            "url": config.get("folder_url")
                        }
                except Exception as e:
                    logger.warning(f"Failed to load workspace config: {e}")
        except Exception as e:
            logger.warning(f"Failed to validate Workspace token: {e}")
    
    return {
        "enabled": authenticated and folder_configured,
        "authenticated": authenticated,
        "token_exists": token_exists,
        "folder_configured": folder_configured,
        "folder": folder_info
    }


@router.post("/google-workspace/enable")
async def enable_workspace_integration(request: Request):
    """
    Enable Google Workspace integration.
    If not authenticated, initiates OAuth flow.
    
    Returns:
        - If authenticated: success status
        - If not authenticated: OAuth authorization URL
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = get_session_manager().create_session()
    
    # Check if already authenticated
    if WORKSPACE_TOKEN_PATH.exists():
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request as GoogleRequest
            
            creds = Credentials.from_authorized_user_file(
                str(WORKSPACE_TOKEN_PATH),
                WORKSPACE_SCOPES
            )
            
            # Refresh if needed
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                with open(WORKSPACE_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            
            if creds.valid:
                # Check if folder is configured
                folder_configured = False
                if WORKSPACE_CONFIG_PATH.exists():
                    try:
                        config_text = WORKSPACE_CONFIG_PATH.read_text()
                        config = json.loads(config_text)
                        folder_configured = bool(config.get("folder_id"))
                    except Exception:
                        pass
                
                # Already authenticated
                audit_logger = get_audit_logger()
                audit_logger.log_user_interaction(
                    "workspace_integration_enabled",
                    "Google Workspace integration enabled",
                    session_id=session_id
                )
                
                return {
                    "status": "enabled",
                    "authenticated": True,
                    "folder_configured": folder_configured,
                    "message": "Google Workspace integration is already enabled" + (
                        "" if folder_configured else ". Please configure workspace folder."
                    )
                }
        except Exception as e:
            logger.warning(f"Workspace token exists but invalid: {e}")
    
    # Need to authenticate - initiate OAuth flow
    try:
        config = get_config()
        base_url = get_base_url()
        workspace_redirect_uri = f"{base_url}/api/integrations/google-workspace/callback"
        oauth_auth = OAuthAuth(
            client_id=config.google_auth.oauth_client_id,
            client_secret=config.google_auth.oauth_client_secret,
            redirect_uri=workspace_redirect_uri,
            scopes=WORKSPACE_SCOPES,
            token_path=WORKSPACE_TOKEN_PATH
        )
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        if session_id not in integration_oauth_states:
            integration_oauth_states[session_id] = {}
        integration_oauth_states[session_id]["google_workspace"] = state
        
        # Get authorization URL
        auth_url = oauth_auth.get_authorization_url(state)
        
        response = JSONResponse({
            "status": "oauth_required",
            "authenticated": False,
            "auth_url": auth_url,
            "message": "OAuth authorization required for Google Workspace"
        })
        response.set_cookie("session_id", session_id, httponly=True)
        return response
        
    except Exception as e:
        logger.error(f"Failed to initiate Google Workspace OAuth flow: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate OAuth flow: {str(e)}"
        )


@router.get("/google-workspace/callback")
async def workspace_oauth_callback(
    code: str,
    state: str,
    request: Request,
    error: Optional[str] = None
):
    """
    OAuth callback for Google Workspace integration.
    Exchanges authorization code for access token and saves it.
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error: {error}"
        )
    
    if not code:
        raise HTTPException(
            status_code=400,
            detail="Authorization code is missing"
        )
    
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Session not found"
        )
    
    # Verify state
    stored_state = None
    if session_id in integration_oauth_states:
        stored_state = integration_oauth_states[session_id].get("google_workspace")
    
    if not stored_state or stored_state != state:
        raise HTTPException(
            status_code=400,
            detail="Invalid state parameter"
        )
    
    try:
        config = get_config()
        base_url = get_base_url()
        workspace_redirect_uri = f"{base_url}/api/integrations/google-workspace/callback"
        oauth_auth = OAuthAuth(
            client_id=config.google_auth.oauth_client_id,
            client_secret=config.google_auth.oauth_client_secret,
            redirect_uri=workspace_redirect_uri,
            scopes=WORKSPACE_SCOPES,
            token_path=WORKSPACE_TOKEN_PATH
        )
        
        # Exchange code for token
        credentials = oauth_auth.exchange_code_for_token(code)
        
        # Clean up state
        if session_id in integration_oauth_states:
            integration_oauth_states[session_id].pop("google_workspace", None)
        
        # Log authentication
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "workspace_oauth_completed",
            "Google Workspace OAuth completed successfully",
            session_id=session_id
        )
        
        # Redirect to frontend - will prompt for folder selection
        frontend_url = get_frontend_url()
        return RedirectResponse(
            url=f"{frontend_url}/?workspace_auth=success",
            status_code=302
        )
        
    except Exception as e:
        logger.error(f"Failed to complete Google Workspace OAuth flow: {e}")
        frontend_url = get_frontend_url()
        return RedirectResponse(
            url=f"{frontend_url}/?workspace_auth=error&error={str(e)}",
            status_code=302
        )


@router.post("/google-workspace/disable")
async def disable_workspace_integration(request: Request):
    """
    Disable Google Workspace integration.
    Removes the OAuth token and configuration.
    """
    session_id = request.cookies.get("session_id")
    
    try:
        # Remove token file
        if WORKSPACE_TOKEN_PATH.exists():
            WORKSPACE_TOKEN_PATH.unlink()
        
        # Remove config file
        if WORKSPACE_CONFIG_PATH.exists():
            WORKSPACE_CONFIG_PATH.unlink()
        
        # Log action
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "workspace_integration_disabled",
            "Google Workspace integration disabled",
            session_id=session_id
        )
        
        return {
            "status": "disabled",
            "message": "Google Workspace integration has been disabled"
        }
        
    except Exception as e:
        logger.error(f"Failed to disable Google Workspace integration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disable integration: {str(e)}"
        )


@router.get("/google-workspace/folders")
async def list_workspace_folders(request: Request):
    """
    List folders from Google Drive that can be used as workspace folder.
    Returns folders from the user's Drive.
    """
    if not WORKSPACE_TOKEN_PATH.exists():
        raise HTTPException(
            status_code=401,
            detail="Google Workspace not authenticated. Please enable integration first."
        )
    
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleRequest
        from googleapiclient.discovery import build
        
        creds = Credentials.from_authorized_user_file(
            str(WORKSPACE_TOKEN_PATH),
            WORKSPACE_SCOPES
        )
        
        # Refresh if needed
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            with open(WORKSPACE_TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
        
        drive_service = build('drive', 'v3', credentials=creds)
        
        # List folders (excluding trashed)
        results = drive_service.files().list(
            q="mimeType='application/vnd.google-apps.folder' and trashed=false",
            pageSize=100,
            fields="files(id, name, createdTime, modifiedTime, webViewLink)",
            orderBy="modifiedTime desc"
        ).execute()
        
        folders = results.get('files', [])
        
        return {
            "folders": [
                {
                    "id": f.get('id'),
                    "name": f.get('name'),
                    "createdTime": f.get('createdTime'),
                    "modifiedTime": f.get('modifiedTime'),
                    "url": f.get('webViewLink')
                }
                for f in folders
            ],
            "count": len(folders)
        }
        
    except Exception as e:
        logger.error(f"Failed to list folders: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list folders: {str(e)}"
        )


@router.post("/google-workspace/set-folder")
async def set_workspace_folder(
    request: Request,
    folder_id: str = Query(..., description="Google Drive folder ID"),
    folder_name: Optional[str] = Query(None, description="Optional folder name")
):
    """
    Set the workspace folder ID.
    
    Args:
        folder_id: Google Drive folder ID
        folder_name: Optional folder name (will be fetched if not provided)
    """
    if not WORKSPACE_TOKEN_PATH.exists():
        raise HTTPException(
            status_code=401,
            detail="Google Workspace not authenticated. Please enable integration first."
        )
    
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleRequest
        from googleapiclient.discovery import build
        
        creds = Credentials.from_authorized_user_file(
            str(WORKSPACE_TOKEN_PATH),
            WORKSPACE_SCOPES
        )
        
        # Refresh if needed
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            with open(WORKSPACE_TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
        
        # Get folder info if name not provided
        if not folder_name:
            drive_service = build('drive', 'v3', credentials=creds)
            folder_info = drive_service.files().get(
                fileId=folder_id,
                fields="id, name, webViewLink"
            ).execute()
            folder_name = folder_info.get('name')
            folder_url = folder_info.get('webViewLink')
        else:
            drive_service = build('drive', 'v3', credentials=creds)
            folder_info = drive_service.files().get(
                fileId=folder_id,
                fields="webViewLink"
            ).execute()
            folder_url = folder_info.get('webViewLink')
        
        # Save configuration
        config = {
            "folder_id": folder_id,
            "folder_name": folder_name,
            "folder_url": folder_url
        }
        
        # Get actual path from DynamicPath and ensure parent directory exists
        config_path = WORKSPACE_CONFIG_PATH._get_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write configuration using write_text method
        WORKSPACE_CONFIG_PATH.write_text(json.dumps(config, indent=2))
        
        # Log action
        session_id = request.cookies.get("session_id")
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "workspace_folder_configured",
            f"Workspace folder set to: {folder_name} ({folder_id})",
            session_id=session_id
        )
        
        return {
            "status": "configured",
            "folder_id": folder_id,
            "folder_name": folder_name,
            "folder_url": folder_url
        }
        
    except HttpError as e:
        logger.error(f"Failed to set workspace folder: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid folder ID or access denied: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to set workspace folder: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set folder: {str(e)}"
        )


@router.get("/google-workspace/current-folder")
async def get_current_workspace_folder():
    """
    Get the current workspace folder configuration.
    
    Returns:
        Current folder information or null if not configured
    """
    if not WORKSPACE_CONFIG_PATH.exists():
        return {
            "folder_id": None,
            "folder_name": None,
            "folder_url": None
        }
    
    try:
        config_text = WORKSPACE_CONFIG_PATH.read_text()
        config = json.loads(config_text)
        
        return {
            "folder_id": config.get("folder_id"),
            "folder_name": config.get("folder_name"),
            "folder_url": config.get("folder_url")
        }
    except Exception as e:
        logger.warning(f"Failed to load workspace config: {e}")
        return {
            "folder_id": None,
            "folder_name": None,
            "folder_url": None
        }


@router.post("/google-workspace/create-folder")
async def create_workspace_folder(
    request: Request,
    folder_name: str = Query(..., description="Name of the folder to create"),
    parent_folder_id: Optional[str] = Query(None, description="Optional parent folder ID")
):
    """
    Create a new folder in Google Drive.
    If parent_folder_id is not provided, creates in Drive root.
    
    Args:
        folder_name: Name of the folder to create
        parent_folder_id: Optional parent folder ID (defaults to root)
    """
    if not WORKSPACE_TOKEN_PATH.exists():
        raise HTTPException(
            status_code=401,
            detail="Google Workspace not authenticated. Please enable integration first."
        )
    
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleRequest
        from googleapiclient.discovery import build
        
        creds = Credentials.from_authorized_user_file(
            str(WORKSPACE_TOKEN_PATH),
            WORKSPACE_SCOPES
        )
        
        # Refresh if needed
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
            with open(WORKSPACE_TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
        
        drive_service = build('drive', 'v3', credentials=creds)
        
        folder_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder"
        }
        
        if parent_folder_id:
            folder_metadata["parents"] = [parent_folder_id]
        
        folder = drive_service.files().create(
            body=folder_metadata,
            fields="id, name, webViewLink"
        ).execute()
        
        # Log action
        session_id = request.cookies.get("session_id")
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "workspace_folder_created",
            f"Created folder: {folder_name} ({folder.get('id')})",
            session_id=session_id
        )
        
        return {
            "id": folder.get('id'),
            "name": folder.get('name'),
            "url": folder.get('webViewLink')
        }
        
    except Exception as e:
        logger.error(f"Failed to create folder: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create folder: {str(e)}"
        )


# 1C OData integration endpoints
@router.post("/onec/config")
async def save_onec_config_endpoint(
    request: Request,
    config: Dict[str, Any]
):
    """
    Save 1C OData configuration.
    
    Expected payload:
    {
        "odata_base_url": "https://...",
        "username": "...",
        "password": "...",
        "organization_guid": "..." (optional)
    }
    """
    try:
        # #region debug log
        import json
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"test","hypothesisId":"A","location":"integration_routes.py:save_onec_config_endpoint:entry","message":"save_onec_config called","data":{"odata_base_url":config.get("odata_base_url",""),"url_length":len(config.get("odata_base_url","")),"url_starts_with_http":config.get("odata_base_url","").startswith(("http://","https://"))},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        onec_config = OneCConfig(**config)
        # #region debug log
        import json
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"test","hypothesisId":"A","location":"integration_routes.py:save_onec_config_endpoint:after_validation","message":"OneCConfig created","data":{"odata_base_url":onec_config.odata_base_url,"url_length":len(onec_config.odata_base_url)},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        save_onec_config(onec_config)
        
        # Log action
        session_id = request.cookies.get("session_id")
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "onec_config_saved",
            f"1C OData config saved: {onec_config.odata_base_url}",
            session_id=session_id
        )
        
        return {
            "success": True,
            "message": "1C configuration saved successfully"
        }
    except Exception as e:
        logger.error(f"Failed to save 1C config: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to save 1C configuration: {str(e)}"
        )


@router.get("/onec/config")
async def get_onec_config_endpoint(request: Request):
    """
    Get current 1C OData configuration.
    Returns config without password for security.
    """
    try:
        onec_config = get_onec_config()
        if not onec_config:
            return {
                "configured": False,
                "config": None
            }
        
        # Return config without password
        config_dict = onec_config.model_dump()
        config_dict["password"] = "***"  # Hide password
        return {
            "configured": True,
            "config": config_dict
        }
    except Exception as e:
        logger.error(f"Failed to get 1C config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get 1C configuration: {str(e)}"
        )


@router.post("/onec/test")
async def test_onec_connection(request: Request):
    """
    Test 1C OData connection by calling $metadata endpoint.
    """
    try:
        onec_config = get_onec_config()
        # #region debug log
        import json
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"test","hypothesisId":"C","location":"integration_routes.py:test_onec_connection:config_loaded","message":"onec_config loaded","data":{"config_exists":onec_config is not None,"odata_base_url":onec_config.odata_base_url if onec_config else None,"url_length":len(onec_config.odata_base_url) if onec_config else 0},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        if not onec_config:
            raise HTTPException(
                status_code=400,
                detail="1C configuration not found. Please configure 1C OData connection first."
            )
        
        # Test connection by calling $metadata
        import httpx
        import base64
        
        # Prepare Basic Auth
        credentials = f"{onec_config.username}:{onec_config.password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        metadata_url = f"{onec_config.odata_base_url}/$metadata"
        # #region debug log
        import json
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"test","hypothesisId":"C","location":"integration_routes.py:test_onec_connection:before_request","message":"About to make HTTP request","data":{"metadata_url":metadata_url,"base_url":onec_config.odata_base_url,"url_constructed":f"{onec_config.odata_base_url}/$metadata"},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                metadata_url,
                headers={
                    "Authorization": f"Basic {encoded_credentials}",
                    "Accept": "application/json"
                }
            )
            # #region debug log
            import json
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"test","hypothesisId":"C","location":"integration_routes.py:test_onec_connection:response_received","message":"HTTP response received","data":{"status_code":response.status_code,"url_requested":str(response.request.url) if hasattr(response,'request') else metadata_url,"response_text_preview":response.text[:200] if response.text else None},"timestamp":int(__import__('time').time()*1000)})+'\n')
            # #endregion
            
            if response.status_code == 200:
                # Log action
                session_id = request.cookies.get("session_id")
                audit_logger = get_audit_logger()
                audit_logger.log_user_interaction(
                    "onec_connection_tested",
                    f"1C OData connection test successful: {onec_config.odata_base_url}",
                    session_id=session_id
                )
                
                return {
                    "connected": True,
                    "message": "Successfully connected to 1C OData endpoint"
                }
            else:
                return {
                    "connected": False,
                    "message": f"Connection failed with status {response.status_code}: {response.text[:200]}"
                }
                
    except httpx.TimeoutException as e:
        # #region debug log
        import json
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"test","hypothesisId":"C","location":"integration_routes.py:test_onec_connection:timeout","message":"Connection timeout","data":{"error":str(e)},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        raise HTTPException(
            status_code=408,
            detail="Connection timeout. Please check the OData URL and network connectivity."
        )
    except httpx.RequestError as e:
        # #region debug log
        import json
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"test","hypothesisId":"C","location":"integration_routes.py:test_onec_connection:request_error","message":"Request error","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        raise HTTPException(
            status_code=500,
            detail=f"Connection error: {str(e)}"
        )
    except Exception as e:
        # #region debug log
        import json
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"test","hypothesisId":"C","location":"integration_routes.py:test_onec_connection:exception","message":"Failed to test 1C connection","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(__import__('time').time()*1000)})+'\n')
        # #endregion
        logger.error(f"Failed to test 1C connection: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test 1C connection: {str(e)}"
        )


@router.get("/onec/status")
async def get_onec_status(request: Request):
    """
    Get 1C integration status.
    """
    onec_config = get_onec_config()
    
    return {
        "enabled": onec_config is not None,
        "configured": onec_config is not None,
        "config_exists": onec_config is not None
    }

