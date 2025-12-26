"""
Google authentication managers for Service Account and OAuth 2.0.
Handles credential management, token refresh, and authentication flows.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from src.utils.exceptions import AuthenticationError
from src.utils.config_loader import GoogleAuthConfig


class ServiceAccountAuth:
    """
    Service Account authentication for backend automation.
    Supports domain-wide delegation for impersonating users.
    """
    
    def __init__(
        self,
        service_account_path: Path,
        scopes: Optional[List[str]] = None,
        subject: Optional[str] = None  # User to impersonate
    ):
        """
        Initialize Service Account authentication.
        
        Args:
            service_account_path: Path to service account JSON key file
            scopes: List of OAuth scopes to request
            subject: Email of user to impersonate (for domain-wide delegation)
        """
        self.service_account_path = service_account_path
        self.scopes = scopes or [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/spreadsheets",
        ]
        self.subject = subject
        self._credentials: Optional[service_account.Credentials] = None
        
    @classmethod
    def from_config(
        cls,
        config: Optional[GoogleAuthConfig] = None,
        subject: Optional[str] = None
    ) -> "ServiceAccountAuth":
        """
        Create ServiceAccountAuth from configuration.
        
        Args:
            config: GoogleAuthConfig instance (uses global config if None)
            subject: User email to impersonate
            
        Returns:
            ServiceAccountAuth instance
            
        Raises:
            AuthenticationError: If service account path is not configured
        """
        if config is None:
            from src.utils.config_loader import get_config
            config = get_config().google_auth
            
        if not config.has_service_account():
            raise AuthenticationError(
                "Service account not configured. "
                "Please set GOOGLE_SERVICE_ACCOUNT_PATH in config/.env"
            )
        
        return cls(
            service_account_path=config.service_account_path,
            subject=subject
        )
    
    def get_credentials(self) -> service_account.Credentials:
        """
        Get or refresh service account credentials.
        
        Returns:
            Valid service account credentials
            
        Raises:
            AuthenticationError: If credentials cannot be loaded
        """
        if self._credentials is None or not self._credentials.valid:
            try:
                self._credentials = service_account.Credentials.from_service_account_file(
                    str(self.service_account_path),
                    scopes=self.scopes
                )
                
                if self.subject:
                    # Delegate domain-wide authority
                    self._credentials = self._credentials.with_subject(self.subject)
                    
            except Exception as e:
                raise AuthenticationError(
                    f"Failed to load service account credentials: {e}"
                ) from e
        
        # Refresh if needed
        if self._credentials.expired:
            self._credentials.refresh(Request())
            
        return self._credentials
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(HttpError)
    )
    def test_connection(self) -> bool:
        """
        Test the service account connection.
        
        Returns:
            True if connection is successful
            
        Raises:
            AuthenticationError: If connection fails
        """
        try:
            creds = self.get_credentials()
            service = build("gmail", "v1", credentials=creds)
            # Simple API call to test
            service.users().getProfile(userId="me").execute()
            return True
        except HttpError as e:
            if e.resp.status == 403:
                raise AuthenticationError(
                    "Service account lacks required permissions. "
                    "Check API enablement and IAM roles."
                ) from e
            raise AuthenticationError(f"Connection test failed: {e}") from e
        except Exception as e:
            raise AuthenticationError(f"Unexpected error during connection test: {e}") from e


class OAuthAuth:
    """
    OAuth 2.0 authentication for user-specific access.
    Handles authorization flow and token management.
    """
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: Optional[List[str]] = None,
        token_path: Optional[Path] = None
    ):
        """
        Initialize OAuth authentication.
        
        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: Redirect URI for OAuth callback
            scopes: List of OAuth scopes to request
            token_path: Path to store/load token (default: config/token.json)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes or [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/spreadsheets",
        ]
        self.token_path = token_path or Path("config/token.json")
        self._credentials: Optional[Credentials] = None
        
    @classmethod
    def from_config(
        cls,
        config: Optional[GoogleAuthConfig] = None,
        token_path: Optional[Path] = None
    ) -> "OAuthAuth":
        """
        Create OAuthAuth from configuration.
        
        Args:
            config: GoogleAuthConfig instance (uses global config if None)
            token_path: Path to store token
            
        Returns:
            OAuthAuth instance
            
        Raises:
            AuthenticationError: If OAuth credentials are not configured
        """
        if config is None:
            from src.utils.config_loader import get_config
            config = get_config().google_auth
            
        # OAuth is now required - config validation ensures these are present
        if not config.oauth_client_id or not config.oauth_client_secret:
            raise AuthenticationError(
                "OAuth credentials are required. "
                "Please set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in config/.env"
            )
        
        return cls(
            client_id=config.oauth_client_id,
            client_secret=config.oauth_client_secret,
            redirect_uri=config.oauth_redirect_uri,
            token_path=token_path
        )
    
    def get_authorization_url(self, state: Optional[str] = None, include_granted_scopes: bool = False) -> str:
        """
        Get the authorization URL for OAuth flow.
        
        Args:
            state: Optional state parameter for CSRF protection
            include_granted_scopes: If True, include previously granted scopes (can cause conflicts
                                   when requesting different scopes for different integrations)
            
        Returns:
            Authorization URL
        """
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = self.redirect_uri
        
        auth_kwargs = {
            "access_type": "offline",
            "prompt": "consent",  # Force consent screen to always get refresh_token
            "state": state
        }
        
        # Only include granted scopes if explicitly requested
        # For integrations (Gmail, Calendar, Sheets), we want separate tokens with specific scopes
        if include_granted_scopes:
            auth_kwargs["include_granted_scopes"] = "true"
        
        authorization_url, _ = flow.authorization_url(**auth_kwargs)
        
        return authorization_url
    
    def exchange_code_for_token(self, authorization_code: str) -> Credentials:
        """
        Exchange authorization code for access token.
        
        Args:
            authorization_code: Authorization code from OAuth callback
            
        Returns:
            OAuth credentials
            
        Raises:
            AuthenticationError: If token exchange fails
        """
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri],
                    }
                },
                scopes=self.scopes
            )
            flow.redirect_uri = self.redirect_uri
            
            flow.fetch_token(code=authorization_code)
            credentials = flow.credentials
            
            # Save token for future use
            self._save_token(credentials)
            self._credentials = credentials
            
            return credentials
            
        except Exception as e:
            raise AuthenticationError(f"Failed to exchange code for token: {e}") from e
    
    def get_credentials(self) -> Optional[Credentials]:
        """
        Get stored OAuth credentials.
        
        Returns:
            OAuth credentials if available, None otherwise
        """
        if self._credentials is None:
            self._credentials = self._load_token()
        
        if self._credentials is None:
            return None
        
        # Refresh if expired
        if self._credentials.expired and self._credentials.refresh_token:
            try:
                self._credentials.refresh(Request())
                self._save_token(self._credentials)
            except Exception as e:
                # Token refresh failed, user needs to re-authenticate
                self._credentials = None
                token_path = Path(self.token_path) if not isinstance(self.token_path, Path) else self.token_path
                if token_path.exists():
                    token_path.unlink()  # Remove invalid token
                raise AuthenticationError(
                    f"Token refresh failed. Please re-authenticate: {e}"
                ) from e
        
        return self._credentials
    
    def _load_token(self) -> Optional[Credentials]:
        """Load token from file."""
        # Ensure token_path is a Path object
        token_path = Path(self.token_path) if not isinstance(self.token_path, Path) else self.token_path
        
        if not token_path.exists():
            return None
        
        try:
            with open(token_path, "r") as f:
                token_data = json.load(f)
            return Credentials.from_authorized_user_info(token_data)
        except Exception as e:
            # Invalid token file, remove it
            token_path.unlink()
            return None
    
    def _save_token(self, credentials: Credentials) -> None:
        """Save token to file."""
        # Ensure token_path is a Path object
        token_path = Path(self.token_path) if not isinstance(self.token_path, Path) else self.token_path
        token_path.parent.mkdir(parents=True, exist_ok=True)
        
        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }
        
        with open(token_path, "w") as f:
            json.dump(token_data, f)
    
    def revoke_token(self) -> None:
        """Revoke and remove stored token."""
        if self._credentials:
            try:
                self._credentials.revoke(Request())
            except Exception:
                pass  # Ignore errors during revocation
        
        token_path = Path(self.token_path) if not isinstance(self.token_path, Path) else self.token_path
        if token_path.exists():
            token_path.unlink()
        
        self._credentials = None


