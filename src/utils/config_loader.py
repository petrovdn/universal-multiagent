"""
Configuration loader with type-safe Pydantic models.
Loads and validates environment variables for the application.
"""

import os
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv


# Load .env file if it exists
env_path = Path(__file__).parent.parent.parent / "config" / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Determine environment (dev or production)
APP_ENV = os.getenv("APP_ENV", "dev").lower()
IS_PRODUCTION = APP_ENV == "production"

# Base paths for data storage
if IS_PRODUCTION:
    # Production: use volume paths
    DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
    TOKENS_DIR = DATA_DIR / "tokens"
    SESSIONS_DIR = DATA_DIR / "sessions"
    CONFIG_DIR = Path("/app/config")
else:
    # Development: use local paths
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    DATA_DIR = PROJECT_ROOT / "data"
    TOKENS_DIR = PROJECT_ROOT / "config"
    SESSIONS_DIR = DATA_DIR / "sessions"
    CONFIG_DIR = PROJECT_ROOT / "config"


class GoogleAuthConfig(BaseModel):
    """Google authentication configuration (OAuth 2.0 only)."""
    
    oauth_client_id: str = Field(
        alias="GOOGLE_OAUTH_CLIENT_ID",
        description="OAuth 2.0 Client ID (required)"
    )
    oauth_client_secret: str = Field(
        alias="GOOGLE_OAUTH_CLIENT_SECRET",
        description="OAuth 2.0 Client Secret (required)"
    )
    oauth_redirect_uri: str = Field(
        default="http://localhost:8000/auth/callback",
        alias="GOOGLE_OAUTH_REDIRECT_URI"
    )
    
    @field_validator("oauth_client_id", "oauth_client_secret")
    @classmethod
    def validate_oauth_required(cls, v):
        """Validate that OAuth credentials are provided."""
        # Allow placeholder values for development/testing
        if v and isinstance(v, str) and v.strip().startswith("your-"):
            return v.strip()
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("OAuth credentials are required")
        return v.strip()
    
    @classmethod
    def from_env(cls) -> "GoogleAuthConfig":
        """Create GoogleAuthConfig from environment variables."""
        return cls(
            GOOGLE_OAUTH_CLIENT_ID=os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
            GOOGLE_OAUTH_CLIENT_SECRET=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            GOOGLE_OAUTH_REDIRECT_URI=os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
        )


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""
    
    name: str
    endpoint: str
    transport: str = Field(default="stdio")  # stdio, http, sse
    api_key: Optional[str] = None
    enabled: bool = True
    
    @field_validator("transport")
    @classmethod
    def validate_transport(cls, v):
        allowed = {"stdio", "http", "sse"}
        if v not in allowed:
            raise ValueError(f"Transport must be one of {allowed}")
        return v


class MCPConfig(BaseModel):
    """MCP servers configuration."""
    
    gmail: MCPServerConfig
    calendar: MCPServerConfig
    sheets: MCPServerConfig
    google_workspace: MCPServerConfig
    
    @classmethod
    def from_env(cls) -> "MCPConfig":
        """Create MCPConfig from environment variables."""
        return cls(
            gmail=MCPServerConfig(
                name="gmail",
                endpoint=os.getenv("GMAIL_MCP_ENDPOINT", "http://localhost:9001"),
                transport=os.getenv("GMAIL_MCP_TRANSPORT", "stdio"),
            ),
            calendar=MCPServerConfig(
                name="calendar",
                endpoint=os.getenv("CALENDAR_MCP_ENDPOINT", "http://localhost:9002"),
                transport=os.getenv("CALENDAR_MCP_TRANSPORT", "stdio"),  # stdio для локального Python сервера
                api_key=None,  # Не требуется для локального сервера
            ),
            sheets=MCPServerConfig(
                name="sheets",
                endpoint=os.getenv("SHEETS_MCP_ENDPOINT", "http://localhost:9003"),
                transport=os.getenv("SHEETS_MCP_TRANSPORT", "stdio"),  # stdio для локального Python сервера
                api_key=None,  # Не требуется для локального сервера
            ),
            google_workspace=MCPServerConfig(
                name="google_workspace",
                endpoint=os.getenv("WORKSPACE_MCP_ENDPOINT", "http://localhost:9004"),
                transport=os.getenv("WORKSPACE_MCP_TRANSPORT", "stdio"),  # stdio для локального Python сервера
                api_key=None,  # Не требуется для локального сервера
            ),
        )


