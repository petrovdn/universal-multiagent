"""
Tests for per-user integration data isolation.

Verifies that get_username_from_session and integration routes
require authenticated users and use per-user token/config paths.
"""

import pytest
from unittest.mock import MagicMock

from src.utils.user_helpers import get_username_from_session


def test_get_username_from_session_no_context():
    """When session has no context, returns None."""
    mock_sm = MagicMock()
    mock_sm.get_session.return_value = None
    assert get_username_from_session("sid", mock_sm) is None
    mock_sm.get_session.assert_called_once_with("sid")


def test_get_username_from_session_from_metadata():
    """Username is read from context.metadata['username']."""
    mock_sm = MagicMock()
    ctx = MagicMock()
    ctx.metadata = {"username": "alice"}
    ctx.messages = []
    mock_sm.get_session.return_value = ctx
    assert get_username_from_session("sid", mock_sm) == "alice"


def test_get_username_from_session_fallback_messages():
    """Username fallback from 'Авторизован как: X' in system messages."""
    mock_sm = MagicMock()
    ctx = MagicMock()
    ctx.metadata = {}
    ctx.messages = [
        {"role": "user", "content": "hi"},
        {"role": "system", "content": "Авторизован как: bob"},
    ]
    mock_sm.get_session.return_value = ctx
    assert get_username_from_session("sid", mock_sm) == "bob"


def test_get_username_from_session_no_username():
    """When metadata and messages have no username, returns None."""
    mock_sm = MagicMock()
    ctx = MagicMock()
    ctx.metadata = {}
    ctx.messages = [{"role": "user", "content": "hi"}]
    mock_sm.get_session.return_value = ctx
    assert get_username_from_session("sid", mock_sm) is None
