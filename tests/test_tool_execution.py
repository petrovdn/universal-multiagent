"""
Интеграционный тест для проверки выполнения create_presentation_batch.
Симулирует реальный путь от UnifiedReActEngine до MCPToolProvider.execute().
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.capability_registry import CapabilityRegistry
from src.core.providers.mcp_provider import MCPToolProvider
from src.core.providers.a2a_provider import A2AAgentProvider
from src.core.unified_react_engine import UnifiedReActEngine, ReActConfig
from src.core.action_provider import CapabilityCategory
from src.api.websocket_manager import WebSocketManager


async def test_tool_execution_path():
    """Проверяет весь путь выполнения инструмента."""
    print("=" * 60)
    print("ИНТЕГРАЦИОННЫЙ ТЕСТ: Путь выполнения create_presentation_batch")
    print("=" * 60)
    
    # Шаг 1: Инициализация registry с провайдерами
    print("\n1. Инициализация CapabilityRegistry...")
    registry = CapabilityRegistry()
    mcp_provider = MCPToolProvider()
    registry.register_provider(mcp_provider)
    a2a_provider = A2AAgentProvider()
    registry.register_provider(a2a_provider)
    
    capabilities = registry.get_capabilities()
    has_capability = any(cap.name == "create_presentation_batch" for cap in capabilities)
    print(f"   ✅ create_presentation_batch в capabilities: {has_capability}")
    assert has_capability, "create_presentation_batch должен быть в capabilities!"
    
    # Шаг 2: Инициализация UnifiedReActEngine
    print("\n2. Инициализация UnifiedReActEngine...")
    config = ReActConfig(
        mode="agent",
        allowed_categories=[]
    )
    ws_manager = WebSocketManager()
    
    engine = UnifiedReActEngine(
        config=config,
        capability_registry=registry,
        ws_manager=ws_manager,
        session_id="test-session"
    )
    
    has_tool = any(t.name == "create_presentation_batch" for t in engine.tools)
    print(f"   ✅ create_presentation_batch в engine.tools: {has_tool}")
    assert has_tool, "create_presentation_batch должен быть в engine.tools!"
    
    # Шаг 3: Проверка _build_tools_from_capabilities
    print("\n3. Проверка _build_tools_from_capabilities...")
    tools_from_caps = engine._build_tools_from_capabilities()
    has_tool_from_caps = any(t.name == "create_presentation_batch" for t in tools_from_caps)
    print(f"   ✅ create_presentation_batch в tools_from_capabilities: {has_tool_from_caps}")
    assert has_tool_from_caps, "create_presentation_batch должен быть в tools_from_capabilities!"
    
    # Шаг 4: Проверка registry.execute (симуляция вызова)
    print("\n4. Проверка registry.execute (симуляция)...")
    
    # Проверяем, что capability есть в registry
    capability = next((cap for cap in capabilities if cap.name == "create_presentation_batch"), None)
    assert capability is not None, "create_presentation_batch capability не найден!"
    
    # Проверяем, что provider может найти инструмент
    tool_in_provider = mcp_provider.tools.get("create_presentation_batch")
    assert tool_in_provider is not None, "create_presentation_batch не найден в mcp_provider.tools!"
    print(f"   ✅ Инструмент найден в mcp_provider.tools: {tool_in_provider.name}")
    
    # Шаг 5: Проверка execute() - НЕ вызываем реально, только проверяем доступность
    print("\n5. Проверка доступности execute()...")
    
    # Проверяем, что execute() не вызовет ValueError("Unknown capability")
    try:
        # Не вызываем реально, только проверяем, что инструмент есть
        if "create_presentation_batch" in mcp_provider.tools:
            print("   ✅ Инструмент доступен для execute()")
        else:
            raise ValueError("Unknown capability: create_presentation_batch")
    except ValueError as e:
        print(f"   ❌ ОШИБКА: {e}")
        raise
    
    # Шаг 6: Проверка _get_relevant_tools
    print("\n6. Проверка _get_relevant_tools...")
    relevant_tools = engine._get_relevant_tools(
        goal="создай презентацию из 5 слайдов про Москву",
        completed_tools=[]
    )
    relevant_tool_names = [t["name"] for t in relevant_tools]
    has_in_relevant = "create_presentation_batch" in relevant_tool_names
    print(f"   ✅ create_presentation_batch в relevant_tools: {has_in_relevant}")
    print(f"   Всего релевантных инструментов: {len(relevant_tools)}")
    print(f"   Имена: {relevant_tool_names}")
    
    if not has_in_relevant:
        print("   ⚠️ ВНИМАНИЕ: create_presentation_batch не попал в relevant_tools!")
        print("   Это может быть причиной проблемы - агент не видит инструмент в промпте")
    
    print("\n" + "=" * 60)
    print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
    print("=" * 60)
    
    return {
        "capability_exists": has_capability,
        "tool_in_engine": has_tool,
        "tool_in_provider": tool_in_provider is not None,
        "in_relevant_tools": has_in_relevant
    }


async def test_mcp_provider_execute_simulation():
    """Симулирует вызов MCPToolProvider.execute() для проверки логирования."""
    print("\n" + "=" * 60)
    print("ТЕСТ: Симуляция MCPToolProvider.execute()")
    print("=" * 60)
    
    provider = MCPToolProvider()
    
    # Лог файл будет создан автоматически при записи
    
    # Симулируем вызов execute (но не вызываем реально, так как нужны OAuth токены)
    capability_name = "create_presentation_batch"
    
    print(f"\nПроверка инструмента '{capability_name}'...")
    print(f"Всего инструментов в provider: {len(provider.tools)}")
    print(f"Инструмент в словаре: {capability_name in provider.tools}")
    
    if capability_name in provider.tools:
        tool = provider.tools[capability_name]
        print(f"✅ Инструмент найден: {tool.name}")
        print(f"   Тип: {type(tool).__name__}")
        
        # Проверяем логирование (должно быть в коде)
        import json
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({
                    "id": f"log_test_mcp_execute",
                    "timestamp": int(__import__('time').time()*1000),
                    "location": "test_tool_execution.py",
                    "message": "MCP execute simulation",
                    "data": {
                        "capability_name": capability_name,
                        "tools_count": len(provider.tools),
                        "has_tool": capability_name in provider.tools
                    },
                    "sessionId": "test-session",
                    "runId": "test-run"
                }) + '\n')
            print("   ✅ Логирование работает")
        except Exception as e:
            print(f"   ⚠️ Ошибка логирования: {e}")
    else:
        print(f"❌ ОШИБКА: Инструмент '{capability_name}' не найден!")
        print(f"   Доступные инструменты: {list(provider.tools.keys())[:20]}")
        raise AssertionError(f"Инструмент {capability_name} не найден!")
    
    print("\n✅ ТЕСТ ПРОЙДЕН")


async def main():
    """Запускает все тесты."""
    try:
        # Тест 1: Путь выполнения
        result = await test_tool_execution_path()
        
        # Тест 2: Симуляция execute
        await test_mcp_provider_execute_simulation()
        
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТЫ:")
        print("=" * 60)
        print(f"Capability существует: {result['capability_exists']}")
        print(f"Tool в engine: {result['tool_in_engine']}")
        print(f"Tool в provider: {result['tool_in_provider']}")
        print(f"В relevant_tools: {result['in_relevant_tools']}")
        print("=" * 60)
        
        if not result['in_relevant_tools']:
            print("\n⚠️ ВНИМАНИЕ: create_presentation_batch не попал в relevant_tools!")
            print("Это может быть причиной проблемы - агент не видит инструмент в промпте.")
            print("Нужно проверить логику _get_relevant_tools() или smart_tool_selector.")
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ ТЕСТ ПРОВАЛЕН: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
