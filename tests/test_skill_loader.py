"""
TDD tests for SkillLoader - Phase 2.1.

These tests should FAIL initially (Red phase), then pass after implementation (Green phase).
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch


@pytest.fixture
def temp_skills_dir():
    """Create temporary directory for skills."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_skill_md():
    """Sample SKILL.md content."""
    return """---
name: slides-formatting
description: >
  Продвинутое форматирование презентаций Google Slides. Используй когда 
  пользователь просит создать красивую презентацию, оформить слайды, 
  добавить стили.
metadata:
  version: "1.0"
  category: formatting
---

## Когда активировать

Ключевые слова: "презентация", "слайды", "оформить", "красиво", "стиль"

## Приоритетный инструмент

`create_presentation` - создание новой презентации
`format_slide` - форматирование слайдов

## Workflow

1. Создай презентацию с помощью create_presentation
2. Добавь заголовок и подзаголовок на первый слайд
3. Используй единый стиль для всех слайдов
4. Добавь изображения через insert_image
5. Примени форматирование через format_slide

## Стили

- Заголовки: шрифт Arial, размер 24, жирный
- Подзаголовки: шрифт Arial, размер 18, обычный
- Текст: шрифт Arial, размер 14
"""


def test_loader_loads_skill_from_directory(temp_skills_dir, sample_skill_md):
    """
    Test: Loader загружает skill из директории.
    
    ОЖИДАЕТСЯ: Провал - SkillLoader ещё не создан.
    """
    from src.core.skills.skill_loader import SkillLoader
    
    # Create skill directory
    skill_dir = temp_skills_dir / "slides-formatting"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(sample_skill_md, encoding="utf-8")
    
    loader = SkillLoader(skills_dir=temp_skills_dir)
    skill = loader.load_skill("slides-formatting")
    
    assert skill is not None, "Skill should be loaded"
    assert skill.name == "slides-formatting", "Skill name should match"
    assert "Продвинутое форматирование" in skill.description, "Description should be parsed"


def test_loader_parses_yaml_frontmatter(temp_skills_dir, sample_skill_md):
    """
    Test: Loader парсит YAML frontmatter.
    
    ОЖИДАЕТСЯ: Провал - SkillLoader ещё не создан.
    """
    from src.core.skills.skill_loader import SkillLoader
    
    skill_dir = temp_skills_dir / "slides-formatting"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(sample_skill_md, encoding="utf-8")
    
    loader = SkillLoader(skills_dir=temp_skills_dir)
    skill = loader.load_skill("slides-formatting")
    
    assert skill.metadata["version"] == "1.0", "Metadata should be parsed"
    assert skill.metadata["category"] == "formatting", "Metadata category should be parsed"


def test_loader_parses_markdown_content(temp_skills_dir, sample_skill_md):
    """
    Test: Loader парсит markdown контент после frontmatter.
    
    ОЖИДАЕТСЯ: Провал - SkillLoader ещё не создан.
    """
    from src.core.skills.skill_loader import SkillLoader
    
    skill_dir = temp_skills_dir / "slides-formatting"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(sample_skill_md, encoding="utf-8")
    
    loader = SkillLoader(skills_dir=temp_skills_dir)
    skill = loader.load_skill("slides-formatting")
    
    assert "Когда активировать" in skill.content, "Markdown content should be parsed"
    assert "Workflow" in skill.content, "Workflow section should be in content"
    assert "create_presentation" in skill.content, "Tool names should be in content"


def test_loader_handles_missing_skill(temp_skills_dir):
    """
    Test: Loader обрабатывает отсутствующий skill.
    
    ОЖИДАЕТСЯ: Провал - SkillLoader ещё не создан.
    """
    from src.core.skills.skill_loader import SkillLoader
    
    loader = SkillLoader(skills_dir=temp_skills_dir)
    
    with pytest.raises((FileNotFoundError, ValueError), match="not found|does not exist"):
        loader.load_skill("non-existent-skill")


def test_loader_loads_all_skills(temp_skills_dir, sample_skill_md):
    """
    Test: Loader загружает все skills из директории.
    
    ОЖИДАЕТСЯ: Провал - SkillLoader ещё не создан.
    """
    from src.core.skills.skill_loader import SkillLoader
    
    # Create multiple skills
    skill1_dir = temp_skills_dir / "slides-formatting"
    skill1_dir.mkdir()
    (skill1_dir / "SKILL.md").write_text(sample_skill_md, encoding="utf-8")
    
    skill2_md = sample_skill_md.replace("slides-formatting", "sheets-analysis")
    skill2_dir = temp_skills_dir / "sheets-analysis"
    skill2_dir.mkdir()
    (skill2_dir / "SKILL.md").write_text(skill2_md, encoding="utf-8")
    
    loader = SkillLoader(skills_dir=temp_skills_dir)
    skills = loader.load_all_skills()
    
    assert len(skills) == 2, "Should load all skills"
    skill_names = [s.name for s in skills]
    assert "slides-formatting" in skill_names
    assert "sheets-analysis" in skill_names


