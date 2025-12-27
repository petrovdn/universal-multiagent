"""
Configuration loader with type-safe Pydantic models.
Loads and validates environment variables for the application.
"""

import os
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
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
        # #region agent log - RUNTIME DEBUG
        import sys
        client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
        client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
        redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
        print(f"[GOOGLE-AUTH-DEBUG] GOOGLE_OAUTH_CLIENT_ID exists: {bool(client_id)}, length: {len(client_id)}", flush=True)
        print(f"[GOOGLE-AUTH-DEBUG] GOOGLE_OAUTH_CLIENT_SECRET exists: {bool(client_secret)}, length: {len(client_secret)}", flush=True)
        sys.stdout.flush()
        # #endregion
        return cls(
            GOOGLE_OAUTH_CLIENT_ID=client_id,
            GOOGLE_OAUTH_CLIENT_SECRET=client_secret,
            GOOGLE_OAUTH_REDIRECT_URI=redirect_uri
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
        extra="ignore"
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
    api_cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000", "http://localhost:3001"],
        alias="API_CORS_ORIGINS"
    )
    
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
    
    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
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
    
    # #region agent log - RUNTIME DEBUG
    import sys
    print("[CONFIG-A] get_config() called", flush=True)
    sys.stdout.flush()
    # #endregion
    
    if _config is None:
        # #region agent log - RUNTIME DEBUG
        print("[CONFIG-B] Creating new AppConfig...", flush=True)
        sys.stdout.flush()
        # #endregion
        _config = AppConfig()
        # #region agent log - RUNTIME DEBUG
        print("[CONFIG-C] AppConfig created, creating directories...", flush=True)
        sys.stdout.flush()
        # #endregion
        
        # Ensure directories exist
        _config.tokens_dir.mkdir(parents=True, exist_ok=True)
        _config.sessions_dir.mkdir(parents=True, exist_ok=True)
        _config.config_dir.mkdir(parents=True, exist_ok=True)
        
        # #region agent log - RUNTIME DEBUG
        print("[CONFIG-D] Directories created, validating credentials...", flush=True)
        sys.stdout.flush()
        # #endregion
        
        # Validate required credentials
        missing = _config.validate_required_credentials()
        # #region agent log - RUNTIME DEBUG
        print(f"[CONFIG-E] Validation result - missing: {missing}", flush=True)
        sys.stdout.flush()
        # #endregion
        if missing:
            # #region agent log - RUNTIME DEBUG
            print(f"[CONFIG-ERROR] Missing credentials: {missing}", flush=True)
            sys.stdout.flush()
            # #endregion
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}. "
                f"Please check config/.env file or environment variables."
            )
        # #region agent log - RUNTIME DEBUG
        print("[CONFIG-F] get_config() SUCCESS - returning config", flush=True)
        sys.stdout.flush()
        # #endregion
    else:
        # #region agent log - RUNTIME DEBUG
        print("[CONFIG-G] Returning cached config", flush=True)
        sys.stdout.flush()
        # #endregion
    
    return _config


def reload_config() -> AppConfig:
    """Reload configuration from environment."""
    global _config
    _config = None
    return get_config()

