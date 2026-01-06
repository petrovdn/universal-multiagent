"""
Configuration loader with type-safe Pydantic models.
Loads and validates environment variables for the application.
"""

import os
import json
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
    """
Google authentication configuration (OAuth 2.0 only)."""
    
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
        """
Validate that OAuth credentials are provided."""
        # Allow placeholder values for development/testing
        if v and isinstance(v, str) and v.strip().startswith("your-"):
            return v.strip()
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("OAuth credentials are required")
        return v.strip()
    
    @classmethod
    def from_env(cls) -> "GoogleAuthConfig":
        """
Create GoogleAuthConfig from environment variables."""
        return cls(
            GOOGLE_OAUTH_CLIENT_ID=os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
            GOOGLE_OAUTH_CLIENT_SECRET=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            GOOGLE_OAUTH_REDIRECT_URI=os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
        )


class MCPServerConfig(BaseModel):
    """
    Configuration for a single MCP server."""
    
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


class OneCConfig(BaseModel):
    """
    Configuration for 1C:Бухгалтерия OData connection."""
    
    odata_base_url: str = Field(description="Base URL for OData endpoint (e.g., https://your-domain.1cfresh.com/odata/standard.odata)")
    username: str = Field(description="OData username")
    password: str = Field(description="OData password")
    organization_guid: Optional[str] = Field(default=None, description="Optional organization GUID for filtering")
    
    @field_validator("odata_base_url")
    @classmethod
    def validate_url(cls, v):
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("OData base URL is required")
        v = v.strip().rstrip('/')
        if not v.startswith(('http://', 'https://')):
            raise ValueError("OData base URL must start with http:// or https://")
        
        # Check if URL contains /odata/ - if not, it's likely incomplete
        original_url = v
        if '/odata/' not in v.lower():
            # Auto-append /odata/standard.odata if it's missing
            v = v.rstrip('/') + '/odata/standard.odata'
        
        return v
    
    @field_validator("username", "password")
    @classmethod
    def validate_credentials(cls, v):
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("Username and password are required")
        return v.strip()


class ProjectLadConfig(BaseModel):
    """
    Configuration for Project Lad API connection."""
    
    base_url: str = Field(description="Base URL for Project Lad API (e.g., https://api.staging.po.ladcloud.ru)")
    email: str = Field(description="Email for authentication")
    password: str = Field(description="Password for authentication")
    
    @field_validator("base_url")
    @classmethod
    def validate_url(cls, v):
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("Base URL is required")
        v = v.strip().rstrip('/')
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Base URL must start with http:// or https://")
        return v
    
    @field_validator("email", "password")
    @classmethod
    def validate_credentials(cls, v):
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("Email and password are required")
        return v.strip()


class MCPConfig(BaseModel):
    """
    MCP servers configuration."""
    
    gmail: MCPServerConfig
    calendar: MCPServerConfig
    sheets: MCPServerConfig
    google_workspace: MCPServerConfig
    docs: MCPServerConfig
    slides: MCPServerConfig
    onec: MCPServerConfig
    projectlad: MCPServerConfig
    
    @classmethod
    def from_env(cls) -> "MCPConfig":
        """
Create MCPConfig from environment variables."""
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
            docs=MCPServerConfig(
                name="docs",
                endpoint=os.getenv("DOCS_MCP_ENDPOINT", "http://localhost:9006"),
                transport=os.getenv("DOCS_MCP_TRANSPORT", "stdio"),  # stdio для локального Python сервера
                api_key=None,  # Не требуется для локального сервера
            ),
            slides=MCPServerConfig(
                name="slides",
                endpoint=os.getenv("SLIDES_MCP_ENDPOINT", "http://localhost:9007"),
                transport=os.getenv("SLIDES_MCP_TRANSPORT", "stdio"),  # stdio для локального Python сервера
                api_key=None,  # Не требуется для локального сервера
            ),
            onec=MCPServerConfig(
                name="onec",
                endpoint=os.getenv("ONEC_MCP_ENDPOINT", "http://localhost:9005"),
                transport=os.getenv("ONEC_MCP_TRANSPORT", "stdio"),  # stdio для локального Python сервера
                api_key=None,  # Не требуется для локального сервера
            ),
            projectlad=MCPServerConfig(
                name="projectlad",
                endpoint=os.getenv("PROJECTLAD_MCP_ENDPOINT", "http://localhost:9008"),
                transport=os.getenv("PROJECTLAD_MCP_TRANSPORT", "stdio"),  # stdio для локального Python сервера
                api_key=None,  # Не требуется для локального сервера
            ),
        )


