"""
Tests для проверки завершения миграции на центральный агент.
Проверяет что вся логика из специализированных агентов перенесена в skills.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.skills.skill_loader import SkillLoader
from src.agents.main_agent import MainAgent


def test_all_agent_logic_in_skills():
    """Test: Вся логика из специализированных агентов теперь в skills"""
    loader = SkillLoader()
    
    # Calendar
    calendar = loader.load_skill("calendar")
    assert "timezone" in calendar.content.lower() or "часовой пояс" in calendar.content.lower()
    assert "относительные даты" in calendar.content.lower() or "relative" in calendar.content.lower()
    
    # Gmail
    gmail = loader.load_skill("gmail")
    assert "send_email" in str(gmail.metadata.get("tools", []))
    assert "validation" in gmail.content.lower() or "валидация" in gmail.content.lower()
    
    # Sheets
    sheets = loader.load_skill("sheets")
    assert "get_all_sheets_data" in str(sheets.metadata.get("tools", []))
    assert "расширенный анализ" in sheets.content.lower() or "extended" in sheets.content.lower()
    
    # Workspace
    workspace = loader.load_skill("workspace")
    assert "search" in workspace.content.lower() or "поиск" in workspace.content.lower()
    
    print("✅ test_all_agent_logic_in_skills PASSED")


def test_main_agent_doesnt_use_sub_agents():
    """Test: MainAgent не должен создавать sub-agents"""
    # Проверяем что MainAgent не имеет атрибутов sub-agents
    # Но не создаём реальный агент (может быть медленно)
    
    # Проверяем код напрямую
    import inspect
    from src.agents.main_agent import MainAgent
    
    init_source = inspect.getsource(MainAgent.__init__)
    
    # Не должно быть создания sub-agents
    assert "self.email_agent" not in init_source
    assert "self.calendar_agent" not in init_source
    assert "self.sheets_agent" not in init_source
    assert "self.workspace_agent" not in init_source
    
    # Должен быть GuardrailsLoader
    assert "_guardrails_loader" in init_source
    assert "GuardrailsLoader" in init_source
    
    print("✅ test_main_agent_doesnt_use_sub_agents PASSED")


def test_main_agent_uses_guardrails():
    """Test: MainAgent должен использовать GuardrailsLoader"""
    import inspect
    from src.agents.main_agent import MainAgent
    
    init_source = inspect.getsource(MainAgent.__init__)
    
    assert "GuardrailsLoader" in init_source
    assert "load_guardrails" in init_source
    
    print("✅ test_main_agent_uses_guardrails PASSED")


def test_main_agent_has_minimal_prompt():
    """Test: MainAgent должен использовать минимальный промпт"""
    from src.agents.main_agent import get_minimal_main_agent_prompt
    
    prompt = get_minimal_main_agent_prompt()
    
    # Проверяем что промпт короткий
    assert len(prompt) < 1200, f"Prompt too long: {len(prompt)} chars"
    
    # Проверяем что нет routing правил
    assert "DATA SOURCE ROUTING" not in prompt
    assert "Project Lad" not in prompt
    assert "projectlad_" not in prompt
    
    # Проверяем что есть ссылки на guardrails и skills
    assert "guardrails" in prompt.lower()
    assert "skill" in prompt.lower()
    
    print("✅ test_main_agent_has_minimal_prompt PASSED")


def test_skills_have_all_routing_keywords():
    """Test: Все routing keywords должны быть в skills, не в MainAgent"""
    loader = SkillLoader()
    
    # ProjectLad keywords
    projectlad = loader.load_skill("projectlad")
    assert "PL" in projectlad.metadata.get("keywords", [])
    assert "проект лад" in projectlad.metadata.get("keywords", [])
    
    # 1C keywords
    onec = loader.load_skill("onec")
    assert "1С" in onec.metadata.get("keywords", [])
    assert "бухгалтерия" in onec.metadata.get("keywords", [])
    
    print("✅ test_skills_have_all_routing_keywords PASSED")


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ завершения миграции")
    print("=" * 70)
    
    try:
        test_all_agent_logic_in_skills()
        test_main_agent_doesnt_use_sub_agents()
        test_main_agent_uses_guardrails()
        test_main_agent_has_minimal_prompt()
        test_skills_have_all_routing_keywords()
        
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
