#!/usr/bin/env python3
"""
Диагностический скрипт для отладки планировщика встреч.
Запуск: python scripts/debug_meeting_scheduler.py

Тестирует MeetingScheduler с реальным MCP Calendar сервером.
"""
import asyncio
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем корень проекта в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.meeting_scheduler import MeetingScheduler

# Путь к debug логам
DEBUG_LOG = Path("/Users/Dima/universal-multiagent/.cursor/debug.log")


def log(location: str, message: str, data: dict, hypothesis: str = "DIAG"):
    """Записывает диагностический лог."""
    entry = {
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(datetime.now().timestamp() * 1000),
        "sessionId": "debug-script",
        "hypothesisId": hypothesis
    }
    with open(DEBUG_LOG, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    # Также выводим в консоль
    print(f"[{hypothesis}] {message}: {json.dumps(data, default=str, ensure_ascii=False)[:200]}")


async def test_freebusy_directly():
    """Тестируем FreeBusy напрямую через MCP."""
    print("\n" + "=" * 70)
    print("🔬 ТЕСТ 1: FreeBusy запрос напрямую через MCP")
    print("=" * 70)
    
    from src.mcp_tools.calendar_tools import get_calendar_tools
    
    tools = get_calendar_tools()  # Синхронная функция
    freebusy_tool = None
    
    for tool in tools:
        if tool.name == "freebusy_query":
            freebusy_tool = tool
            break
    
    if not freebusy_tool:
        print("❌ freebusy_query tool не найден!")
        log("test_freebusy", "freebusy_query not found", {"tools": [t.name for t in tools]}, "A")
        return
    
    participants = [
        "dn.petrovdn@gmail.com",
        "dp.projectlad@gmail.com",
        "petrov@lad24.ru"
    ]
    
    now = datetime.now()
    time_min = now.isoformat()
    time_max = (now + timedelta(days=1)).isoformat()
    
    print(f"\n📋 Участники: {participants}")
    print(f"⏰ Период: {time_min} → {time_max}")
    
    log("test_freebusy", "Calling freebusy_query", {
        "participants": participants,
        "time_min": time_min,
        "time_max": time_max
    }, "A")
    
    try:
        result = await freebusy_tool._arun(
            attendees=json.dumps(participants),
            time_min=time_min,
            time_max=time_max
        )
        
        log("test_freebusy", "freebusy_query result", {"result": result}, "A")
        
        print(f"\n📊 Результат FreeBusy:")
        print(result)
        
        # Парсим результат
        if isinstance(result, str):
            try:
                result_data = json.loads(result)
            except:
                result_data = {"raw": result}
        else:
            result_data = result
            
        print(f"\n📊 Parsed:")
        print(json.dumps(result_data, indent=2, default=str, ensure_ascii=False))
        
    except Exception as e:
        log("test_freebusy", "freebusy_query error", {"error": str(e)}, "A")
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


async def test_meeting_scheduler_internal():
    """Тестируем MeetingScheduler только с внутренними пользователями."""
    print("\n" + "=" * 70)
    print("🔬 ТЕСТ 4: MeetingScheduler - внутренние пользователи (lad24.ru)")
    print("=" * 70)
    
    # Пользователи из того же домена - должен быть доступ к календарям
    participants = [
        "petrov@lad24.ru",
        "bsn@lad24.ru"
    ]
    
    duration_minutes = 60
    buffer_minutes = 10
    
    print(f"\n📋 Участники: {participants}")
    print(f"⏱  Длительность: {duration_minutes} мин")
    print(f"🔄 Буфер: {buffer_minutes} мин")
    
    scheduler = MeetingScheduler(use_mcp=True)
    
    search_start = datetime.now()
    search_end = search_start + timedelta(days=7)
    
    print(f"\n🔎 Поиск слота: {search_start.strftime('%Y-%m-%d %H:%M')} → {search_end.strftime('%Y-%m-%d %H:%M')}")
    print("-" * 70)
    
    # ДЕТАЛЬНАЯ ДИАГНОСТИКА: Сначала получаем календари
    print("\n📊 ДЕТАЛЬНЫЙ АНАЛИЗ ЗАНЯТОСТИ:")
    print("-" * 70)
    
    try:
        calendars = await scheduler._get_calendar_events(
            participants=participants,
            start=search_start,
            end=search_end
        )
        
        for email, busy_slots in calendars.items():
            print(f"\n📧 {email}: {len(busy_slots)} занятых слотов")
            for i, slot in enumerate(busy_slots):
                start_str = slot.get('start', 'N/A')
                end_str = slot.get('end', 'N/A')
                print(f"   {i+1}. {start_str} → {end_str}")
        
        # Анализ 9 января отдельно
        print("\n📅 АНАЛИЗ 9 ЯНВАРЯ:")
        jan9_start = datetime(2026, 1, 9, 0, 0)
        jan9_end = datetime(2026, 1, 9, 23, 59)
        for email, busy_slots in calendars.items():
            jan9_slots = []
            for slot in busy_slots:
                # Parse slot times
                start_str = slot.get('start', '')
                end_str = slot.get('end', '')
                try:
                    if 'Z' in start_str:
                        start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                        # Convert to naive for comparison
                        start_dt = start_dt.replace(tzinfo=None)
                        end_dt = end_dt.replace(tzinfo=None)
                    else:
                        start_dt = datetime.fromisoformat(start_str)
                        end_dt = datetime.fromisoformat(end_str)
                    
                    # Check if overlaps with Jan 9
                    if start_dt < jan9_end and end_dt > jan9_start:
                        duration_hours = (end_dt - start_dt).total_seconds() / 3600
                        jan9_slots.append(f"{start_str} → {end_str} ({duration_hours:.1f}ч)")
                except:
                    pass
            
            if jan9_slots:
                print(f"   {email}:")
                for s in jan9_slots:
                    print(f"      - {s}")
            
    except Exception as e:
        print(f"💥 Ошибка получения календарей: {e}")
    
    print("\n" + "-" * 70)
    print("🔍 ПОИСК СЛОТА:")
    
    log("test_internal", "Starting find_available_slot with internal users", {
        "participants": participants,
        "duration": duration_minutes,
        "buffer": buffer_minutes
    }, "INTERNAL")
    
    try:
        result = await scheduler.find_available_slot(
            participants=participants,
            duration_minutes=duration_minutes,
            buffer_minutes=buffer_minutes,
            search_start=search_start,
            search_end=search_end
        )
        
        log("test_internal", "find_available_slot result", {
            "result": result
        }, "INTERNAL")
        
        if result:
            print(f"\n✅ Найден слот:")
            print(f"   📅 Начало: {result['start']}")
            print(f"   📅 Конец:  {result['end']}")
        else:
            print(f"\n❌ Слот не найден")
            
    except Exception as e:
        log("test_internal", "find_available_slot error", {"error": str(e)}, "INTERNAL")
        print(f"\n💥 Ошибка: {e}")


async def test_meeting_scheduler():
    """Тестируем MeetingScheduler с внешними пользователями."""
    print("\n" + "=" * 70)
    print("🔬 ТЕСТ 2: MeetingScheduler.find_available_slot (внешние пользователи)")
    print("=" * 70)
    
    participants = [
        "dn.petrovdn@gmail.com",
        "dp.projectlad@gmail.com",
        "petrov@lad24.ru"
    ]
    
    duration_minutes = 120
    buffer_minutes = 10
    
    print(f"\n📋 Участники: {participants}")
    print(f"⏱  Длительность: {duration_minutes} мин")
    print(f"🔄 Буфер: {buffer_minutes} мин")
    
    scheduler = MeetingScheduler(use_mcp=True)
    
    search_start = datetime.now()
    search_end = search_start + timedelta(days=7)
    
    print(f"\n🔎 Поиск слота: {search_start.strftime('%Y-%m-%d %H:%M')} → {search_end.strftime('%Y-%m-%d %H:%M')}")
    print("-" * 70)
    
    log("test_scheduler", "Starting find_available_slot", {
        "participants": participants,
        "duration": duration_minutes,
        "buffer": buffer_minutes,
        "search_start": search_start.isoformat(),
        "search_end": search_end.isoformat()
    }, "B")
    
    try:
        result = await scheduler.find_available_slot(
            participants=participants,
            duration_minutes=duration_minutes,
            buffer_minutes=buffer_minutes,
            search_start=search_start,
            search_end=search_end
        )
        
        log("test_scheduler", "find_available_slot result", {
            "result": result
        }, "B")
        
        if result:
            print(f"\n✅ Найден слот:")
            print(f"   📅 Начало: {result['start']}")
            print(f"   📅 Конец:  {result['end']}")
            
            # Проверяем - не сейчас ли это?
            slot_start = result['start']
            if hasattr(slot_start, 'replace'):
                slot_start_naive = slot_start.replace(tzinfo=None)
            else:
                slot_start_naive = slot_start
                
            time_diff = (slot_start_naive - datetime.now()).total_seconds() / 60
            
            if time_diff < 30:
                print(f"\n⚠️  ВНИМАНИЕ: Слот начинается через {time_diff:.0f} минут!")
                print(f"   Это может означать, что занятость участников НЕ учтена!")
            else:
                print(f"\n✅ Слот через {time_diff:.0f} минут - выглядит корректно")
        else:
            print(f"\n❌ Слот не найден")
            
    except Exception as e:
        log("test_scheduler", "find_available_slot error", {"error": str(e)}, "B")
        print(f"\n💥 Ошибка: {e}")
        import traceback
        traceback.print_exc()


async def test_get_calendar_events():
    """Тестируем _get_calendar_events напрямую."""
    print("\n" + "=" * 70)
    print("🔬 ТЕСТ 3: MeetingScheduler._get_calendar_events (внутренний метод)")
    print("=" * 70)
    
    participants = [
        "dn.petrovdn@gmail.com",
        "dp.projectlad@gmail.com",
        "petrov@lad24.ru"
    ]
    
    scheduler = MeetingScheduler(use_mcp=True)
    
    start = datetime.now()
    end = start + timedelta(days=1)
    
    print(f"\n📋 Участники: {participants}")
    print(f"⏰ Период: {start.strftime('%Y-%m-%d %H:%M')} → {end.strftime('%Y-%m-%d %H:%M')}")
    
    log("test_get_events", "Calling _get_calendar_events", {
        "participants": participants,
        "start": start.isoformat(),
        "end": end.isoformat()
    }, "C")
    
    try:
        calendars = await scheduler._get_calendar_events(
            participants=participants,
            start=start,
            end=end
        )
        
        log("test_get_events", "_get_calendar_events result", {
            "calendars_keys": list(calendars.keys()),
            "calendars": {k: len(v) for k, v in calendars.items()}
        }, "C")
        
        print(f"\n📊 Результат _get_calendar_events:")
        print(f"   Календарей: {len(calendars)}")
        
        for email, busy_slots in calendars.items():
            print(f"\n   📧 {email}: {len(busy_slots)} занятых слотов")
            for i, slot in enumerate(busy_slots[:5]):
                print(f"      {i+1}. {slot.get('start')} → {slot.get('end')}")
            if len(busy_slots) > 5:
                print(f"      ... и ещё {len(busy_slots) - 5} слотов")
                
    except Exception as e:
        log("test_get_events", "_get_calendar_events error", {"error": str(e)}, "C")
        print(f"\n💥 Ошибка: {e}")
        import traceback
        traceback.print_exc()


async def test_create_meeting():
    """Создаём реальную встречу с bsn@lad24.ru."""
    print("\n" + "=" * 70)
    print("🔬 ТЕСТ 5: Создание реальной встречи")
    print("=" * 70)
    
    from src.mcp_tools.calendar_tools import ScheduleGroupMeetingTool
    
    tool = ScheduleGroupMeetingTool()
    
    print("\n📋 Параметры:")
    print("   Название: Тестовая встреча (автотест)")
    print("   Участники: bsn@lad24.ru")
    print("   Длительность: 60 мин")
    print("   Буфер: 10 мин")
    
    try:
        result = await tool._arun(
            title="Тестовая встреча (автотест)",
            attendees=["bsn@lad24.ru"],
            duration="60m",
            buffer="10m"
        )
        
        print(f"\n📊 Результат:")
        print(result)
        
        log("test_create", "Meeting created", {"result": result}, "CREATE")
        
    except Exception as e:
        print(f"\n💥 Ошибка: {e}")
        import traceback
        traceback.print_exc()
        log("test_create", "Error creating meeting", {"error": str(e)}, "CREATE")


async def main():
    print("=" * 70)
    print("🔍 ДИАГНОСТИКА: MeetingScheduler с реальным MCP")
    print("=" * 70)
    print(f"📝 Логи записываются в: {DEBUG_LOG}")
    
    # Очищаем лог файл
    if DEBUG_LOG.exists():
        DEBUG_LOG.unlink()
    DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    log("main", "Diagnostic script started", {}, "START")
    
    # Тест 1: FreeBusy напрямую
    await test_freebusy_directly()
    
    # Тест 2: _get_calendar_events
    await test_get_calendar_events()
    
    # Тест 3: find_available_slot (внешние пользователи - должен вернуть ошибку)
    await test_meeting_scheduler()
    
    # Тест 4: find_available_slot (внутренние пользователи - должен работать)
    await test_meeting_scheduler_internal()
    
    log("main", "Diagnostic script completed", {}, "END")
    
    print("\n" + "=" * 70)
    print("✅ Диагностика завершена")
    print(f"📝 Полные логи: {DEBUG_LOG}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
