"""
Conftest for chart_dashboard tests - mocks config_loader before imports.
"""
import sys
import os
from unittest.mock import MagicMock

# Mock config_loader BEFORE any imports
# Need to provide all config fields that might be accessed
mock_config_obj = MagicMock()
mock_config_obj.anthropic_api_key = 'test-key'
mock_config_obj.openai_api_key = 'test-key'
mock_config_obj.default_model = 'claude-3-haiku'
mock_config_obj.timezone = 'UTC'  # Required by calendar_agent
mock_config_obj.data_dir = '/tmp/test-data'
mock_config_obj.tokens_dir = '/tmp/test-tokens'
mock_config_obj.sessions_dir = '/tmp/test-sessions'

mock_config_module = MagicMock()
mock_config_module.get_config = MagicMock(return_value=mock_config_obj)
sys.modules['src.utils.config_loader'] = mock_config_module

# Set env vars
os.environ.setdefault('ANTHROPIC_API_KEY', 'test-key')
os.environ.setdefault('OPENAI_API_KEY', 'test-key')
os.environ.setdefault('DEFAULT_MODEL', 'claude-3-haiku')
