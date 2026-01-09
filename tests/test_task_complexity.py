"""
Tests for TaskComplexityAnalyzer - определяет сложность задачи для выбора budget_tokens и модели.
"""
import pytest
from src.core.task_complexity import TaskComplexityAnalyzer, TaskComplexity


def test_simple_task_classification():
    """
    TaskComplexityAnalyzer должен правильно классифицировать простые задачи.
    """
    analyzer = TaskComplexityAnalyzer()
    
    simple_tasks = [
        "назначь встречу на завтра",
        "отправь письмо Ивану",
        "покажи встречи",
        "покажи письма",
    ]
    
    for goal in simple_tasks:
        complexity = analyzer.analyze(goal)
        assert complexity.level == "simple", (
            f"Task '{goal}' should be classified as 'simple', got '{complexity.level}'"
        )
        assert complexity.budget_tokens == 0, (
            f"Simple task should have budget_tokens=0, got {complexity.budget_tokens}"
        )
        assert complexity.use_fast_model is True, (
            f"Simple task should use fast model, got {complexity.use_fast_model}"
        )


def test_complex_task_classification():
    """
    TaskComplexityAnalyzer должен правильно классифицировать сложные задачи.
    """
    analyzer = TaskComplexityAnalyzer()
    
    complex_tasks = [
        "проанализируй встречи и письма и создай отчёт",
        "сравни данные из таблицы с данными из 1С",
        "создай план работы на неделю с детализацией",
        "найди все письма от Ивана, проанализируй их и создай сводку",
    ]
    
    for goal in complex_tasks:
        complexity = analyzer.analyze(goal)
        assert complexity.level == "complex", (
            f"Task '{goal}' should be classified as 'complex', got '{complexity.level}'"
        )
        assert complexity.budget_tokens >= 2000, (
            f"Complex task should have budget_tokens >= 2000, got {complexity.budget_tokens}"
        )
        assert complexity.use_fast_model is False, (
            f"Complex task should not use fast model, got {complexity.use_fast_model}"
        )


def test_medium_task_classification():
    """
    TaskComplexityAnalyzer должен правильно классифицировать средние задачи.
    """
    analyzer = TaskComplexityAnalyzer()
    
    medium_tasks = [
        "найди встречи на следующей неделе и покажи детали",
        "отправь письмо с вложением",
        "создай таблицу с данными из календаря",
    ]
    
    for goal in medium_tasks:
        complexity = analyzer.analyze(goal)
        assert complexity.level == "medium", (
            f"Task '{goal}' should be classified as 'medium', got '{complexity.level}'"
        )
        assert 0 < complexity.budget_tokens < 2000, (
            f"Medium task should have budget_tokens between 0 and 2000, got {complexity.budget_tokens}"
        )


def test_returns_correct_budget_tokens():
    """
    TaskComplexityAnalyzer должен возвращать правильные budget_tokens для каждого уровня сложности.
    """
    analyzer = TaskComplexityAnalyzer()
    
    # Simple
    simple = analyzer.analyze("назначь встречу")
    assert simple.budget_tokens == 0
    
    # Medium
    medium = analyzer.analyze("найди встречи и покажи детали")
    assert 1000 <= medium.budget_tokens <= 2000
    
    # Complex
    complex_task = analyzer.analyze("проанализируй все данные и создай отчёт")
    assert 2000 <= complex_task.budget_tokens <= 3000


def test_returns_correct_estimated_duration():
    """
    TaskComplexityAnalyzer должен возвращать оценочное время выполнения.
    """
    analyzer = TaskComplexityAnalyzer()
    
    # Simple - должно быть быстро (2-4 сек)
    simple = analyzer.analyze("назначь встречу")
    assert 2 <= simple.estimated_duration_sec <= 4, (
        f"Simple task estimated duration should be 2-4 sec, got {simple.estimated_duration_sec}"
    )
    
    # Medium - среднее время (5-8 сек)
    medium = analyzer.analyze("найди встречи и покажи")
    assert 5 <= medium.estimated_duration_sec <= 8, (
        f"Medium task estimated duration should be 5-8 sec, got {medium.estimated_duration_sec}"
    )
    
    # Complex - долгое время (10-15 сек)
    complex_task = analyzer.analyze("проанализируй и создай отчёт")
    assert 10 <= complex_task.estimated_duration_sec <= 15, (
        f"Complex task estimated duration should be 10-15 sec, got {complex_task.estimated_duration_sec}"
    )


def test_use_fast_model_flag():
    """
    TaskComplexityAnalyzer должен правильно устанавливать флаг use_fast_model.
    """
    analyzer = TaskComplexityAnalyzer()
    
    # Simple задачи должны использовать быструю модель
    simple = analyzer.analyze("покажи встречи")
    assert simple.use_fast_model is True
    
    # Complex задачи не должны использовать быструю модель
    complex_task = analyzer.analyze("проанализируй все данные")
    assert complex_task.use_fast_model is False


def test_edge_cases():
    """
    TaskComplexityAnalyzer должен корректно обрабатывать граничные случаи.
    """
    analyzer = TaskComplexityAnalyzer()
    
    # Очень короткая задача
    short = analyzer.analyze("привет")
    assert short.level in ["simple", "medium"], "Very short task should be simple or medium"
    
    # Очень длинная задача
    long_task = " ".join(["найди"] * 50 + ["встречи"])
    result = analyzer.analyze(long_task)
    assert result.level in ["simple", "medium", "complex"], "Long task should have valid level"
    
    # Пустая задача (не должна падать)
    empty = analyzer.analyze("")
    assert empty.level in ["simple", "medium"], "Empty task should default to simple or medium"
    assert empty.budget_tokens >= 0, "Budget tokens should be non-negative"


def test_multiple_keywords():
    """
    TaskComplexityAnalyzer должен учитывать несколько ключевых слов для определения сложности.
    """
    analyzer = TaskComplexityAnalyzer()
    
    # Задача с несколькими действиями должна быть complex
    multi_action = analyzer.analyze("найди встречи и отправь письмо и создай таблицу")
    assert multi_action.level == "complex", "Multi-action task should be complex"
    
    # Задача с "и" должна быть сложнее
    with_and = analyzer.analyze("найди встречи и покажи детали")
    simple = analyzer.analyze("найди встречи")
    
    # Задача с "и" должна быть сложнее или равна простой
    assert with_and.level in ["medium", "complex"] or (
        with_and.level == "simple" and simple.level == "simple"
    ), "Task with 'и' should be at least as complex as simple task"
