"""
OAuth 2.0 authentication routes for user authentication.
Handles OAuth flow and token management.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from typing import Dict, Any
import secrets

from src.utils.google_auth import AuthManager
from src.utils.audit import get_audit_logger
from src.api.session_manager import get_session_manager

router = APIRouter(prefix="/auth", tags=["authentication"])

# Store OAuth state for CSRF protection
oauth_states: Dict[str, str] = {}


@router.get("/login")
async def login(request: Request):
    """
    Initiate OAuth 2.0 login flow.
    Redirects user to Google OAuth consent screen.
    """
    try:
        auth_manager = AuthManager.from_config()
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        session_id = request.cookies.get("session_id")
        if not session_id:
            session_id = get_session_manager().create_session()
        
        oauth_states[session_id] = state
        
        # Get authorization URL
        auth_url = auth_manager.get_authorization_url(state)
        
        # Redirect to Google
        response = RedirectResponse(url=auth_url)
        response.set_cookie("session_id", session_id, httponly=True)
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate OAuth flow: {str(e)}"
        )


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    request: Request,
    error: str = None
):
    """
    OAuth 2.0 callback endpoint.
    Exchanges authorization code for access token.
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
    stored_state = oauth_states.get(session_id)
    if not stored_state or stored_state != state:
        raise HTTPException(
            status_code=400,
            detail="Invalid state parameter"
        )
    
    try:
        auth_manager = AuthManager.from_config()
        credentials = auth_manager.exchange_code_for_token(code)
        
        # Store credentials in session
        session_manager = get_session_manager()
        context = session_manager.get_session(session_id)
        if context:
            # Store user email in context
            from google.oauth2.credentials import Credentials
            if isinstance(credentials, Credentials):
                # Get user info
                from googleapiclient.discovery import build
                service = build("oauth2", "v2", credentials=credentials)
                user_info = service.userinfo().get().execute()
                context.add_message(
                    "system",
                    f"Authenticated as: {user_info.get('email')}"
                )
                session_manager.update_session(session_id, context)
        
        # Clean up state
        del oauth_states[session_id]
        
        # Log authentication
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "oauth_login",
            f"User authenticated successfully",
            session_id=session_id
        )
        
        # Redirect to frontend
        from src.api.integration_routes import get_frontend_url
        frontend_url = get_frontend_url()
        return RedirectResponse(
            url=f"{frontend_url}/?auth=success",
            status_code=302
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to complete OAuth flow: {str(e)}"
        )


@router.post("/logout")
async def logout(request: Request):
    """
    Logout user and revoke OAuth token.
    """
    session_id = request.cookies.get("session_id")
    if session_id:
        try:
            auth_manager = AuthManager.from_config()
            auth_manager.oauth_auth.revoke_token()
            
            # Clear session
            session_manager = get_session_manager()
            session_manager.delete_session(session_id)
            
            return {"status": "logged_out"}
        except Exception as e:
            # Continue even if token revocation fails
            pass
    
    return {"status": "logged_out"}

