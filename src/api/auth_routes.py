"""
Authentication routes for user authentication.
Supports both OAuth 2.0 (legacy) and simple username/password (for demo).
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Dict, Any, Optional
from pydantic import BaseModel
from pathlib import Path
import json
import secrets

from src.utils.google_auth import AuthManager
from src.utils.audit import get_audit_logger
from src.api.session_manager import get_session_manager

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Store OAuth state for CSRF protection
oauth_states: Dict[str, str] = {}

# Path to users file for demo authentication
# Try multiple possible paths
_current_dir = Path(__file__).parent
_possible_paths = [
    _current_dir.parent.parent / "config" / "users.json",  # From src/api/auth_routes.py
    Path.cwd() / "config" / "users.json",  # From project root
    Path("/Users/Dima/universal-multiagent/config/users.json"),  # Absolute path for development
]

USERS_FILE = None
for path in _possible_paths:
    if path.exists():
        USERS_FILE = path
        break

if USERS_FILE is None:
    # Use project root as fallback
    USERS_FILE = Path.cwd() / "config" / "users.json"

# Ensure users file directory exists
if not USERS_FILE.parent.exists():
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)


class LoginRequest(BaseModel):
    username: str
    password: str


class SimpleAuthManager:
    """Simple file-based authentication manager for demo."""
    
    def __init__(self, users_file: Path):
        self.users_file = users_file
        self._users: Optional[Dict[str, Dict[str, str]]] = None
    
    def _load_users(self, force_reload: bool = False) -> Dict[str, Dict[str, str]]:
        """Load users from file."""
        if self._users is not None and not force_reload:
            return self._users
        
        if not self.users_file.exists():
            # Create default users file if it doesn't exist
            default_users = {
                "admin": {
                    "password": "admin123",  # Plain text for demo
                    "username": "admin"
                },
                "demo": {
                    "password": "demo123",
                    "username": "demo"
                }
            }
            self.users_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(default_users, f, indent=2, ensure_ascii=False)
            self._users = default_users
            return self._users
        
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                self._users = json.load(f)
            return self._users
        except json.JSONDecodeError as e:
            from src.utils.logging_config import get_logger
            logger = get_logger(__name__)
            logger.error(f"Invalid JSON in users file {self.users_file}: {e}")
            raise ValueError(f"Invalid users file format: {str(e)}")
        except Exception as e:
            from src.utils.logging_config import get_logger
            logger = get_logger(__name__)
            logger.error(f"Failed to load users file {self.users_file}: {e}")
            raise RuntimeError(f"Failed to load users file: {str(e)}")
    
    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate user with username and password."""
        try:
            # Force reload to always check latest file
            users = self._load_users(force_reload=True)
            
            from src.utils.logging_config import get_logger
            logger = get_logger(__name__)
            logger.debug(f"Attempting authentication for user: {username}")
            logger.debug(f"Available users in file: {list(users.keys())}")
            
            if username not in users:
                logger.warning(f"User '{username}' not found in users file")
                return False
            
            # For demo: simple password comparison (plain text)
            # In production, use proper password hashing
            stored_password = users[username].get("password", "")
            # Strip whitespace from both for comparison
            password_match = stored_password.strip() == password.strip()
            
            if not password_match:
                logger.warning(f"Password mismatch for user '{username}'")
                logger.debug(f"Expected password length: {len(stored_password)}, Received length: {len(password)}")
            
            return password_match
        except Exception as e:
            from src.utils.logging_config import get_logger
            logger = get_logger(__name__)
            import traceback
            logger.error(f"Error in authenticate for user '{username}': {e}\n{traceback.format_exc()}")
            return False
    
    def get_user_info(self, username: str) -> Optional[Dict[str, str]]:
        """Get user information."""
        users = self._load_users()
        return users.get(username)


# Global simple auth manager
_simple_auth_manager: Optional[SimpleAuthManager] = None


