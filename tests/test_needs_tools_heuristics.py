"""
Tests for _needs_tools heuristics - should classify 80%+ queries without LLM.
"""
import pytest
from tests.conftest import (
    create_test_engine_with_mock_llm,
    mock_ws_manager,
    empty_context,
    mock_llm
)


class TestNeedsToolsHeuristics:
    """Тесты для эвристик _needs_tools без LLM fallback."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("query,expected", [
        # Должны определяться ЭВРИСТИКОЙ (без LLM) - нужны инструменты
        ("покажи встречи на завтра", True),
        ("найди письма от Иванова", True),
        ("создай таблицу с зарплатами", True),
        ("открой файл", True),
        ("получи данные из 1С", True),
        ("выведи статистику продаж", True),
        # Граничные случаи - должны определяться эвристикой
        ("статистика продаж за месяц", True),
        ("сравни показатели Q1 и Q2", True),
        ("составь отчет по проекту", True),
        ("проанализируй данные", True),
        ("подготовь презентацию", True),
        ("выгрузи данные", True),
        ("обнови таблицу", True),
        ("удали старые записи", True),
        # Должны определяться ЭВРИСТИКОЙ (без LLM) - НЕ нужны инструменты
        ("напиши хокку", False),
        ("привет", False),
        ("что ты умеешь", False),
        ("спасибо", False),
        ("объясни что такое AI", False),
        ("переведи на английский", False),
        ("перефразируй это предложение", False),
    ])
    async def test_heuristic_classification(self, query, expected, mock_ws_manager, empty_context, mock_llm):
        """
        Эвристика должна классифицировать без LLM.
        
        Эти запросы должны определяться эвристикой в _needs_tools,
        без необходимости вызывать LLM для классификации.
        """
        # Создаем mock LLM, который будет отслеживать вызовы
        engine = create_test_engine_with_mock_llm(mock_ws_manager, mock_llm)
        
        # Вызываем _needs_tools
        result = await engine._needs_tools(query, empty_context)
        
        # LLM НЕ должен вызываться для этих запросов (эвристика должна сработать)
        assert mock_llm.invoke_count == 0, (
            f"LLM was called {mock_llm.invoke_count} times for query '{query}', "
            f"but heuristic should have classified it. Expected: {expected}, Got: {result}"
        )
        
        # Результат должен соответствовать ожидаемому
        assert result == expected, (
            f"Query '{query}' classified incorrectly. Expected: {expected}, Got: {result}"
        )


@pytest.mark.asyncio
async def test_common_queries_no_llm_call(mock_ws_manager, empty_context, mock_llm):
    """
    90% обычных запросов должны классифицироваться без LLM.
    
    Этот тест проверяет, что для набора типичных запросов
    LLM не вызывается ни разу - все определяется эвристикой.
    """
    common_queries = [
        # Запросы, требующие инструментов
        "покажи встречи",
        "найди письма",
        "создай таблицу",
        "открой файл",
        "получи данные",
        "статистика продаж",
        "сравни показатели",
        "составь отчет",
        "проанализируй данные",
        # Простые запросы без инструментов
        "напиши стих",
        "привет",
        "спасибо",
        "что ты умеешь",
        "объясни что такое AI",
    ]
    
    engine = create_test_engine_with_mock_llm(mock_ws_manager, mock_llm)
    
    # Классифицируем все запросы
    for query in common_queries:
        await engine._needs_tools(query, empty_context)
    
    # LLM НЕ должен вызываться ни разу
    assert mock_llm.invoke_count == 0, (
        f"LLM was called {mock_llm.invoke_count} times for common queries, "
        f"but should have been 0. All queries should be classified by heuristics."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "статистика продаж за месяц",
    "сравни показатели Q1 и Q2",
    "составь отчет по проекту",
    "проанализируй данные за прошлый год",
    "подготовь презентацию для клиента",
    "выгрузи данные в Excel",
    "обнови таблицу с новыми значениями",
    "удали старые записи из базы",
    "скопируй данные из одной таблицы в другую",
])
async def test_new_keywords_classified_correctly(query, mock_ws_manager, empty_context, mock_llm):
    """
    Новые ключевые слова должны правильно классифицироваться как нуждающиеся в инструментах.
    
    Эти запросы содержат новые ключевые слова, которые мы добавляем в tool_keywords_early:
    - статистик, отчет, сравни, проанализируй, подготовь, выгрузи, обнови, удали, скопируй
    """
    engine = create_test_engine_with_mock_llm(mock_ws_manager, mock_llm)
    
    result = await engine._needs_tools(query, empty_context)
    
    # Должны требовать инструменты
    assert result is True, f"Query '{query}' should require tools, but got {result}"
    
    # LLM не должен вызываться
    assert mock_llm.invoke_count == 0, (
        f"LLM was called for query '{query}', but new keywords should be in heuristics"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "объясни что такое AI",
    "переведи на английский",
    "перефразируй это предложение",
    "суммируй основные идеи",
    "ответь на вопрос о Python",
])
async def test_new_simple_patterns_classified_correctly(query, mock_ws_manager, empty_context, mock_llm):
    """
    Новые простые паттерны должны правильно классифицироваться как НЕ нуждающиеся в инструментах.
    
    Эти запросы содержат новые паттерны в simple_generative_patterns:
    - объясни, переведи, перефразируй, суммируй (без файлов), ответь на вопрос
    """
    engine = create_test_engine_with_mock_llm(mock_ws_manager, mock_llm)
    
    result = await engine._needs_tools(query, empty_context)
    
    # НЕ должны требовать инструменты
    assert result is False, f"Query '{query}' should NOT require tools, but got {result}"
    
    # LLM не должен вызываться
    assert mock_llm.invoke_count == 0, (
        f"LLM was called for query '{query}', but new patterns should be in heuristics"
    )
