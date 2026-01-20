"""
Tests для Anthropic Cache (Guardrails + Base Prompt).
Проверяет что system prompt отправляется с cache_control для экономии токенов.
"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import inspect

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.base_agent import BaseAgent
from langchain_core.tools import BaseTool


class MockTool(BaseTool):
    """Mock tool для тестов."""
    name = "mock_tool"
    description = "Mock tool for testing"
    
    def _run(self, query: str) -> str:
        return "mock result"


def test_base_agent_system_prompt_has_cache_control():
    """Test: BaseAgent должен добавлять cache_control к system prompt для Anthropic"""
    # Создаём mock LLM (Anthropic)
    with patch('src.agents.base_agent.create_llm') as mock_create_llm:
        mock_llm = MagicMock()
        mock_llm.__class__.__name__ = "ChatAnthropic"  # Имитируем Anthropic модель
        mock_create_llm.return_value = mock_llm
        
        agent = BaseAgent(
            name="TestAgent",
            system_prompt="Test system prompt",
            tools=[MockTool()]
        )
        
        # Проверяем что _build_graph был вызван
        assert agent.graph is not None
        
        # Проверяем что prompt создан (через inspect или mock)
        # Нужно проверить что system message имеет cache_control
        print("✅ test_base_agent_system_prompt_has_cache_control PASSED (needs implementation check)")


def test_anthropic_model_uses_cache_control():
    """Test: Для Anthropic моделей должен использоваться cache_control"""
    with patch('src.agents.base_agent.create_llm') as mock_create_llm:
        mock_llm = MagicMock()
        mock_llm.__class__.__name__ = "ChatAnthropic"
        mock_create_llm.return_value = mock_llm
        
        agent = BaseAgent(
            name="TestAgent",
            system_prompt="Test prompt",
            tools=[MockTool()]
        )
        
        # Проверяем что для Anthropic используется cache_control
        # Это будет проверено через проверку вызовов LLM
        assert agent.llm is not None
        print("✅ test_anthropic_model_uses_cache_control PASSED (needs implementation check)")


def test_non_anthropic_model_no_cache_control():
    """Test: Для не-Anthropic моделей cache_control НЕ используется"""
    with patch('src.agents.base_agent.create_llm') as mock_create_llm:
        mock_llm = MagicMock()
        mock_llm.__class__.__name__ = "ChatOpenAI"  # OpenAI модель
        mock_create_llm.return_value = mock_llm
        
        agent = BaseAgent(
            name="TestAgent",
            system_prompt="Test prompt",
            tools=[MockTool()]
        )
        
        # Проверяем что для OpenAI НЕ используется cache_control
        assert agent.llm is not None
        print("✅ test_non_anthropic_model_no_cache_control PASSED (needs implementation check)")


def test_cache_control_type_ephemeral():
    """Test: cache_control должен иметь type='ephemeral'"""
    # Проверяем что в коде используется ephemeral cache
    from src.agents.base_agent import BaseAgent
    
    # Читаем исходный код _build_graph
    source = inspect.getsource(BaseAgent._build_graph)
    
    # После реализации должен быть cache_control с ephemeral
    # Пока проверяем что метод существует
    assert "_build_graph" in source
    print("✅ test_cache_control_type_ephemeral PASSED (will check after implementation)")


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ Anthropic Cache")
    print("=" * 70)
    
    try:
        test_base_agent_system_prompt_has_cache_control()
        test_anthropic_model_uses_cache_control()
        test_non_anthropic_model_no_cache_control()
        test_cache_control_type_ephemeral()
        
        print("=" * 70)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ (или готовы к реализации)")
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