class AuthManager:
    """
    Unified authentication manager using OAuth 2.0 only.
    All operations are performed on behalf of the authenticated user.
    """
    
    def __init__(self, oauth_auth: OAuthAuth):
        """
        Initialize authentication manager.
        
        Args:
            oauth_auth: OAuth authenticator (required)
        """
        if not oauth_auth:
            raise AuthenticationError("OAuth authenticator is required")
        self.oauth_auth = oauth_auth
    
    @classmethod
    def from_config(cls) -> "AuthManager":
        """
        Create AuthManager from global configuration.
        
        Returns:
            AuthManager instance
            
        Raises:
            AuthenticationError: If OAuth is not configured
        """
        from src.utils.config_loader import get_config
        
        config = get_config().google_auth
        
        try:
            oauth_auth = OAuthAuth.from_config(config)
        except Exception as e:
            raise AuthenticationError(
                "OAuth credentials are required. "
                "Please configure GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in config/.env"
            ) from e
        
        return cls(oauth_auth=oauth_auth)
    
    def get_credentials(self):
        """
        Get OAuth credentials for the authenticated user.
        
        Returns:
            Valid OAuth credentials
            
        Raises:
            AuthenticationError: If credentials are not available or expired
        """
        creds = self.oauth_auth.get_credentials()
        if not creds:
            raise AuthenticationError(
                "User not authenticated. Please complete OAuth flow first."
            )
        return creds
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Get authorization URL for OAuth flow.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL
        """
        return self.oauth_auth.get_authorization_url(state)
    
    def exchange_code_for_token(self, authorization_code: str) -> Credentials:
        """
        Exchange authorization code for access token.
        
        Args:
            authorization_code: Authorization code from OAuth callback
            
        Returns:
            OAuth credentials
        """
        return self.oauth_auth.exchange_code_for_token(authorization_code)

