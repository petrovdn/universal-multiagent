"""
Conftest for sheets_read_all tests - mocks config_loader before imports.
"""
import sys
import os
from unittest.mock import MagicMock

# Mock config_loader BEFORE any imports
mock_config_obj = MagicMock(
    anthropic_api_key='test-key',
    openai_api_key='test-key',
    default_model='claude-3-haiku'
)

mock_config_module = MagicMock()
mock_config_module.get_config = MagicMock(return_value=mock_config_obj)
sys.modules['src.utils.config_loader'] = mock_config_module

# Set env vars
os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key')
os.environ.setdefault('OPENAI_API_KEY', 'test-key')
os.environ.setdefault('DEFAULT_MODEL', 'claude-3-haiku')
