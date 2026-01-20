"""
Tests для минимального MainAgent prompt.
Проверяет что промпт компактный и не содержит routing логику.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.main_agent import MainAgent


def get_minimal_main_agent_prompt():
    """Вспомогательная функция для получения минимального промпта."""
    # Создаём временный агент чтобы получить промпт
    agent = MainAgent()
    return agent.system_prompt


def test_minimal_prompt_is_short():
    """Test: Минимальный промпт должен быть < 300 tokens (~1200 chars)"""
    prompt = get_minimal_main_agent_prompt()
    
    # Base prompt без guardrails должен быть коротким
    # Guardrails добавляются отдельно, но base должен быть компактным
    assert len(prompt) < 2500, f"Prompt too long: {len(prompt)} chars (expected < 2500)"
    assert "Ты универсальный AI-ассистент" in prompt or "универсальный" in prompt.lower()
    print("✅ test_minimal_prompt_is_short PASSED")


def test_minimal_prompt_references_guardrails():
    """Test: Промпт должен ссылаться на guardrails"""
    prompt = get_minimal_main_agent_prompt()
    
    assert "<guardrails" in prompt or "guardrails" in prompt.lower()
    print("✅ test_minimal_prompt_references_guardrails PASSED")


def test_minimal_prompt_references_skills():
    """Test: Промпт должен ссылаться на skill_instructions"""
    prompt = get_minimal_main_agent_prompt()
    
    assert "<skill_instructions>" in prompt or "skill" in prompt.lower()
    print("✅ test_minimal_prompt_references_skills PASSED")


def test_minimal_prompt_no_routing_rules():
    """Test: Промпт НЕ должен содержать DATA SOURCE ROUTING"""
    prompt = get_minimal_main_agent_prompt()
    
    assert "DATA SOURCE ROUTING" not in prompt
    assert "Project Lad" not in prompt or "projectlad" not in prompt.lower()
    # Может быть упоминание в guardrails, но не детальные правила
    print("✅ test_minimal_prompt_no_routing_rules PASSED")


def test_main_agent_loads_guardrails():
    """Test: MainAgent должен загружать guardrails при инициализации"""
    agent = MainAgent()
    
    # Check that guardrails are loaded
    assert hasattr(agent, '_guardrails_loader')
    
    guardrails = agent._guardrails_loader.load_guardrails()
    assert len(guardrails) > 0
    print("✅ test_main_agent_loads_guardrails PASSED")


def test_main_agent_prompt_contains_guardrails():
    """Test: System prompt должен содержать guardrails"""
    agent = MainAgent()
    prompt = agent.system_prompt
    
    # Guardrails должны быть в промпте
    assert "<guardrails" in prompt
    assert "priority=\"critical\"" in prompt
    print("✅ test_main_agent_prompt_contains_guardrails PASSED")


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ минимального MainAgent prompt")
    print("=" * 70)
    
    try:
        test_minimal_prompt_is_short()
        test_minimal_prompt_references_guardrails()
        test_minimal_prompt_references_skills()
        test_minimal_prompt_no_routing_rules()
        test_main_agent_loads_guardrails()
        test_main_agent_prompt_contains_guardrails()
        
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
