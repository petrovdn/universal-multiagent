"""
Test that common queries don't trigger LLM calls in _needs_tools.
"""
import pytest
from tests.conftest import (
    create_test_engine_with_mock_llm,
    mock_ws_manager,
    empty_context,
    mock_llm
)


@pytest.mark.asyncio
async def test_common_queries_no_llm_call(mock_ws_manager, empty_context, mock_llm):
    """
    90% обычных запросов должны классифицироваться без LLM.
    
    Проверяем, что для набора типичных запросов LLM не вызывается ни разу.
    """
    common_queries = [
        # Запросы, требующие инструментов
        "покажи встречи",
        "найди письма",
        "создай таблицу",
        "открой файл",
        "получи данные",
        # Простые запросы без инструментов
        "напиши стих",
        "привет",
        "спасибо",
    ]
    
    engine = create_test_engine_with_mock_llm(mock_ws_manager, mock_llm)
    
    for query in common_queries:
        await engine._needs_tools(query, empty_context)
    
    # LLM НЕ должен вызываться ни разу
    assert mock_llm.call_count == 0, (
        f"LLM was called {mock_llm.call_count} times, expected 0. "
        f"All {len(common_queries)} queries should be classified by heuristics."
    )
