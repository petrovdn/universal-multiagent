"""
TDD test for slides-formatting SKILL.md - Phase 2.3.

This test should FAIL initially (Red phase), then pass after creating SKILL.md (Green phase).
"""
import pytest
from pathlib import Path
from src.core.skills.skill_loader import SkillLoader
from src.core.skills.skill_selector import SkillSelector


def test_slides_formatting_skill_exists():
    """
    Test: slides-formatting SKILL.md существует и загружается корректно.
    
    ОЖИДАЕТСЯ: Провал - SKILL.md ещё не создан.
    """
    # Определяем путь к skills директории
    project_root = Path(__file__).parent.parent
    skills_dir = project_root / "skills"
    
    loader = SkillLoader(skills_dir=skills_dir)
    
    # Пытаемся загрузить slides-formatting skill
    skill = loader.load_skill("slides-formatting")
    
    assert skill is not None, "slides-formatting skill should exist"
    assert skill.name == "slides-formatting", "Skill name should match"
    assert "презентация" in skill.description.lower() or "slides" in skill.description.lower(), "Description should mention presentations"
    assert len(skill.content) > 0, "Skill should have content"


def test_slides_formatting_skill_is_selected_for_presentation_queries():
    """
    Test: slides-formatting skill выбирается для запросов о презентациях.
    
    ОЖИДАЕТСЯ: Провал - SKILL.md ещё не создан или selector не работает.
    """
    project_root = Path(__file__).parent.parent
    skills_dir = project_root / "skills"
    
    loader = SkillLoader(skills_dir=skills_dir)
    skills = loader.load_all_skills()
    
    # Проверяем что slides-formatting есть в списке
    slides_skill = next((s for s in skills if s.name == "slides-formatting"), None)
    assert slides_skill is not None, "slides-formatting skill should be loaded"
    
    # Тестируем selector (если есть другие skills, они тоже загрузятся)
    selector = SkillSelector(skills=skills)
    
    # Запрос о презентации должен выбрать slides-formatting
    selected = selector.select_skill("создай красивую презентацию")
    
    assert selected is not None, "Should select a skill for presentation query"
    assert selected.name == "slides-formatting", f"Should select slides-formatting, got {selected.name if selected else None}"


def test_slides_formatting_skill_contains_workflow():
    """
    Test: slides-formatting skill содержит workflow инструкции.
    
    ОЖИДАЕТСЯ: Провал - SKILL.md ещё не создан или не содержит workflow.
    """
    project_root = Path(__file__).parent.parent
    skills_dir = project_root / "skills"
    
    loader = SkillLoader(skills_dir=skills_dir)
    skill = loader.load_skill("slides-formatting")
    
    # Проверяем наличие ключевых секций
    content_lower = skill.content.lower()
    
    # Должны быть инструкции о workflow или инструментах
    has_workflow = "workflow" in content_lower or "шаг" in content_lower or "инструмент" in content_lower
    assert has_workflow, "Skill should contain workflow or tool instructions"
    
    # Должны быть упоминания ключевых инструментов
    has_tools = any(tool in content_lower for tool in [
        "create_presentation",
        "format",
        "insert",
        "slide"
    ])
    assert has_tools, "Skill should mention presentation tools"