class AppConfig(BaseSettings):
    """Main application configuration."""
    
    model_config = SettingsConfigDict(
        env_file="config/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,  # Ignore empty environment variables
        env_prefix=""  # No prefix for env vars
    )
    
    # Anthropic API
    anthropic_api_key: Optional[str] = Field(default="", alias="ANTHROPIC_API_KEY")
    
    # OpenAI API (новое)
    openai_api_key: Optional[str] = Field(default="", alias="OPENAI_API_KEY")
    
    # Model settings (новое)
    default_model: str = Field(default="gpt-4o", alias="DEFAULT_MODEL")
    
    # Application settings
    timezone: str = Field(default="Europe/Moscow", alias="APP_TIMEZONE")
    debug: bool = Field(default=False, alias="APP_DEBUG")
    log_level: str = Field(default="INFO", alias="APP_LOG_LEVEL")
    
    # FastAPI settings
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_cors_origins_raw: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://localhost:3001",
        alias="API_CORS_ORIGINS",
        validation_alias="API_CORS_ORIGINS"
    )
    
    @field_validator("api_cors_origins_raw", mode="before")
    @classmethod
    def parse_cors_origins_raw(cls, v):
        """Parse CORS origins raw string, handling empty/invalid values."""
        import logging
        logger = logging.getLogger(__name__)
        print(f"[DEBUG][CORS] parse_cors_origins_raw called with: type={type(v)}, value={repr(v)}", flush=True)
        
        if v is None:
            print("[DEBUG][CORS] Value is None, returning default", flush=True)
            return "http://localhost:5173,http://localhost:3000,http://localhost:3001"
        if isinstance(v, str):
            v = v.strip()
            if not v:
                print("[DEBUG][CORS] Value is empty string, returning default", flush=True)
                return "http://localhost:5173,http://localhost:3000,http://localhost:3001"
            print(f"[DEBUG][CORS] Returning string value: {v}", flush=True)
            return v
        # For any other type, convert to string
        result = str(v) if v else "http://localhost:5173,http://localhost:3000,http://localhost:3001"
        print(f"[DEBUG][CORS] Converted non-string to string: {result}", flush=True)
        return result
    
    @property
    def api_cors_origins(self) -> List[str]:
        """Parse CORS origins from string to list."""
        v = self.api_cors_origins_raw
        # Handle None or empty string
        if not v or not v.strip():
            return ["http://localhost:5173", "http://localhost:3000", "http://localhost:3001"]
        
        v = v.strip()
        
        # Try to parse as JSON first (for Railway env vars that might be JSON)
        try:
            import json
            parsed = json.loads(v)
            if isinstance(parsed, list):
                result = [str(origin).strip() for origin in parsed if origin and str(origin).strip()]
                return result if result else ["http://localhost:5173", "http://localhost:3000", "http://localhost:3001"]
            elif isinstance(parsed, str):
                # If it's a JSON string, treat as comma-separated
                origins = [origin.strip() for origin in parsed.split(",") if origin.strip()]
                return origins if origins else ["http://localhost:5173", "http://localhost:3000", "http://localhost:3001"]
        except (json.JSONDecodeError, ValueError, TypeError):
            # Not JSON, treat as comma-separated string
            pass
        
        # Parse as comma-separated string
        origins = [origin.strip() for origin in v.split(",") if origin.strip()]
        return origins if origins else ["http://localhost:5173", "http://localhost:3000", "http://localhost:3001"]
    
    # Session settings
    session_timeout_minutes: int = Field(default=30, alias="SESSION_TIMEOUT_MINUTES")
    max_sessions_per_user: int = Field(default=10, alias="MAX_SESSIONS_PER_USER")
    
    # Rate limiting
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    max_api_calls_per_message: int = Field(default=5, alias="MAX_API_CALLS_PER_MESSAGE")
    
    # Google Auth
    google_auth: GoogleAuthConfig = Field(default_factory=GoogleAuthConfig.from_env)
    
    # MCP Config
    mcp: MCPConfig = Field(default_factory=MCPConfig.from_env)
    
    # Storage paths (computed properties)
    @property
    def tokens_dir(self) -> Path:
        """Get directory for storing OAuth tokens."""
        return TOKENS_DIR
    
    @property
    def sessions_dir(self) -> Path:
        """Get directory for storing sessions."""
        return SESSIONS_DIR
    
    @property
    def config_dir(self) -> Path:
        """Get directory for configuration files."""
        return CONFIG_DIR
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return IS_PRODUCTION
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v.upper()
    
    
    def validate_required_credentials(self) -> List[str]:
        """
        Validate that required credentials are present.
        
        Returns:
            List of missing credential names (empty if all present)
        """
        missing = []
        
        # At least one API key should be present (Anthropic or OpenAI)
        if not self.anthropic_api_key and not self.openai_api_key:
            missing.append("At least one API key is required (ANTHROPIC_API_KEY or OPENAI_API_KEY)")
        
        # OAuth is now required
        if not self.google_auth.oauth_client_id or not self.google_auth.oauth_client_secret:
            missing.append("Google OAuth credentials (GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)")
        
        return missing


