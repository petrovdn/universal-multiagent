"""
Tests для новых skills: projectlad и onec.
Проверяет что вся routing логика из MainAgent перенесена в skills.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.skills.skill_loader import SkillLoader


def test_projectlad_skill_exists():
    """Test: ProjectLad skill должен существовать"""
    loader = SkillLoader()
    skill = loader.load_skill("projectlad")
    
    assert skill.name == "projectlad"
    assert "project" in skill.description.lower() or "проект" in skill.description.lower()
    assert len(skill.content) > 100
    print("✅ test_projectlad_skill_exists PASSED")


def test_onec_skill_exists():
    """Test: 1C skill должен существовать"""
    loader = SkillLoader()
    skill = loader.load_skill("onec")
    
    assert skill.name == "onec"
    assert "1с" in skill.description.lower() or "бухгалтерия" in skill.description.lower()
    assert len(skill.content) > 100
    print("✅ test_onec_skill_exists PASSED")


def test_skills_have_routing_keywords():
    """Test: Новые skills должны содержать routing keywords"""
    loader = SkillLoader()
    
    projectlad = loader.load_skill("projectlad")
    assert "keywords" in projectlad.metadata
    keywords = projectlad.metadata["keywords"]
    assert any("project" in kw.lower() or "проект" in kw.lower() or "pl" in kw.lower() for kw in keywords)
    
    onec = loader.load_skill("onec")
    assert "keywords" in onec.metadata
    keywords = onec.metadata["keywords"]
    assert any("1с" in kw.lower() or "бухгалтерия" in kw.lower() for kw in keywords)
    
    print("✅ test_skills_have_routing_keywords PASSED")


def test_projectlad_has_tools_list():
    """Test: ProjectLad skill должен содержать список tools"""
    loader = SkillLoader()
    projectlad = loader.load_skill("projectlad")
    
    assert "tools" in projectlad.metadata
    tools = projectlad.metadata["tools"]
    assert "projectlad_list_projects" in tools
    assert "projectlad_get_project_works" in tools
    print("✅ test_projectlad_has_tools_list PASSED")


def test_onec_has_tools_list():
    """Test: 1C skill должен содержать список tools"""
    loader = SkillLoader()
    onec = loader.load_skill("onec")
    
    assert "tools" in onec.metadata
    tools = onec.metadata["tools"]
    assert "onec_get_salary_by_employee_month" in tools
    print("✅ test_onec_has_tools_list PASSED")


def test_projectlad_has_routing_rules():
    """Test: ProjectLad skill должен содержать routing правила"""
    loader = SkillLoader()
    projectlad = loader.load_skill("projectlad")
    
    # Должны быть правила о том, что Project Lad != Google Drive
    content_lower = projectlad.content.lower()
    assert "google drive" in content_lower or "не ищи" in content_lower or "не используй" in content_lower
    print("✅ test_projectlad_has_routing_rules PASSED")


def test_onec_has_routing_rules():
    """Test: 1C skill должен содержать routing правила"""
    loader = SkillLoader()
    onec = loader.load_skill("onec")
    
    # Должны быть правила о том, что 1C != Google Drive
    content_lower = onec.content.lower()
    assert "google drive" in content_lower or "не ищи" in content_lower or "не используй" in content_lower
    print("✅ test_onec_has_routing_rules PASSED")


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ новых skills (projectlad, onec)")
    print("=" * 70)
    
    try:
        test_projectlad_skill_exists()
        test_onec_skill_exists()
        test_skills_have_routing_keywords()
        test_projectlad_has_tools_list()
        test_onec_has_tools_list()
        test_projectlad_has_routing_rules()
        test_onec_has_routing_rules()
        
        print("=" * 70)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n❌ ТЕСТ ПРОВАЛЕН: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
