"""
TDD tests for SkillSelector - Phase 2.2.

These tests should FAIL initially (Red phase), then pass after implementation (Green phase).
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

# Handle numpy import issues in sandbox
try:
    import numpy as np
    HAS_NUMPY = True
except (ImportError, OSError):
    HAS_NUMPY = False

# Mock config before imports
import sys
import os
os.environ.setdefault('OPENAI_API_KEY', 'test-key')

mock_config_obj = MagicMock()
mock_config_obj.openai_api_key = "test-key"
mock_config_loader = MagicMock()
mock_config_loader.get_config = MagicMock(return_value=mock_config_obj)
sys.modules['src.utils.config_loader'] = mock_config_loader

from src.core.skills.skill_loader import Skill, SkillLoader


@pytest.fixture
def temp_skills_dir():
    """Create temporary directory for skills."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_cache_dir():
    """Create temporary directory for embedding cache."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_skills(temp_skills_dir):
    """Create sample skills for testing."""
    # Skill 1: slides-formatting
    slides_md = """---
name: slides-formatting
description: >
  Продвинутое форматирование презентаций Google Slides. Используй когда 
  пользователь просит создать красивую презентацию, оформить слайды.
metadata:
  version: "1.0"
  category: formatting
---

## Когда активировать

Ключевые слова: "презентация", "слайды", "оформить", "красиво"
"""
    
    slides_dir = temp_skills_dir / "slides-formatting"
    slides_dir.mkdir()
    (slides_dir / "SKILL.md").write_text(slides_md, encoding="utf-8")
    
    # Skill 2: sheets-analysis
    sheets_md = """---
name: sheets-analysis
description: >
  Анализ данных в Google Sheets. Используй когда пользователь просит 
  проанализировать таблицу, построить графики, найти закономерности.
metadata:
  version: "1.0"
  category: analysis
---

## Когда активировать

Ключевые слова: "таблица", "анализ", "график", "данные"
"""
    
    sheets_dir = temp_skills_dir / "sheets-analysis"
    sheets_dir.mkdir()
    (sheets_dir / "SKILL.md").write_text(sheets_md, encoding="utf-8")
    
    # Skill 3: calendar-scheduling
    calendar_md = """---
name: calendar-scheduling
description: >
  Планирование встреч в календаре. Используй когда пользователь просит 
  запланировать встречу, найти свободное время, создать событие.
metadata:
  version: "1.0"
  category: scheduling
---

## Когда активировать

Ключевые слова: "встреча", "календарь", "запланировать", "событие"
"""
    
    calendar_dir = temp_skills_dir / "calendar-scheduling"
    calendar_dir.mkdir()
    (calendar_dir / "SKILL.md").write_text(calendar_md, encoding="utf-8")
    
    return temp_skills_dir


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for embeddings."""
    mock_client = MagicMock()
    
    def create_embedding_side_effect(model, input):
        mock_response = MagicMock()
        input_lower = input.lower()
        
        # Создаем более реалистичные embeddings с разными паттернами
        # Презентации - паттерн: первые 200 элементов = 0.8, следующие 200 = 0.6, остальные = 0.1
        if "презентац" in input_lower or "слайд" in input_lower or "slides" in input_lower or "красив" in input_lower:
            embedding = [0.8] * 200 + [0.6] * 200 + [0.1] * 1136
        # Таблицы/анализ - паттерн: первые 200 элементов = 0.7, следующие 200 = 0.5, остальные = 0.2
        elif "таблиц" in input_lower or "sheets" in input_lower or "анализ" in input_lower or "график" in input_lower or "проанализ" in input_lower:
            embedding = [0.7] * 200 + [0.5] * 200 + [0.2] * 1136
        # Календарь - паттерн: первые 200 элементов = 0.6, следующие 200 = 0.4, остальные = 0.3
        elif "календар" in input_lower or "calendar" in input_lower or "встреч" in input_lower or "запланир" in input_lower:
            embedding = [0.6] * 200 + [0.4] * 200 + [0.3] * 1136
        # Нерелевантные запросы (стихи и т.д.) - паттерн: первые 200 = -0.5, следующие 200 = -0.3, остальные = 0.01
        # Отрицательные значения дадут низкую/отрицательную similarity с положительными skill embeddings
        else:
            embedding = [-0.5] * 200 + [-0.3] * 200 + [0.01] * 1136
        
        mock_data = MagicMock()
        mock_data.embedding = embedding
        mock_response.data = [mock_data]
        return mock_response
    
    mock_client.embeddings.create = MagicMock(side_effect=create_embedding_side_effect)
    return mock_client


@pytest.fixture
def mock_openai_class(mock_openai_client):
    """Mock OpenAI class to return our mock client."""
    with patch('src.core.tool_selection.embedding_cache.OpenAI', return_value=mock_openai_client):
        yield mock_openai_client


def test_selector_finds_slides_skill_for_presentation_query(temp_skills_dir, temp_cache_dir, sample_skills, mock_openai_class):
    """
    Test: 'создай красивую презентацию' -> slides-formatting skill.
    
    ОЖИДАЕТСЯ: Провал - SkillSelector ещё не создан.
    """
    from src.core.skills.skill_selector import SkillSelector
    
    loader = SkillLoader(skills_dir=temp_skills_dir)
    skills = loader.load_all_skills()
    
    selector = SkillSelector(skills=skills, cache_dir=temp_cache_dir)
    selected = selector.select_skill("создай красивую презентацию")
    
    assert selected is not None, "Should select a skill"
    assert selected.name == "slides-formatting", "Should select slides-formatting skill"


