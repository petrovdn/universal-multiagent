"""
Тест для проверки загрузки инструментов, особенно create_presentation_batch.
Проверяет, что инструменты правильно загружаются в MCPToolProvider.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.providers.mcp_provider import MCPToolProvider
from src.mcp_tools.slides_tools import get_slides_tools


def test_slides_tools_loading():
    """Проверяет, что get_slides_tools() возвращает create_presentation_batch."""
    print("=" * 60)
    print("ТЕСТ 1: Загрузка инструментов из get_slides_tools()")
    print("=" * 60)
    
    tools = get_slides_tools()
    tool_names = [t.name for t in tools]
    
    print(f"Всего инструментов: {len(tools)}")
    print(f"Имена инструментов: {tool_names}")
    
    has_create_presentation_batch = "create_presentation_batch" in tool_names
    print(f"\n✅ create_presentation_batch в списке: {has_create_presentation_batch}")
    
    if has_create_presentation_batch:
        tool = next(t for t in tools if t.name == "create_presentation_batch")
        print(f"   Описание: {tool.description[:100]}...")
    
    assert has_create_presentation_batch, "create_presentation_batch должен быть в списке инструментов!"
    print("✅ ТЕСТ 1 ПРОЙДЕН\n")
    return tools


def test_mcp_provider_loading():
    """Проверяет, что MCPToolProvider загружает create_presentation_batch."""
    print("=" * 60)
    print("ТЕСТ 2: Загрузка инструментов в MCPToolProvider")
    print("=" * 60)
    
    provider = MCPToolProvider()
    tool_names = list(provider.tools.keys())
    
    print(f"Всего инструментов в provider: {len(provider.tools)}")
    print(f"Первые 20 инструментов: {tool_names[:20]}")
    
    has_create_presentation_batch = "create_presentation_batch" in provider.tools
    print(f"\n✅ create_presentation_batch в provider.tools: {has_create_presentation_batch}")
    
    if has_create_presentation_batch:
        tool = provider.tools["create_presentation_batch"]
        print(f"   Тип инструмента: {type(tool).__name__}")
        print(f"   Имя инструмента: {tool.name}")
    
    # Проверяем все инструменты для презентаций
    slides_tools = [name for name in tool_names if "presentation" in name.lower() or "slide" in name.lower()]
    print(f"\nВсе инструменты для презентаций: {slides_tools}")
    
    assert has_create_presentation_batch, "create_presentation_batch должен быть в provider.tools!"
    print("✅ ТЕСТ 2 ПРОЙДЕН\n")
    return provider


def test_capability_registry():
    """Проверяет, что CapabilityRegistry видит create_presentation_batch."""
    print("=" * 60)
    print("ТЕСТ 3: CapabilityRegistry и capabilities")
    print("=" * 60)
    
    from src.core.capability_registry import CapabilityRegistry
    from src.core.providers.mcp_provider import MCPToolProvider
    from src.core.providers.a2a_provider import A2AAgentProvider
    
    # Инициализируем registry так же, как в AgentWrapper
    registry = CapabilityRegistry()
    
    # Регистрируем провайдеры
    mcp_provider = MCPToolProvider()
    registry.register_provider(mcp_provider)
    
    a2a_provider = A2AAgentProvider()
    registry.register_provider(a2a_provider)
    
    capabilities = registry.get_capabilities()
    capability_names = [cap.name for cap in capabilities]
    
    print(f"Всего capabilities: {len(capabilities)}")
    
    has_create_presentation_batch = "create_presentation_batch" in capability_names
    print(f"\n✅ create_presentation_batch в capabilities: {has_create_presentation_batch}")
    
    if has_create_presentation_batch:
        cap = next(cap for cap in capabilities if cap.name == "create_presentation_batch")
        print(f"   Описание: {cap.description[:100]}...")
        print(f"   Категория: {cap.category}")
        print(f"   Провайдер тип: {cap.provider_type}")
    
    # Проверяем все capabilities для презентаций
    slides_caps = [name for name in capability_names if "presentation" in name.lower() or "slide" in name.lower()]
    print(f"\nВсе capabilities для презентаций: {slides_caps}")
    
    assert has_create_presentation_batch, "create_presentation_batch должен быть в capabilities!"
    print("✅ ТЕСТ 3 ПРОЙДЕН\n")
    return registry


def test_unified_react_engine_tools():
    """Проверяет, что UnifiedReActEngine видит инструменты."""
    print("=" * 60)
    print("ТЕСТ 4: UnifiedReActEngine и bind_tools")
    print("=" * 60)
    
    from src.core.capability_registry import CapabilityRegistry
    from src.core.providers.mcp_provider import MCPToolProvider
    from src.core.providers.a2a_provider import A2AAgentProvider
    from src.core.unified_react_engine import UnifiedReActEngine, ReActConfig
    from src.core.action_provider import CapabilityCategory
    from src.api.websocket_manager import WebSocketManager
    
    # Создаем минимальную конфигурацию
    config = ReActConfig(
        mode="agent",
        allowed_categories=[]
    )
    
    # Инициализируем registry с провайдерами
    registry = CapabilityRegistry()
    mcp_provider = MCPToolProvider()
    registry.register_provider(mcp_provider)
    a2a_provider = A2AAgentProvider()
    registry.register_provider(a2a_provider)
    
    ws_manager = WebSocketManager()
    
    engine = UnifiedReActEngine(
        config=config,
        capability_registry=registry,
        ws_manager=ws_manager,
        session_id="test-session"
    )
    
    tool_names = [t.name for t in engine.tools]
    
    print(f"Всего инструментов в engine.tools: {len(engine.tools)}")
    print(f"Первые 20 инструментов: {tool_names[:20]}")
    
    has_create_presentation_batch = any(t.name == "create_presentation_batch" for t in engine.tools)
    print(f"\n✅ create_presentation_batch в engine.tools: {has_create_presentation_batch}")
    
    if has_create_presentation_batch:
        tool = next(t for t in engine.tools if t.name == "create_presentation_batch")
        print(f"   Тип инструмента: {type(tool).__name__}")
        print(f"   Имя инструмента: {tool.name}")
    
    # Проверяем все инструменты для презентаций
    slides_tools = [name for name in tool_names if "presentation" in name.lower() or "slide" in name.lower()]
    print(f"\nВсе инструменты для презентаций: {slides_tools}")
    
    assert has_create_presentation_batch, "create_presentation_batch должен быть в engine.tools!"
    print("✅ ТЕСТ 4 ПРОЙДЕН\n")
    return engine


def test_mcp_provider_execute():
    """Проверяет, что MCPToolProvider может найти инструмент при execute()."""
    print("=" * 60)
    print("ТЕСТ 5: MCPToolProvider.execute() - поиск инструмента")
    print("=" * 60)
    
    provider = MCPToolProvider()
    
    # Проверяем, что инструмент есть в словаре
    has_tool = "create_presentation_batch" in provider.tools
    print(f"create_presentation_batch в provider.tools: {has_tool}")
    
    if has_tool:
        tool = provider.tools["create_presentation_batch"]
        print(f"   Инструмент найден: {tool.name}")
        print(f"   Тип: {type(tool).__name__}")
        
        # Проверяем, что execute() не вызовет ValueError
        # (не вызываем реально, так как нужны OAuth токены)
        print("\n   ✅ Инструмент доступен для выполнения")
    else:
        print("\n   ❌ ОШИБКА: Инструмент не найден в provider.tools!")
        print(f"   Доступные инструменты: {list(provider.tools.keys())[:20]}")
        raise AssertionError("create_presentation_batch не найден в provider.tools!")
    
    print("✅ ТЕСТ 5 ПРОЙДЕН\n")


def main():
    """Запускает все тесты."""
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАГРУЗКИ ИНСТРУМЕНТОВ")
    print("=" * 60 + "\n")
    
    try:
        # Тест 1: Загрузка из get_slides_tools()
        slides_tools = test_slides_tools_loading()
        
        # Тест 2: Загрузка в MCPToolProvider
        provider = test_mcp_provider_loading()
        
        # Тест 3: CapabilityRegistry
        registry = test_capability_registry()
        
        # Тест 4: UnifiedReActEngine
        engine = test_unified_react_engine_tools()
        
        # Тест 5: MCPToolProvider.execute()
        test_mcp_provider_execute()
        
        print("=" * 60)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print("\n" + "=" * 60)
        print(f"❌ ТЕСТ ПРОВАЛЕН: {e}")
        print("=" * 60)
        return 1
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ ОШИБКА ПРИ ВЫПОЛНЕНИИ ТЕСТОВ: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
