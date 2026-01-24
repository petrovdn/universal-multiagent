"""
Helpers for user identity resolution from session context.
"""

from typing import Optional, Any


def get_username_from_session(session_id: str, session_manager: Any) -> Optional[str]:
    """
    Извлечь username из session context.
    Возвращает None, если session не найдена или username не установлен.
    """
    context = session_manager.get_session(session_id)
    if not context:
        return None

    # Попробовать metadata
    if hasattr(context, "metadata") and context.metadata:
        username = context.metadata.get("username")
        if username:
            return username

    # Fallback: искать в messages
    for msg in reversed(context.messages):
        if msg.get("role") == "system" and "Авторизован как:" in msg.get("content", ""):
            username = msg.get("content", "").split("Авторизован как:")[-1].strip()
            if username:
                return username

    return None