def get_simple_auth_manager() -> SimpleAuthManager:
    """Get global simple auth manager."""
    global _simple_auth_manager
    
    if _simple_auth_manager is None:
        from src.utils.logging_config import get_logger
        logger = get_logger(__name__)
        
        try:
            logger.info(f"Initializing SimpleAuthManager with users file: {USERS_FILE}")
            logger.info(f"Users file exists: {USERS_FILE.exists() if USERS_FILE else False}")
            
            if USERS_FILE is None:
                raise ValueError("USERS_FILE is None - cannot initialize auth manager")
            
            _simple_auth_manager = SimpleAuthManager(USERS_FILE)
            # Test load on initialization
            try:
                users = _simple_auth_manager._load_users(force_reload=True)
                logger.info(f"Loaded {len(users)} users: {list(users.keys())}")
            except Exception as e:
                logger.error(f"Failed to load users on initialization: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
        except Exception as e:
            logger.error(f"Failed to initialize SimpleAuthManager: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    return _simple_auth_manager


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
    Logout user and clear session.
    Works for both OAuth and simple auth.
    """
    session_id = request.cookies.get("session_id")
    
    if session_id:
        # Get username before clearing
        session_manager = get_session_manager()
        context = session_manager.get_session(session_id)
        username = "unknown"
        if context:
            if hasattr(context, 'metadata') and context.metadata:
                username = context.metadata.get('username', 'unknown')
            else:
                # Try to get from messages
                for msg in reversed(context.messages):
                    if msg.get('role') == 'system' and 'Авторизован как:' in msg.get('content', ''):
                        username = msg.get('content', '').split('Авторизован как:')[-1].strip()
                        break
        
        # Try to revoke OAuth token if exists
        try:
            auth_manager = AuthManager.from_config()
            auth_manager.oauth_auth.revoke_token()
        except Exception:
            # Continue even if token revocation fails (might not be OAuth)
            pass
        
        # Clear session
        session_manager.delete_session(session_id)
        
        # Log logout
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "logout",
            f"User {username} logged out",
            session_id=session_id
        )
    
    response = JSONResponse({"status": "logged_out"})
    response.delete_cookie("session_id")
    return response


@router.post("/login")
async def simple_login(login_request: LoginRequest, request: Request):
    """
    Simple username/password login for demo.
    Creates or updates session with user info.
    """
    from src.utils.logging_config import get_logger
    logger = get_logger(__name__)
    
    # Log that we received the request
    logger.info(f"POST /auth/login received - username: {login_request.username}")
    
    try:
        auth_manager = get_simple_auth_manager()
        logger.info(f"Auth manager initialized, attempting authentication for: {login_request.username}")
        
        if not auth_manager.authenticate(login_request.username, login_request.password):
            logger.warning(f"Authentication failed for user: {login_request.username}")
            raise HTTPException(
                status_code=401,
                detail="Неверное имя пользователя или пароль"
            )
        
        logger.info(f"Authentication successful for user: {login_request.username}")
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except (ValueError, RuntimeError) as e:
        # Errors loading users file
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error loading users file: {e}\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка загрузки файла пользователей: {str(e)}"
        )
    except Exception as e:
        # Other unexpected errors
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Unexpected error during authentication: {e}\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка аутентификации: {str(e)}"
        )
    
    # Create or get session
    session_manager = get_session_manager()
    
    # Check if there's an existing session from cookies
    session_id = request.cookies.get("session_id")
    
    # Use existing session if valid, otherwise create new
    if session_id:
        context = session_manager.get_session(session_id)
        if not context:
            session_id = None  # Invalid session, create new
    
    if not session_id:
        session_id = session_manager.create_session()
    
    # Store username in session context
    context = session_manager.get_session(session_id)
    if context:
        context.add_message(
            "system",
            f"Авторизован как: {login_request.username}"
        )
        # Store username in metadata (create if doesn't exist)
        if not hasattr(context, 'metadata'):
            context.metadata = {}
        context.metadata['username'] = login_request.username
        session_manager.update_session(session_id, context)
    
    # Log authentication
    try:
        audit_logger = get_audit_logger()
        audit_logger.log_user_interaction(
            "login",
            f"User {login_request.username} logged in",
            session_id=session_id
        )
    except Exception as e:
        logger.warning(f"Failed to log authentication to audit log: {e}")
    
    response = JSONResponse({
        "status": "success",
        "session_id": session_id,
        "username": login_request.username
    })
    # Set cookie with proper attributes
    try:
        response.set_cookie(
            "session_id",
            session_id,
            httponly=True,
            samesite="lax",
            secure=False,  # Set to True in production with HTTPS
            max_age=86400 * 7  # 7 days
        )
        logger.info(f"Session cookie set for user {login_request.username}, session_id: {session_id}")
    except Exception as e:
        logger.error(f"Failed to set session cookie: {e}")
        # Still return success, cookie might be set by browser
    
    return response


@router.get("/me")
async def get_current_user(request: Request):
    """
    Get current authenticated user info.
    Works for both OAuth and simple auth.
    """
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session_manager = get_session_manager()
    context = session_manager.get_session(session_id)
    
    if not context:
        # Return 401 instead of 404 to indicate auth needed, not just session not found
        raise HTTPException(status_code=401, detail="Session not found or expired")
    
    username = "unknown"
    if hasattr(context, 'metadata') and context.metadata:
        username = context.metadata.get('username', 'unknown')
    else:
        # Try to get from messages
        for msg in reversed(context.messages):
            if msg.get('role') == 'system' and 'Авторизован как:' in msg.get('content', ''):
                username = msg.get('content', '').split('Авторизован как:')[-1].strip()
                break
    
    return {
        "username": username,
        "session_id": session_id
    }

