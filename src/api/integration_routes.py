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

from src.utils.google_auth import AuthManager, OAuthAuth
from src.utils.config_loader import get_config
from src.utils.audit import get_audit_logger
from src.api.session_manager import get_session_manager

# Import Google API errors at module level
try:
    from googleapiclient.errors import HttpError
except ImportError:
    HttpError = Exception  # Fallback if not available

logger = logging.getLogger(__name__)

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
                    with open(WORKSPACE_CONFIG_PATH, 'r') as f:
                        config = json.load(f)
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
        calendar_redirect_uri = "http://localhost:8000/api/integrations/google-calendar/callback"
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
        calendar_redirect_uri = "http://localhost:8000/api/integrations/google-calendar/callback"
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
        return RedirectResponse(
            url="http://localhost:5173/?calendar_auth=success",
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
        gmail_redirect_uri = "http://localhost:8000/api/integrations/gmail/callback"
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
        return RedirectResponse(
            url=f"http://localhost:5173/?gmail_auth=error&error={error}",
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
        gmail_redirect_uri = "http://localhost:8000/api/integrations/gmail/callback"
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
        return RedirectResponse(
            url="http://localhost:5173/?gmail_auth=success",
            status_code=302
        )
        
    except Exception as e:
        logger.error(f"Failed to complete Gmail OAuth flow: {e}")
        return RedirectResponse(
            url=f"http://localhost:5173/?gmail_auth=error&error={str(e)}",
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


@router.post("/google-sheets/enable")
async def enable_sheets_integration(request: Request):
    """
    Enable Google Sheets integration.
    If not authenticated, initiates OAuth flow.
    
    Returns:
        - If authenticated: success status
        - If not authenticated: OAuth authorization URL
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
        sheets_redirect_uri = "http://localhost:8000/api/integrations/google-sheets/callback"
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
        return RedirectResponse(
            url=f"http://localhost:5173/?sheets_auth=error&error={error}",
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
        sheets_redirect_uri = "http://localhost:8000/api/integrations/google-sheets/callback"
        oauth_auth = OAuthAuth(
            client_id=config.google_auth.oauth_client_id,
            client_secret=config.google_auth.oauth_client_secret,
            redirect_uri=sheets_redirect_uri,
            scopes=SHEETS_SCOPES,
            token_path=SHEETS_TOKEN_PATH
        )
        
        # Exchange code for token
        credentials = oauth_auth.exchange_code_for_token(code)
        
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
        return RedirectResponse(
            url="http://localhost:5173/?sheets_auth=success",
            status_code=302
        )
        
    except Exception as e:
        logger.error(f"Failed to complete Google Sheets OAuth flow: {e}")
        return RedirectResponse(
            url=f"http://localhost:5173/?sheets_auth=error&error={str(e)}",
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
                    with open(WORKSPACE_CONFIG_PATH, 'r') as f:
                        config = json.load(f)
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
                        with open(WORKSPACE_CONFIG_PATH, 'r') as f:
                            config = json.load(f)
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
        workspace_redirect_uri = "http://localhost:8000/api/integrations/google-workspace/callback"
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
        workspace_redirect_uri = "http://localhost:8000/api/integrations/google-workspace/callback"
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
        return RedirectResponse(
            url="http://localhost:5173/?workspace_auth=success",
            status_code=302
        )
        
    except Exception as e:
        logger.error(f"Failed to complete Google Workspace OAuth flow: {e}")
        return RedirectResponse(
            url=f"http://localhost:5173/?workspace_auth=error&error={str(e)}",
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
    folder_id: str = Query(...),
    folder_name: Optional[str] = Query(None)
):
    """
    Set the workspace folder ID.
    
    Args:
        folder_id: Google Drive folder ID
        folder_name: Optional folder name (will be fetched if not provided)
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from googleapiclient.discovery import build
    
    if not WORKSPACE_TOKEN_PATH.exists():
        raise HTTPException(
            status_code=401,
            detail="Google Workspace not authenticated. Please enable integration first."
        )
    
    try:
        
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
        
        config_path = WORKSPACE_CONFIG_PATH._get_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
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
        
    except Exception as e:
        # Check if it's an HttpError from googleapiclient
        error_type = type(e).__name__
        if error_type == 'HttpError' or 'HttpError' in str(type(e)):
            logger.error(f"Failed to set workspace folder (HttpError): {e}", exc_info=True)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid folder ID or access denied: {str(e)}"
            )
        else:
            logger.error(f"Failed to set workspace folder: {e}", exc_info=True)
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
        with open(WORKSPACE_CONFIG_PATH, 'r') as f:
            config = json.load(f)
        
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
async def create_workspace_folder(request: Request, folder_name: str, parent_folder_id: Optional[str] = None):
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

