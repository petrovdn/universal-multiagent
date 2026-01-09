"""
Model factory for creating LLM instances.
Supports multiple providers (Anthropic, OpenAI) and models.
"""

from typing import Dict, Any, Optional
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
import logging

from src.utils.config_loader import get_config

logger = logging.getLogger(__name__)


# Model configurations
MODELS: Dict[str, Dict[str, Any]] = {
    # Anthropic models
    "claude-sonnet-4-5": {
        "provider": "anthropic",
        "model_id": "claude-sonnet-4-5-20250929",
        "supports_reasoning": True,
        "reasoning_type": "extended_thinking",
        "supports_vision": True,
        "display_name": "Claude Sonnet 4.5"
    },
    "claude-3-haiku": {
        "provider": "anthropic",
        "model_id": "claude-3-haiku-20240307",
        "supports_reasoning": False,
        "reasoning_type": None,
        "supports_vision": True,
        "display_name": "Claude 3 Haiku",
        "speed_class": "fast"
    },
    "claude-3-5-sonnet": {
        "provider": "anthropic",
        "model_id": "claude-3-5-sonnet-20241022",
        "supports_reasoning": False,
        "reasoning_type": None,
        "supports_vision": True,
        "display_name": "Claude 3.5 Sonnet",
        "speed_class": "medium"
    },
    
    # OpenAI models
    "gpt-4o": {
        "provider": "openai",
        "model_id": "gpt-4o",
        "supports_reasoning": False,
        "reasoning_type": None,
        "supports_vision": True,
        "display_name": "GPT-4o"
    },
    "gpt-4o-mini": {
        "provider": "openai",
        "model_id": "gpt-4o-mini",
        "supports_reasoning": False,
        "reasoning_type": None,
        "supports_vision": True,
        "display_name": "GPT-4o Mini",
        "speed_class": "fast"
    },
    "o1": {
        "provider": "openai",
        "model_id": "o1",
        "supports_reasoning": True,
        "reasoning_type": "native",
        "supports_vision": False,
        "display_name": "OpenAI o1"
    }
}


def get_available_models() -> Dict[str, Dict[str, Any]]:
    """
    Get list of available models with their configurations.
    
    Returns:
        Dictionary mapping model IDs to their configurations
    """
    config = get_config()
    available = {}
    
    for model_id, model_config in MODELS.items():
        # Check if API key is available for the provider (must be non-empty string)
        if model_config["provider"] == "anthropic" and config.anthropic_api_key and config.anthropic_api_key.strip():
            available[model_id] = model_config
        elif model_config["provider"] == "openai" and config.openai_api_key and config.openai_api_key.strip():
            available[model_id] = model_config
    return available


def create_llm(model_name: str, api_keys: Optional[Dict[str, str]] = None) -> BaseChatModel:
    """
    Create LLM instance based on model name.
    
    Args:
        model_name: Model identifier (e.g., "claude-sonnet-4-5", "gpt-4o", "o1")
        api_keys: Optional dict with "anthropic" and/or "openai" keys.
                  If None, will use keys from config.
    
    Returns:
        Initialized LLM instance (ChatAnthropic or ChatOpenAI)
        
    Raises:
        ValueError: If model name is not supported or API key is missing
    """
    if model_name not in MODELS:
        raise ValueError(f"Unknown model: {model_name}. Supported models: {list(MODELS.keys())}")
    
    model_config = MODELS[model_name]
    config = get_config()
    
    # Use provided API keys or get from config
    if api_keys is None:
        api_keys = {
            "anthropic": config.anthropic_api_key,
            "openai": config.openai_api_key
        }
    
    if model_config["provider"] == "anthropic":
        if not api_keys.get("anthropic"):
            raise ValueError(f"Anthropic API key is required for model {model_name}")
        
        # Base parameters for all Anthropic models
        llm_params: Dict[str, Any] = {
            "model": model_config["model_id"],
            "api_key": api_keys["anthropic"],
            "streaming": True,  # Enable streaming for real-time token output
        }
        
        # Enable thinking only for models that support it (e.g., claude-sonnet-4-5)
        if model_config.get("supports_reasoning") and model_config.get("reasoning_type") == "extended_thinking":
            llm_params["temperature"] = 1  # Required for extended thinking
            llm_params["thinking"] = {  # Enable extended thinking for reasoning visibility
                "type": "enabled",
                "budget_tokens": 10000  # Allocate tokens for thinking
            }
        else:
            # Standard models without thinking
            llm_params["temperature"] = 1.0
        
        return ChatAnthropic(**llm_params)
    
    elif model_config["provider"] == "openai":
        if not api_keys.get("openai"):
            raise ValueError(f"OpenAI API key is required for model {model_name}")
        
        llm_params: Dict[str, Any] = {
            "model": model_config["model_id"],
            "api_key": api_keys["openai"],
            "streaming": True,
        }
        
        # o1 models have special requirements
        if model_name in ("o1", "o1-mini"):
            # o1 models don't support temperature or top_p
            # They use reasoning_effort parameter instead
            llm_params["reasoning_effort"] = "medium"  # low, medium, or high
            # Note: o1 reasoning is internal and not accessible via streaming
            # OpenAI o1 models perform reasoning internally but don't expose it through the API
            # Reasoning is not visible to users unlike Claude's extended thinking
        else:
            # For GPT-4o and other standard models
            llm_params["temperature"] = 1.0
        
        return ChatOpenAI(**llm_params)
    
    else:
        raise ValueError(f"Unsupported provider: {model_config['provider']}")


def get_model_info(model_name: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a model.
    
    Args:
        model_name: Model identifier
        
    Returns:
        Model configuration dict or None if not found
    """
    return MODELS.get(model_name)


def is_model_available(model_name: str) -> bool:
    """
    Check if a model is available (has required API key).
    
    Args:
        model_name: Model identifier
        
    Returns:
        True if model is available, False otherwise
    """
    if model_name not in MODELS:
        return False
    
    config = get_config()
    model_config = MODELS[model_name]
    
    if model_config["provider"] == "anthropic":
        return bool(config.anthropic_api_key and config.anthropic_api_key.strip())
    elif model_config["provider"] == "openai":
        return bool(config.openai_api_key and config.openai_api_key.strip())
    
    return False


def supports_vision(model_name: str) -> bool:
    """
    Check if model supports vision (images).
    
    Args:
        model_name: Model identifier
        
    Returns:
        True if model supports vision, False otherwise
    """
    model_config = MODELS.get(model_name)
    if not model_config:
        return False
    return model_config.get("supports_vision", False)

