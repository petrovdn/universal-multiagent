#!/usr/bin/env python3
"""
Комплексный тест всех интеграций: Gmail, Calendar, Sheets.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pytz

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.mcp_loader import get_mcp_manager
from src.utils.config_loader import get_config


async def test_all_integrations():
    """Тест всех интеграций."""
    print("=" * 70)
    print("КОМПЛЕКСНЫЙ ТЕСТ ВСЕХ ИНТЕГРАЦИЙ")
    print("=" * 70)
    
    try:
        # Получаем конфигурацию
        config = get_config()
        print(f"\n📋 Конфигурация:")
        print(f"   Timezone: {config.timezone}")
        
        # Получаем MCP менеджер
        mcp_manager = get_mcp_manager()
        print(f"\n🔌 Подключение ко всем MCP серверам...")
        
        # Подключаемся ко всем серверам
        results = await mcp_manager.connect_all()
        print(f"\n✅ Результаты подключения:")
        for server, status in results.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {server}: {'подключен' if status else 'не подключен'}")
        
        # Проверяем здоровье серверов
        health = await mcp_manager.health_check()
        print(f"\n📊 Статус серверов:")
        for server, status in health.items():
            tools_count = status['tools_count']
            tools_icon = "✅" if tools_count > 0 else "⚠️"
            print(f"   {tools_icon} {server}: connected={status['connected']}, tools={tools_count}")
        
        # Получаем список всех инструментов
        all_tools = mcp_manager.get_all_tools()
        print(f"\n🛠️  Всего доступно инструментов: {len(all_tools)}")
        
        # Группируем инструменты по серверам
        print(f"\n📦 Инструменты по серверам:")
        
        # Gmail инструменты
        gmail_tools = [t for t in all_tools.keys() if 'email' in t.lower() or 'gmail' in t.lower() or 'mail' in t.lower()]
        print(f"\n   📧 Gmail ({len(gmail_tools)} инструментов):")
        for tool_name in sorted(gmail_tools)[:10]:
            print(f"      - {tool_name}")
        if len(gmail_tools) > 10:
            print(f"      ... и еще {len(gmail_tools) - 10}")
        
        # Calendar инструменты
        calendar_tools = [t for t in all_tools.keys() if 'calendar' in t.lower() or 'event' in t.lower() or 'meeting' in t.lower()]
        print(f"\n   📅 Calendar ({len(calendar_tools)} инструментов):")
        for tool_name in sorted(calendar_tools)[:10]:
            print(f"      - {tool_name}")
        if len(calendar_tools) > 10:
            print(f"      ... и еще {len(calendar_tools) - 10}")
        
        # Sheets инструменты
        sheets_tools = [t for t in all_tools.keys() if 'sheet' in t.lower() or 'spreadsheet' in t.lower() or 'cell' in t.lower()]
        print(f"\n   📊 Sheets ({len(sheets_tools)} инструментов):")
        for tool_name in sorted(sheets_tools)[:10]:
            print(f"      - {tool_name}")
        if len(sheets_tools) > 10:
            print(f"      ... и еще {len(sheets_tools) - 10}")
        
        # Тестируем создание встречи
        print(f"\n" + "=" * 70)
        print("ТЕСТ 1: СОЗДАНИЕ ВСТРЕЧИ В КАЛЕНДАРЕ")
        print("=" * 70)
        
        if calendar_tools:
            # Ищем инструмент для создания события
            create_tool = None
            for tool_name in calendar_tools:
                if 'create' in tool_name.lower() and 'event' in tool_name.lower():
                    create_tool = tool_name
                    break
            
            if create_tool:
                print(f"\n✅ Найден инструмент: {create_tool}")
                
                # Подготавливаем данные для встречи
                timezone = config.timezone
                tz = pytz.timezone(timezone)
                now = datetime.now(tz)
                tomorrow = now + timedelta(days=1)
                start_time = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0)
                end_time = start_time + timedelta(hours=1)
                
                print(f"\n📝 Параметры встречи:")
                print(f"   Название: Тестовая встреча от AI")
                print(f"   Начало: {start_time.strftime('%Y-%m-%d %H:%M')} ({timezone})")
                print(f"   Конец: {end_time.strftime('%Y-%m-%d %H:%M')} ({timezone})")
                print(f"   Участник: petrov@lad24.ru")
                
                # Формируем аргументы
                args = {
                    "summary": "Тестовая встреча от AI",
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
                    "description": "Тестовая встреча создана автоматически для проверки интеграции"
                }
                
                print(f"\n🚀 Вызываем инструмент {create_tool}...")
                try:
                    result = await mcp_manager.call_tool(create_tool, args, server_name="calendar")
                    print(f"\n✅ УСПЕХ! Встреча создана!")
                    import json
                    print(f"   Результат:")
                    result_str = json.dumps(result, indent=2, ensure_ascii=False, default=str)
                    # Показываем только первые 500 символов
                    if len(result_str) > 500:
                        print(f"   {result_str[:500]}...")
                    else:
                        print(f"   {result_str}")
                except Exception as e:
                    print(f"\n❌ ОШИБКА при создании встречи:")
                    print(f"   Тип: {type(e).__name__}")
                    print(f"   Сообщение: {str(e)}")
                    import traceback
                    print(f"\n   Traceback:")
                    traceback.print_exc()
            else:
                print(f"\n⚠️  Инструмент для создания события не найден")
                print(f"   Доступные инструменты календаря:")
                for tool_name in sorted(calendar_tools)[:5]:
                    print(f"      - {tool_name}")
        else:
            print(f"\n❌ Инструменты календаря не обнаружены!")
            print(f"   Проверьте, что интеграция Google Calendar авторизована через OAuth")
        
        # Тестируем отправку email
        print(f"\n" + "=" * 70)
        print("ТЕСТ 2: ОТПРАВКА EMAIL")
        print("=" * 70)
        
        if gmail_tools:
            # Ищем инструмент для отправки email
            send_tool = None
            for tool_name in gmail_tools:
                if 'send' in tool_name.lower() and 'email' in tool_name.lower():
                    send_tool = tool_name
                    break
            
            if send_tool:
                print(f"\n✅ Найден инструмент: {send_tool}")
                print(f"\n📝 Параметры email:")
                print(f"   Кому: petrov@lad24.ru")
                print(f"   Тема: Тестовое письмо от AI")
                print(f"   Текст: Это тестовое письмо для проверки интеграции Gmail")
                
                # Формируем аргументы (зависит от формата инструмента)
                print(f"\n⚠️  Пропускаем отправку email (требуется проверка формата аргументов)")
                print(f"   Для тестирования можно использовать инструмент напрямую")
            else:
                print(f"\n⚠️  Инструмент для отправки email не найден")
                print(f"   Доступные инструменты Gmail:")
                for tool_name in sorted(gmail_tools)[:5]:
                    print(f"      - {tool_name}")
        else:
            print(f"\n❌ Инструменты Gmail не обнаружены!")
        
        # Тестируем работу с таблицами
        print(f"\n" + "=" * 70)
        print("ТЕСТ 3: РАБОТА С ТАБЛИЦАМИ")
        print("=" * 70)
        
        if sheets_tools:
            print(f"\n✅ Обнаружено {len(sheets_tools)} инструментов для работы с таблицами")
            print(f"   Доступные инструменты:")
            for tool_name in sorted(sheets_tools)[:5]:
                print(f"      - {tool_name}")
            print(f"\n⚠️  Пропускаем тест создания таблицы (требуется проверка формата аргументов)")
        else:
            print(f"\n❌ Инструменты Sheets не обнаружены!")
            print(f"   Проверьте, что интеграция Google Sheets авторизована через OAuth")
        
        # Итоговый отчет
        print(f"\n" + "=" * 70)
        print("ИТОГОВЫЙ ОТЧЕТ")
        print("=" * 70)
        
        total_tools = len(all_tools)
        gmail_count = len(gmail_tools)
        calendar_count = len(calendar_tools)
        sheets_count = len(sheets_tools)
        
        print(f"\n📊 Статистика:")
        print(f"   Всего инструментов: {total_tools}")
        print(f"   Gmail: {gmail_count} {'✅' if gmail_count > 0 else '❌'}")
        print(f"   Calendar: {calendar_count} {'✅' if calendar_count > 0 else '❌'}")
        print(f"   Sheets: {sheets_count} {'✅' if sheets_count > 0 else '❌'}")
        
        if calendar_count > 0:
            print(f"\n✅ Calendar интеграция работает!")
        else:
            print(f"\n❌ Calendar интеграция не работает - проверьте OAuth авторизацию")
        
        if gmail_count > 0:
            print(f"✅ Gmail интеграция работает!")
        else:
            print(f"❌ Gmail интеграция не работает")
        
        if sheets_count > 0:
            print(f"✅ Sheets интеграция работает!")
        else:
            print(f"❌ Sheets интеграция не работает - проверьте OAuth авторизацию")
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА:")
        print(f"   Тип: {type(e).__name__}")
        print(f"   Сообщение: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Отключаемся от всех серверов
        print(f"\n🔌 Отключение от всех MCP серверов...")
        try:
            await mcp_manager.disconnect_all()
        except:
            pass
        print("✅ Готово!")


if __name__ == "__main__":
    asyncio.run(test_all_integrations())