class AppConfig(BaseSettings):
    """
Main application configuration."""
    
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
        """
Parse CORS origins raw string, handling empty/invalid values."""
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
    
    @model_validator(mode="before")
    @classmethod
    def exclude_properties_from_env(cls, values):
        """
Exclude properties from env parsing."""
        print(f"[DEBUG][MODEL_VALIDATOR] exclude_properties_from_env called with: {type(values)}", flush=True)
        if isinstance(values, dict):
            print(f"[DEBUG][MODEL_VALIDATOR] Keys before removal: {list(values.keys())[:10]}", flush=True)
            # Remove api_cors_origins from env values if present
            removed1 = values.pop("api_cors_origins", None)
            removed2 = values.pop("API_CORS_ORIGINS", None)
            print(f"[DEBUG][MODEL_VALIDATOR] Removed api_cors_origins: {removed1 is not None}, API_CORS_ORIGINS: {removed2 is not None}", flush=True)
        return values
    
    def __init__(self, **kwargs):
        """
Override __init__ to exclude api_cors_origins from kwargs."""
        print(f"[DEBUG][INIT] AppConfig.__init__ called with keys: {list(kwargs.keys())[:10] if kwargs else []}", flush=True)
        # Remove api_cors_origins before calling super().__init__
        kwargs.pop("api_cors_origins", None)
        kwargs.pop("API_CORS_ORIGINS", None)
        super().__init__(**kwargs)
    
    @property
    def api_cors_origins(self):
        """
Parse CORS origins from string to list."""
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
        """
Get directory for storing OAuth tokens."""
        return TOKENS_DIR
    
    @property
    def sessions_dir(self) -> Path:
        """
Get directory for storing sessions."""
        return SESSIONS_DIR
    
    @property
    def config_dir(self) -> Path:
        """
Get directory for configuration files."""
        return CONFIG_DIR
    
    @property
    def is_production(self) -> bool:
        """
Check if running in production environment."""
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
        try:
            print("[DEBUG][CONFIG] Calling AppConfig() constructor", flush=True)
            _config = AppConfig()
            print("[DEBUG][CONFIG] AppConfig created successfully", flush=True)
        except Exception as e:
            import traceback
            print(f"[DEBUG][CONFIG] Failed to create AppConfig: {e}", flush=True)
            print(f"[DEBUG][CONFIG] Traceback: {traceback.format_exc()}", flush=True)
            raise
        
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
    
    return _config


def reload_config() -> AppConfig:
    """
Reload configuration from environment."""
    global _config
    _config = None
    return get_config()


def get_onec_config() -> Optional[OneCConfig]:
    """
    Load 1C OData configuration from file.
    
    Returns:
        OneCConfig instance or None if config file doesn't exist
    """
    config = get_config()
    config_path = config.config_dir / "onec_config.json"
    
    if not config_path.exists():
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return OneCConfig(**data)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to load 1C config from {config_path}: {e}")
        return None


def save_onec_config(onec_config: OneCConfig) -> None:
    """
    Save 1C OData configuration to file.
    
    Args:
        onec_config: OneCConfig instance to save
    """
    config = get_config()
    config_path = config.config_dir / "onec_config.json"
    
    # Ensure config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # If password is empty or "***", load existing config and use its password
    if not onec_config.password or onec_config.password == "***":
        existing_config = get_onec_config()
        if existing_config and existing_config.password:
            onec_config.password = existing_config.password
    
    # Save config (password will be stored in plain text for demo purposes)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(onec_config.model_dump(), f, indent=2, ensure_ascii=False)
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"1C config saved to {config_path}")


def get_projectlad_config() -> Optional[ProjectLadConfig]:
    """
    Load Project Lad configuration from file.
    
    Returns:
        ProjectLadConfig instance or None if config file doesn't exist
    """
    config = get_config()
    config_path = config.config_dir / "projectlad_config.json"
    
    if not config_path.exists():
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return ProjectLadConfig(**data)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to load Project Lad config from {config_path}: {e}")
        return None


def save_projectlad_config(projectlad_config: ProjectLadConfig) -> None:
    """
    Save Project Lad configuration to file.
    
    Args:
        projectlad_config: ProjectLadConfig instance to save
    """
    config = get_config()
    config_path = config.config_dir / "projectlad_config.json"
    
    # Ensure config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # If password is empty or "***", load existing config and use its password
    if not projectlad_config.password or projectlad_config.password == "***":
        existing_config = get_projectlad_config()
        if existing_config and existing_config.password:
            projectlad_config.password = existing_config.password
    
    # Save config (password will be stored in plain text for demo purposes)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(projectlad_config.model_dump(), f, indent=2, ensure_ascii=False)
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Project Lad config saved to {config_path}")