# Global config instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """
    Get the global application configuration.
    
    Returns:
        AppConfig instance
        
    Raises:
        ValueError: If required configuration is missing
    """
    global _config
    
    if _config is None:
        print("[DEBUG][CONFIG] Creating new AppConfig instance", flush=True)
        # #region agent log
        try:
            import os
            import json
            import time
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"location": "config_loader.py:250", "message": "Creating AppConfig instance", "data": {"env_anthropic_set": bool(os.getenv("ANTHROPIC_API_KEY")), "env_openai_set": bool(os.getenv("OPENAI_API_KEY")), "env_anthropic_len": len(os.getenv("ANTHROPIC_API_KEY", "")), "env_openai_len": len(os.getenv("OPENAI_API_KEY", ""))}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}) + "\n")
        except: pass
        # #endregion
        
        try:
            print("[DEBUG][CONFIG] Calling AppConfig() constructor", flush=True)
            _config = AppConfig()
            print("[DEBUG][CONFIG] AppConfig created successfully", flush=True)
        except Exception as e:
            import traceback
            print(f"[DEBUG][CONFIG] Failed to create AppConfig: {e}", flush=True)
            print(f"[DEBUG][CONFIG] Traceback: {traceback.format_exc()}", flush=True)
            raise
        
        # #region agent log
        try:
            import json
            import time
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"location": "config_loader.py:253", "message": "AppConfig created, checking API keys", "data": {"anthropic_key_exists": bool(_config.anthropic_api_key), "anthropic_key_len": len(_config.anthropic_api_key) if _config.anthropic_api_key else 0, "anthropic_key_stripped_len": len(_config.anthropic_api_key.strip()) if _config.anthropic_api_key else 0, "openai_key_exists": bool(_config.openai_api_key), "openai_key_len": len(_config.openai_api_key) if _config.openai_api_key else 0, "openai_key_stripped_len": len(_config.openai_api_key.strip()) if _config.openai_api_key else 0}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "run1", "hypothesisId": "B"}) + "\n")
        except: pass
        # #endregion
        
        # Ensure directories exist
        _config.tokens_dir.mkdir(parents=True, exist_ok=True)
        _config.sessions_dir.mkdir(parents=True, exist_ok=True)
        _config.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Validate required credentials (but don't fail startup - allow healthcheck to work)
        missing = _config.validate_required_credentials()
        if missing:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"Missing configuration: {', '.join(missing)}. "
                f"Some features may not work. Please check environment variables."
            )
            # Log API key status for debugging (without exposing keys)
            has_anthropic = bool(_config.anthropic_api_key and _config.anthropic_api_key.strip())
            has_openai = bool(_config.openai_api_key and _config.openai_api_key.strip())
            logger.info(f"API keys status: Anthropic={'set' if has_anthropic else 'missing'}, OpenAI={'set' if has_openai else 'missing'}")
        
        # #region agent log
        try:
            import json
            import time
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"location": "config_loader.py:275", "message": "Config validation complete", "data": {"missing_count": len(missing), "has_anthropic": bool(_config.anthropic_api_key and _config.anthropic_api_key.strip()), "has_openai": bool(_config.openai_api_key and _config.openai_api_key.strip())}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "run1", "hypothesisId": "C"}) + "\n")
        except: pass
        # #endregion
    
    return _config


def reload_config() -> AppConfig:
    """Reload configuration from environment."""
    global _config
    _config = None
    return get_config()

