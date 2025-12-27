#!/usr/bin/env python3
"""
Тест отправки email через Gmail MCP.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.utils.mcp_loader import get_mcp_manager


async def test_send_email():
    """Тест отправки email."""
    print("=" * 60)
    print("ТЕСТ ОТПРАВКИ EMAIL ЧЕРЕЗ GMAIL MCP")
    print("=" * 60)
    
    try:
        mcp_manager = get_mcp_manager()
        
        # Подключаемся
        print("\n1. Подключение к Gmail MCP...")
        results = await mcp_manager.connect_all()
        if not results.get("gmail"):
            print("❌ Не удалось подключиться к Gmail MCP")
            return
        
        print("✅ Подключено к Gmail MCP")
        
        # Получаем инструменты
        all_tools = mcp_manager.get_all_tools()
        gmail_tools = [t for t in all_tools.keys() if 'send' in t.lower() and 'email' in t.lower()]
        
        if not gmail_tools:
            print("❌ Инструмент send_email не найден")
            return
        
        send_tool = gmail_tools[0]
        print(f"\n2. Найден инструмент: {send_tool}")
        
        # Получаем информацию об инструменте
        tool_info = mcp_manager.get_tool(send_tool)
        if tool_info:
            print(f"   Описание: {tool_info.get('description', 'No description')[:100]}")
            print(f"   Schema: {tool_info.get('inputSchema', {})}")
        
        # Пробуем отправить тестовый email
        print(f"\n3. Подготовка тестового email...")
        print(f"   Кому: petrov@lad24.ru")
        print(f"   Тема: Тестовое письмо от AI системы")
        print(f"   Текст: Это автоматический тест отправки email через Gmail MCP")
        
        # Формируем аргументы (зависит от формата инструмента)
        # Нужно проверить правильный формат
        args = {
            "to": "petrov@lad24.ru",
            "subject": "Тестовое письмо от AI системы",
            "body": "Это автоматический тест отправки email через Gmail MCP интеграцию.\n\nЕсли вы получили это письмо, значит интеграция работает корректно!"
        }
        
        print(f"\n4. Аргументы:")
        import json
        print(json.dumps(args, indent=2, ensure_ascii=False))
        
        print(f"\n5. Вызываем инструмент {send_tool}...")
        try:
            result = await mcp_manager.call_tool(send_tool, args, server_name="gmail")
            print(f"\n✅ УСПЕХ! Email отправлен!")
            print(f"   Результат: {result}")
        except Exception as e:
            print(f"\n❌ ОШИБКА при отправке email:")
            print(f"   Тип: {type(e).__name__}")
            print(f"   Сообщение: {str(e)}")
            print(f"\n   Попробуем другой формат аргументов...")
            
            # Пробуем альтернативный формат
            args2 = {
                "recipient": "petrov@lad24.ru",
                "subject": "Тестовое письмо от AI системы",
                "body": "Это автоматический тест отправки email через Gmail MCP интеграцию."
            }
            try:
                result = await mcp_manager.call_tool(send_tool, args2, server_name="gmail")
                print(f"\n✅ УСПЕХ с альтернативным форматом! Email отправлен!")
                print(f"   Результат: {result}")
            except Exception as e2:
                print(f"\n❌ Ошибка с альтернативным форматом: {e2}")
                import traceback
                traceback.print_exc()
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА:")
        print(f"   {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        await mcp_manager.disconnect_all()
        print("\n✅ Готово!")


if __name__ == "__main__":
    asyncio.run(test_send_email())

