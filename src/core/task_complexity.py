"""
TaskComplexityAnalyzer - определяет сложность задачи для выбора budget_tokens и модели.

Цель: адаптивно выбирать модель и budget_tokens на основе сложности задачи,
чтобы простые задачи выполнялись быстро, а сложные - качественно.
"""
import re
from dataclasses import dataclass
from typing import Literal


@dataclass
class TaskComplexity:
    """Результат анализа сложности задачи."""
    level: Literal["simple", "medium", "complex"]
    budget_tokens: int
    estimated_duration_sec: int
    use_fast_model: bool


class TaskComplexityAnalyzer:
    """Определяет сложность задачи для выбора budget_tokens и модели."""
    
    # Паттерны для простых задач (одно действие, простой запрос)
    SIMPLE_PATTERNS = [
        r"назначь\s+встречу",
        r"создай\s+встречу",
        r"запланируй\s+встречу",
        r"отправь\s+письмо",
        r"напиши\s+письмо",
        r"покажи\s+встречи",
        r"покажи\s+письма",
        r"список\s+встреч",
        r"список\s+писем",
    ]
    
    # Паттерны для сложных задач (множественные действия, анализ, сравнение)
    COMPLEX_PATTERNS = [
        r"проанализируй\s+.+\s+и\s+.+",
        r"сравни\s+.+\s+с\s+.+",
        r"сравни\s+.+\s+и\s+.+",
        r"создай\s+план",
        r"создай\s+отчёт",
        r"найди\s+.+\s+и\s+.+\s+и\s+.+",  # Три действия
        r"проанализируй\s+.+\s+и\s+.+\s+и\s+.+",
    ]
    
    # Ключевые слова для определения сложности
    COMPLEX_KEYWORDS = [
        "проанализируй", "сравни", "создай план", "создай отчёт",
        "объедини", "сопоставь", "сделай анализ"
    ]
    
    # Ключевые слова для средних задач
    MEDIUM_KEYWORDS = [
        "и покажи", "и отправь", "и создай", "с деталями", "с вложением"
    ]
    
    # Количество действий (по союзам "и", "затем", "потом")
    ACTION_SEPARATORS = [r"\s+и\s+", r"\s+затем\s+", r"\s+потом\s+", r"\s+далее\s+"]
    
    def analyze(self, goal: str) -> TaskComplexity:
        """
        Анализирует сложность задачи.
        
        Args:
            goal: Цель задачи
            
        Returns:
            TaskComplexity с полями:
            - level: 'simple' | 'medium' | 'complex'
            - budget_tokens: 0 | 1500 | 2000-3000
            - estimated_duration_sec: 3 | 6 | 12
            - use_fast_model: bool
        """
        if not goal or not goal.strip():
            # Пустая задача - считаем простой
            return TaskComplexity(
                level="simple",
                budget_tokens=0,
                estimated_duration_sec=3,
                use_fast_model=True
            )
        
        goal_lower = goal.lower()
        
        # Подсчитываем количество действий (по разделителям)
        action_count = 1  # Минимум одно действие
        for separator in self.ACTION_SEPARATORS:
            matches = len(re.findall(separator, goal_lower))
            action_count += matches
        
        # Проверяем сложные паттерны
        is_complex = False
        for pattern in self.COMPLEX_PATTERNS:
            if re.search(pattern, goal_lower):
                is_complex = True
                break
        
        # Проверяем сложные ключевые слова
        if not is_complex:
            for keyword in self.COMPLEX_KEYWORDS:
                if keyword in goal_lower:
                    is_complex = True
                    break
        
        # Если много действий (3+), считаем сложной
        if action_count >= 3:
            is_complex = True
        
        # Проверяем простые паттерны
        is_simple = False
        if not is_complex:
            for pattern in self.SIMPLE_PATTERNS:
                if re.search(pattern, goal_lower):
                    is_simple = True
                    break
        
        # Проверяем средние паттерны (дополнительные параметры, но не множественные действия)
        is_medium = False
        if action_count == 2 or (action_count == 1 and any(keyword in goal_lower for keyword in ["с вложением", "с деталями", "и покажи", "и отправь"])):
            is_medium = True
        
        # Определяем уровень сложности
        if is_complex:
            level = "complex"
            budget_tokens = 2500  # Среднее значение между 2000 и 3000
            estimated_duration_sec = 12
            use_fast_model = False
        elif is_simple and action_count == 1 and not is_medium:
            level = "simple"
            budget_tokens = 0
            estimated_duration_sec = 3
            use_fast_model = True
        else:
            # Средняя сложность
            level = "medium"
            budget_tokens = 1500
            estimated_duration_sec = 6
            use_fast_model = False  # Для средних задач можно использовать среднюю модель
        
        return TaskComplexity(
            level=level,
            budget_tokens=budget_tokens,
            estimated_duration_sec=estimated_duration_sec,
            use_fast_model=use_fast_model
        )
