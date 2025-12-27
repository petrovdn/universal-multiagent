#!/usr/bin/env python3
"""
Тестовый скрипт для проверки создания встречи через MCP напрямую.
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.mcp_loader import get_mcp_manager
from src.utils.config_loader import get_config


async def test_create_event():
    """Тест создания встречи через MCP."""
    print("=" * 60)
    print("Тест создания встречи через MCP")
    print("=" * 60)
    
    try:
        # Получаем конфигурацию
        config = get_config()
        print(f"Timezone: {config.timezone}")
        
        # Получаем MCP менеджер
        mcp_manager = get_mcp_manager()
        print("\n1. Подключение к MCP серверам...")
        
        # Подключаемся ко всем серверам
        results = await mcp_manager.connect_all()
        print(f"Результаты подключения: {results}")
        
        # Проверяем здоровье серверов
        health = await mcp_manager.health_check()
        print(f"\n2. Статус серверов:")
        for server, status in health.items():
            print(f"  {server}: connected={status['connected']}, tools={status['tools_count']}")
        
        # Получаем список всех инструментов
        all_tools = mcp_manager.get_all_tools()
        print(f"\n3. Доступные инструменты ({len(all_tools)}):")
        for tool_name in sorted(all_tools.keys()):
            print(f"  - {tool_name}")
        
        # Проверяем наличие инструмента create_event
        calendar_tools = [t for t in all_tools.keys() if 'calendar' in t.lower() or 'event' in t.lower()]
        print(f"\n4. Инструменты календаря:")
        for tool_name in calendar_tools:
            print(f"  - {tool_name}")
        
        # Пробуем найти инструмент для создания события
        create_tool_name = None
        for tool_name in all_tools.keys():
            if 'create' in tool_name.lower() and 'event' in tool_name.lower():
                create_tool_name = tool_name
                break
        
        if not create_tool_name:
            print("\n❌ Инструмент для создания события не найден!")
            print("Доступные инструменты:")
            for tool_name in sorted(all_tools.keys()):
                tool_info = all_tools[tool_name]
                print(f"  - {tool_name}: {tool_info.get('description', 'No description')}")
            return
        
        print(f"\n5. Используем инструмент: {create_tool_name}")
        
        # Подготавливаем данные для встречи
        timezone = config.timezone
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        # Создаем встречу на завтра в 10:00
        tomorrow = now + timedelta(days=1)
        start_time = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)
        
        print(f"\n6. Создаем встречу:")
        print(f"   Название: Тестовая встреча")
        print(f"   Начало: {start_time.isoformat()} ({timezone})")
        print(f"   Конец: {end_time.isoformat()} ({timezone})")
        print(f"   Участник: petrov@lad24.ru")
        
        # Формируем аргументы для MCP
        args = {
            "summary": "Тестовая встреча",
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": timezone
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": timezone
            },
            "attendees": [
                {"email": "petrov@lad24.ru"}
            ],
            "description": "Тестовая встреча создана через MCP"
        }
        
        print(f"\n7. Аргументы для MCP:")
        import json
        print(json.dumps(args, indent=2, ensure_ascii=False))
        
        # Вызываем инструмент
        print(f"\n8. Вызываем MCP инструмент {create_tool_name}...")
        try:
            result = await mcp_manager.call_tool(create_tool_name, args, server_name="calendar")
            print(f"\n✅ Успех! Результат:")
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        except Exception as e:
            print(f"\n❌ Ошибка при создании встречи:")
            print(f"   Тип: {type(e).__name__}")
            print(f"   Сообщение: {str(e)}")
            import traceback
            print(f"\n   Traceback:")
            traceback.print_exc()
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка:")
        print(f"   Тип: {type(e).__name__}")
        print(f"   Сообщение: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Отключаемся от всех серверов
        print("\n9. Отключение от MCP серверов...")
        await mcp_manager.disconnect_all()
        print("Готово!")


if __name__ == "__main__":
    asyncio.run(test_create_event())

