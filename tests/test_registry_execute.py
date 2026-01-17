"""
Тест для проверки registry.execute() - симулирует реальный вызов.
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


async def test_registry_execute():
    """Проверяет, что registry.execute() может найти и вызвать инструмент."""
    print("=" * 60)
    print("ТЕСТ: registry.execute() для create_presentation_batch")
    print("=" * 60)
    
    # Инициализация
    registry = CapabilityRegistry()
    mcp_provider = MCPToolProvider()
    registry.register_provider(mcp_provider)
    a2a_provider = A2AAgentProvider()
    registry.register_provider(a2a_provider)
    
    capability_name = "create_presentation_batch"
    
    print(f"\n1. Проверка capability в registry...")
    capabilities = registry.get_capabilities()
    capability = next((cap for cap in capabilities if cap.name == capability_name), None)
    
    if capability:
        print(f"   ✅ Capability найден: {capability.name}")
        print(f"   Категория: {capability.category}")
        print(f"   Провайдер: {capability.provider_type}")
    else:
        print(f"   ❌ Capability не найден!")
        return False
    
    print(f"\n2. Проверка provider в registry...")
    provider, cap = registry._capability_map.get(capability_name, (None, None))
    
    if provider:
        print(f"   ✅ Provider найден: {type(provider).__name__}")
        print(f"   Provider type: {provider.provider_type.value}")
    else:
        print(f"   ❌ Provider не найден в _capability_map!")
        return False
    
    print(f"\n3. Проверка инструмента в provider.tools...")
    if hasattr(provider, 'tools'):
        tool = provider.tools.get(capability_name)
        if tool:
            print(f"   ✅ Инструмент найден в provider.tools: {tool.name}")
        else:
            print(f"   ❌ Инструмент НЕ найден в provider.tools!")
            print(f"   Доступные инструменты: {list(provider.tools.keys())[:20]}")
            return False
    else:
        print(f"   ❌ Provider не имеет атрибута 'tools'!")
        return False
    
    print(f"\n4. Симуляция registry.execute() (без реального вызова)...")
    # Не вызываем реально, так как нужны OAuth токены
    # Но проверяем, что все компоненты на месте
    
    # Проверяем, что execute() не вызовет ValueError
    if capability_name in provider.tools:
        print(f"   ✅ Инструмент доступен для execute()")
        print(f"   ✅ execute() НЕ вызовет ValueError('Unknown capability')")
    else:
        print(f"   ❌ Инструмент НЕ доступен - execute() вызовет ValueError!")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
    print("=" * 60)
    print("\nВЫВОД:")
    print("  - Capability зарегистрирован в registry")
    print("  - Provider найден в _capability_map")
    print("  - Инструмент найден в provider.tools")
    print("  - execute() НЕ вызовет ошибку 'Unknown capability'")
    print("\nЕсли в реальном выполнении возникает ошибка 'инструмент не найден',")
    print("проблема НЕ в загрузке инструментов, а в другом месте:")
    print("  - Возможно, агент вызывает инструмент с неправильным именем")
    print("  - Или есть проблема в обработке ошибок")
    print("  - Или агент видит только FINISH из-за другой логики")
    
    return True


async def main():
    """Запускает тест."""
    try:
        result = await test_registry_execute()
        return 0 if result else 1
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