def test_loader_handles_missing_skill_md(temp_skills_dir):
    """
    Test: Loader обрабатывает директорию без SKILL.md.
    
    ОЖИДАЕТСЯ: Провал - SkillLoader ещё не создан.
    """
    from src.core.skills.skill_loader import SkillLoader
    
    # Create directory without SKILL.md
    skill_dir = temp_skills_dir / "incomplete-skill"
    skill_dir.mkdir()
    
    loader = SkillLoader(skills_dir=temp_skills_dir)
    
    # Should skip incomplete skills or raise error
    skills = loader.load_all_skills()
    assert "incomplete-skill" not in [s.name for s in skills], "Incomplete skills should be skipped"


def test_loader_handles_invalid_yaml(temp_skills_dir):
    """
    Test: Loader обрабатывает невалидный YAML frontmatter.
    
    ОЖИДАЕТСЯ: Провал - SkillLoader ещё не создан.
    """
    from src.core.skills.skill_loader import SkillLoader
    
    invalid_skill_md = """---
name: invalid
description: test
invalid: yaml: [unclosed
---

Content here
"""
    
    skill_dir = temp_skills_dir / "invalid-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(invalid_skill_md, encoding="utf-8")
    
    loader = SkillLoader(skills_dir=temp_skills_dir)
    
    # Should handle gracefully (skip or raise informative error)
    with pytest.raises((ValueError, KeyError), match="YAML|frontmatter|parse"):
        loader.load_skill("invalid-skill")


# ========== Phase 1: Domain Skills Tests ==========

def test_load_gmail_skill():
    """Domain skill gmail должен загружаться с правильными metadata."""
    from src.core.skills.skill_loader import SkillLoader
    
    loader = SkillLoader()
    skill = loader.load_skill("gmail")
    
    assert skill.name == "gmail"
    assert skill.metadata.get("type") == "domain"
    assert "send_email" in skill.metadata.get("tools", [])


def test_load_calendar_skill():
    """Domain skill calendar должен загружаться с правильными metadata."""
    from src.core.skills.skill_loader import SkillLoader
    
    loader = SkillLoader()
    skill = loader.load_skill("calendar")
    
    assert skill.name == "calendar"
    assert skill.metadata.get("type") == "domain"
    assert "get_calendar_events" in skill.metadata.get("tools", [])


def test_load_sheets_skill():
    """Domain skill sheets должен загружаться с правильными metadata."""
    from src.core.skills.skill_loader import SkillLoader
    
    loader = SkillLoader()
    skill = loader.load_skill("sheets")
    
    assert skill.name == "sheets"
    assert skill.metadata.get("type") == "domain"
    assert "get_sheet_data" in skill.metadata.get("tools", [])


def test_load_docs_skill():
    """Domain skill docs должен загружаться с правильными metadata."""
    from src.core.skills.skill_loader import SkillLoader
    
    loader = SkillLoader()
    skill = loader.load_skill("docs")
    
    assert skill.name == "docs"
    assert skill.metadata.get("type") == "domain"
    assert "read_document" in skill.metadata.get("tools", [])


def test_load_workspace_skill():
    """Domain skill workspace должен загружаться с правильными metadata."""
    from src.core.skills.skill_loader import SkillLoader
    
    loader = SkillLoader()
    skill = loader.load_skill("workspace")
    
    assert skill.name == "workspace"
    assert skill.metadata.get("type") == "domain"
    assert "search_files" in skill.metadata.get("tools", [])


def test_load_all_domain_skills():
    """Все domain skills должны загружаться."""
    from src.core.skills.skill_loader import SkillLoader
    
    loader = SkillLoader()
    skills = loader.load_all_skills()
    
    domain_skills = [s for s in skills if s.metadata.get("type") == "domain"]
    domain_names = [s.name for s in domain_skills]
    
    assert "gmail" in domain_names
    assert "calendar" in domain_names
    assert "sheets" in domain_names
    assert "docs" in domain_names
    assert "workspace" in domain_names


# ========== Phase 1: Composite Skills Tests ==========

def test_load_focus_day_composite_skill():
    """Composite skill focus-day должен загружаться с domains."""
    from src.core.skills.skill_loader import SkillLoader
    
    loader = SkillLoader()
    skill = loader.load_skill("focus-day")
    
    assert skill.name == "focus-day"
    assert skill.metadata.get("type") == "composite"
    assert "gmail" in skill.metadata.get("domains", [])
    assert "calendar" in skill.metadata.get("domains", [])
    assert skill.metadata.get("execution") == "parallel"


def test_load_meeting_prep_composite_skill():
    """Composite skill meeting-prep должен загружаться с domains."""
    from src.core.skills.skill_loader import SkillLoader
    
    loader = SkillLoader()
    skill = loader.load_skill("meeting-prep")
    
    assert skill.name == "meeting-prep"
    assert skill.metadata.get("type") == "composite"
    assert "calendar" in skill.metadata.get("domains", [])
    assert skill.metadata.get("execution") == "sequential"