def test_selector_finds_sheets_skill_for_analysis_query(temp_skills_dir, temp_cache_dir, sample_skills, mock_openai_class):
    """
    Test: 'проанализируй таблицу' -> sheets-analysis skill.
    
    ОЖИДАЕТСЯ: Провал - SkillSelector ещё не создан.
    """
    from src.core.skills.skill_selector import SkillSelector
    
    loader = SkillLoader(skills_dir=temp_skills_dir)
    skills = loader.load_all_skills()
    
    selector = SkillSelector(skills=skills, cache_dir=temp_cache_dir)
    # Используем запрос с ключевыми словами для sheets-analysis
    selected = selector.select_skill("проанализируй таблицу и построй график")
    
    assert selected is not None, "Should select a skill"
    assert selected.name == "sheets-analysis", f"Should select sheets-analysis skill, got {selected.name if selected else None}"


def test_selector_returns_none_when_no_match(temp_skills_dir, temp_cache_dir, sample_skills, mock_openai_class):
    """
    Test: Selector возвращает None если нет релевантного skill.
    
    ОЖИДАЕТСЯ: Провал - SkillSelector ещё не создан.
    """
    from src.core.skills.skill_selector import SkillSelector
    
    loader = SkillLoader(skills_dir=temp_skills_dir)
    skills = loader.load_all_skills()
    
    # Используем threshold чтобы отфильтровать нерелевантные запросы
    selector = SkillSelector(
        skills=skills,
        cache_dir=temp_cache_dir,
        similarity_threshold=0.3  # Threshold для фильтрации нерелевантных
    )
    selected = selector.select_skill("напиши стихотворение про любовь")
    
    # Нерелевантный запрос должен вернуть None (similarity будет очень низкой)
    assert selected is None, "Should return None for non-relevant query"


def test_selector_uses_similarity_threshold(temp_skills_dir, temp_cache_dir, sample_skills, mock_openai_class):
    """
    Test: Selector использует threshold для фильтрации низких similarity.
    
    ОЖИДАЕТСЯ: Провал - SkillSelector ещё не создан.
    """
    from src.core.skills.skill_selector import SkillSelector
    
    loader = SkillLoader(skills_dir=temp_skills_dir)
    skills = loader.load_all_skills()
    
    # Высокий threshold - должен вернуть None для нерелевантного запроса
    # Используем 0.5 как высокий threshold для теста (нерелевантные запросы дадут ~0.1-0.2 similarity)
    # По умолчанию threshold = 0.3 (более низкий для лучшего покрытия)
    selector = SkillSelector(
        skills=skills,
        cache_dir=temp_cache_dir,
        similarity_threshold=0.5  # Высокий threshold для теста фильтрации
    )
    selected = selector.select_skill("напиши стихотворение про любовь")
    
    # С threshold 0.5 нерелевантный запрос должен вернуть None
    assert selected is None, "Should return None when similarity below threshold"


def test_selector_handles_empty_skills_list(temp_cache_dir, mock_openai_class):
    """
    Test: Selector обрабатывает пустой список skills.
    
    ОЖИДАЕТСЯ: Провал - SkillSelector ещё не создан.
    """
    from src.core.skills.skill_selector import SkillSelector
    
    selector = SkillSelector(skills=[], cache_dir=temp_cache_dir)
    selected = selector.select_skill("любой запрос")
    
    assert selected is None, "Should return None when no skills available"


def test_selector_handles_empty_query(temp_skills_dir, temp_cache_dir, sample_skills, mock_openai_class):
    """
    Test: Selector обрабатывает пустой запрос.
    
    ОЖИДАЕТСЯ: Провал - SkillSelector ещё не создан.
    """
    from src.core.skills.skill_selector import SkillSelector
    
    loader = SkillLoader(skills_dir=temp_skills_dir)
    skills = loader.load_all_skills()
    
    selector = SkillSelector(skills=skills, cache_dir=temp_cache_dir)
    selected = selector.select_skill("")
    
    # Может вернуть None или первый skill
    assert selected is None or isinstance(selected, Skill), "Should handle empty query gracefully"


# ========== Phase 1: SkillSelector Filter Tests ==========

def test_skill_selector_filters_by_domain_type(temp_cache_dir, mock_openai_class):
    """SkillSelector должен фильтровать по type=domain."""
    from src.core.skills.skill_selector import SkillSelector
    from src.core.skills.skill_loader import SkillLoader
    from pathlib import Path
    
    # Use real skills directory
    project_root = Path(__file__).parent.parent
    skills_dir = project_root / "skills"
    
    loader = SkillLoader(skills_dir=skills_dir)
    skills = loader.load_all_skills()
    
    selector = SkillSelector(skills=skills, cache_dir=temp_cache_dir)
    skill = selector.select_skill("покажи почту", skill_type="domain")
    
    assert skill is not None
    assert skill.metadata.get("type") == "domain"


def test_get_domain_skills_for_composite(temp_cache_dir, mock_openai_class):
    """Метод должен возвращать domain skills для composite."""
    from src.core.skills.skill_selector import SkillSelector
    from src.core.skills.skill_loader import SkillLoader
    from pathlib import Path
    
    # Use real skills directory
    project_root = Path(__file__).parent.parent
    skills_dir = project_root / "skills"
    
    loader = SkillLoader(skills_dir=skills_dir)
    skills = loader.load_all_skills()
    
    selector = SkillSelector(skills=skills, cache_dir=temp_cache_dir)
    composite = loader.load_skill("focus-day")
    domain_skills = selector.get_domain_skills_for_composite(composite)
    
    domain_names = [s.name for s in domain_skills]
    assert "gmail" in domain_names
    assert "calendar" in domain_names
