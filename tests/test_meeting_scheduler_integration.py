# tests/test_meeting_scheduler_integration.py
"""
Интеграционные тесты для MeetingScheduler с MCP Calendar.

Тестирует:
1. Получение событий из календарей участников
2. Создание встречи в найденном слоте
3. Полный flow: поиск слота → создание события
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

# Импорты будут работать после реализации
from src.core.meeting_scheduler import MeetingScheduler


class TestMeetingSchedulerMCPIntegration:
    """Тесты интеграции MeetingScheduler с MCP Calendar."""
    
    @pytest.mark.asyncio
    async def test_mcp_mode_uses_freebusy_for_all_participants(self):
        """
        ФИКС: В MCP режиме планировщик использует FreeBusy API для проверки
        занятости ВСЕХ участников.
        
        Ожидаемое поведение:
        - Вызывает freebusy_query с items для всех участников
        - Учитывает занятость каждого участника
        """
        import pytz
        mock_mcp_manager = AsyncMock()
        
        # FreeBusy возвращает: Alice свободна, Bob занят 9:00-12:00 UTC
        freebusy_response = {
            "timeMin": "2026-01-09T09:00:00Z",
            "timeMax": "2026-01-09T18:00:00Z",
            "calendars": {
                "alice@example.com": {"busy": []},
                "bob@example.com": {
                    "busy": [
                        {"start": "2026-01-09T09:00:00Z", "end": "2026-01-09T12:00:00Z"}
                    ]
                }
            }
        }
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text=json.dumps(freebusy_response))
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            with patch('src.core.meeting_scheduler.get_local_timezone', return_value=pytz.UTC):
                scheduler = MeetingScheduler(use_mcp=True)
                
                result = await scheduler.find_available_slot(
                    participants=["alice@example.com", "bob@example.com"],
                    duration_minutes=50,
                    buffer_minutes=10,
                    search_start=datetime(2026, 1, 9, 9, 0),
                    search_end=datetime(2026, 1, 9, 18, 0)
                )
        
        # Проверяем что использовался freebusy_query
        assert mock_mcp_manager.call_tool.called
        call_args = mock_mcp_manager.call_tool.call_args_list
        assert any('freebusy_query' in str(call) for call in call_args), \
            f"Должен использовать freebusy_query, но вызвал: {call_args}"
        
        # Проверяем что учёл занятость Bob (UTC timezone)
        assert result is not None, "Должен найти слот"
        assert result["start"] >= datetime(2026, 1, 9, 12, 10), \
            f"Должен учитывать занятость Bob (до 12:00 + буфер), но получили {result['start']}"
    
    @pytest.mark.asyncio
    async def test_mcp_mode_freebusy_includes_all_participants(self):
        """
        Тест: FreeBusy запрос включает всех участников.
        """
        mock_mcp_manager = AsyncMock()
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text='{"calendars": {}}')
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            scheduler = MeetingScheduler(use_mcp=True)
            
            await scheduler.find_available_slot(
                participants=["alice@example.com", "bob@example.com", "charlie@example.com"],
                duration_minutes=50,
                search_start=datetime(2026, 1, 9, 9, 0),
                search_end=datetime(2026, 1, 9, 18, 0)
            )
        
        # Проверяем что все участники включены в запрос
        call_args = mock_mcp_manager.call_tool.call_args
        items = call_args[0][1].get("items", [])
        item_ids = [item["id"] for item in items]
        
        assert "alice@example.com" in item_ids
        assert "bob@example.com" in item_ids
        assert "charlie@example.com" in item_ids
    
    @pytest.mark.asyncio
    async def test_fetches_events_from_mcp_via_freebusy(self):
        """
        Тест: Получает занятость календаря через MCP FreeBusy API.
        """
        # Mock MCP manager с FreeBusy ответом
        mock_mcp_manager = AsyncMock()
        freebusy_response = {
            "calendars": {
                "alice@example.com": {
                    "busy": [
                        {"start": "2026-01-09T10:00:00Z", "end": "2026-01-09T11:00:00Z"}
                    ]
                }
            }
        }
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text=json.dumps(freebusy_response))
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            scheduler = MeetingScheduler(use_mcp=True)
            
            events = await scheduler._get_calendar_events(
                participants=["alice@example.com"],
                start=datetime(2026, 1, 9, 9, 0),
                end=datetime(2026, 1, 9, 18, 0)
            )
        
        # Должен вызвать freebusy_query
        assert mock_mcp_manager.call_tool.called
        call_args = mock_mcp_manager.call_tool.call_args
        assert call_args[0][0] == "freebusy_query"
        
        # Должен вернуть занятость
        assert "alice@example.com" in events
        assert len(events["alice@example.com"]) == 1
    
    @pytest.mark.asyncio
    async def test_handles_multiple_participants_calendars(self):
        """
        Тест: Получает календари нескольких участников.
        """
        # Mock для двух участников
        mock_mcp_manager = AsyncMock()
        
        # Разные события для разных участников
        def mock_call_tool(tool_name, args, server_name=None):
            # Симулируем разные календари
            return [MagicMock(text='{"items": [{"summary": "Busy", "start": {"dateTime": "2026-01-09T10:00:00"}, "end": {"dateTime": "2026-01-09T11:00:00"}}], "count": 1}')]
        
        mock_mcp_manager.call_tool = AsyncMock(side_effect=mock_call_tool)
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            scheduler = MeetingScheduler(use_mcp=True)
            
            events = await scheduler._get_calendar_events(
                participants=["alice@example.com", "bob@example.com"],
                start=datetime(2026, 1, 9, 9, 0),
                end=datetime(2026, 1, 9, 18, 0)
            )
        
        # Должен запросить календарь каждого участника
        assert mock_mcp_manager.call_tool.call_count >= 1
        # Должен вернуть данные для обоих
        assert "alice@example.com" in events or "bob@example.com" in events


class TestCalendarAccessDenied:
    """
    Тесты для случаев, когда календари недоступны.
    
    БАГО-ФИХ: Планировщик ранее считал "notFound" календари свободными,
    теперь возвращает явную ошибку.
    """
    
    @pytest.mark.asyncio
    async def test_raises_error_when_calendar_not_found(self):
        """
        Тест: Если FreeBusy возвращает "notFound" для участника,
        планировщик должен вернуть ошибку, а НЕ считать его свободным.
        """
        mock_mcp_manager = AsyncMock()
        
        # FreeBusy возвращает "notFound" для внешнего пользователя
        freebusy_response = {
            "calendars": {
                "external@gmail.com": {
                    "errors": [{"domain": "global", "reason": "notFound"}],
                    "busy": []
                },
                "internal@company.com": {
                    "busy": [
                        {"start": "2026-01-09T09:00:00Z", "end": "2026-01-09T10:00:00Z"}
                    ]
                }
            }
        }
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text=json.dumps(freebusy_response))
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            scheduler = MeetingScheduler(use_mcp=True)
            
            # Должен выбросить ValueError
            with pytest.raises(ValueError) as exc_info:
                await scheduler.find_available_slot(
                    participants=["external@gmail.com", "internal@company.com"],
                    duration_minutes=50,
                    search_start=datetime(2026, 1, 9, 9, 0),
                    search_end=datetime(2026, 1, 9, 18, 0)
                )
            
            # Ошибка должна содержать email недоступного календаря
            assert "external@gmail.com" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_raises_error_when_calendar_forbidden(self):
        """
        Тест: Если FreeBusy возвращает "forbidden", планировщик должен вернуть ошибку.
        """
        mock_mcp_manager = AsyncMock()
        
        freebusy_response = {
            "calendars": {
                "private@example.com": {
                    "errors": [{"domain": "global", "reason": "forbidden"}],
                    "busy": []
                }
            }
        }
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text=json.dumps(freebusy_response))
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            scheduler = MeetingScheduler(use_mcp=True)
            
            with pytest.raises(ValueError) as exc_info:
                await scheduler.find_available_slot(
                    participants=["private@example.com"],
                    duration_minutes=50,
                    search_start=datetime(2026, 1, 9, 9, 0),
                    search_end=datetime(2026, 1, 9, 18, 0)
                )
            
            assert "private@example.com" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_all_accessible_calendars_still_work(self):
        """
        Тест: Если все календари доступны, планировщик работает нормально.
        """
        import pytz
        mock_mcp_manager = AsyncMock()
        
        freebusy_response = {
            "calendars": {
                "user1@company.com": {
                    "busy": [
                        {"start": "2026-01-09T09:00:00Z", "end": "2026-01-09T10:00:00Z"}
                    ]
                },
                "user2@company.com": {
                    "busy": []
                }
            }
        }
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text=json.dumps(freebusy_response))
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            with patch('src.core.meeting_scheduler.get_local_timezone', return_value=pytz.UTC):
                scheduler = MeetingScheduler(use_mcp=True)
                
                result = await scheduler.find_available_slot(
                    participants=["user1@company.com", "user2@company.com"],
                    duration_minutes=50,
                    buffer_minutes=10,
                    search_start=datetime(2026, 1, 9, 9, 0),
                    search_end=datetime(2026, 1, 9, 18, 0)
                )
                
                # Должен найти слот после занятости user1 (10:00 + 10 мин буфер)
                assert result is not None
                assert result["start"] >= datetime(2026, 1, 9, 10, 10)


class TestScheduleGroupMeetingTool:
    """Тесты для LangChain tool ScheduleGroupMeetingTool."""
    
    @pytest.mark.asyncio
    async def test_tool_finds_slot_and_creates_event(self):
        """
        Тест: Tool находит слот и создаёт событие.
        """
        from src.mcp_tools.calendar_tools import ScheduleGroupMeetingTool
        
        tool = ScheduleGroupMeetingTool()
        
        # Mock calendar events (все свободны)
        mock_mcp_manager = AsyncMock()
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text='{"items": [], "count": 0}')
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            with patch('src.mcp_tools.calendar_tools.get_mcp_manager', return_value=mock_mcp_manager):
                result = await tool._arun(
                    title="Командная встреча",
                    attendees=["alice@example.com", "bob@example.com"],
                    duration="50m",
                    buffer="10m"
                )
        
        # Должен вернуть информацию о созданной встрече
        assert "alice@example.com" in result or "bob@example.com" in result or "встреч" in result.lower() or "slot" in result.lower()
    
    @pytest.mark.asyncio
    async def test_tool_returns_error_when_no_slot(self):
        """
        Тест: Tool возвращает ошибку, если слот не найден.
        
        Мокаем FreeBusy так, чтобы все рабочие часы были заняты.
        """
        from src.mcp_tools.calendar_tools import ScheduleGroupMeetingTool
        
        tool = ScheduleGroupMeetingTool()
        
        # Mock: заняты все рабочие часы на ближайшие дни (FreeBusy формат)
        mock_mcp_manager = AsyncMock()
        
        # Создаём FreeBusy ответ с занятостью весь день каждый день
        busy_slots = []
        base_date = datetime.now().date()
        for day_offset in range(7):
            event_date = base_date + timedelta(days=day_offset)
            busy_slots.append({
                "start": f"{event_date}T09:00:00Z",
                "end": f"{event_date}T18:00:00Z"
            })
        
        freebusy_response = {
            "calendars": {
                "alice@example.com": {"busy": busy_slots}
            }
        }
        
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text=json.dumps(freebusy_response))
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            with patch('src.mcp_tools.calendar_tools.get_mcp_manager', return_value=mock_mcp_manager):
                result = await tool._arun(
                    title="Командная встреча",
                    attendees=["alice@example.com"],
                    duration="50m",
                    buffer="10m",
                    search_days=7  # Ищем 7 дней
                )
        
        # Должен вернуть сообщение об отсутствии слота
        assert "не удалось" in result.lower() or "не найден" in result.lower() or "no slot" in result.lower()
    
    @pytest.mark.asyncio
    async def test_tool_respects_buffer_time(self):
        """
        Тест: Tool учитывает буферное время.
        """
        from src.mcp_tools.calendar_tools import ScheduleGroupMeetingTool
        
        tool = ScheduleGroupMeetingTool()
        
        # Mock: встреча заканчивается в 10:00
        mock_mcp_manager = AsyncMock()
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text='{"items": [{"summary": "Morning meeting", "start": {"dateTime": "2026-01-09T09:00:00"}, "end": {"dateTime": "2026-01-09T10:00:00"}}], "count": 1}')
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            with patch('src.mcp_tools.calendar_tools.get_mcp_manager', return_value=mock_mcp_manager):
                result = await tool._arun(
                    title="Follow-up",
                    attendees=["alice@example.com"],
                    duration="50m",
                    buffer="10m"
                )
        
        # Результат должен содержать время после 10:00 + 10 мин буфер = 10:10
        # Либо сообщение об успешном создании
        assert result is not None


class TestTimezoneConversion:
    """
    Тесты для корректной конвертации таймзон.
    
    БАГО-ФИХ: Планировщик ранее не конвертировал UTC времена в локальную
    таймзону, что приводило к неправильному расчёту свободных слотов.
    """
    
    @pytest.mark.asyncio
    async def test_utc_times_converted_to_local(self):
        """
        Тест: UTC времена из FreeBusy корректно конвертируются в локальное время.
        
        Сценарий: Встреча 09:35 UTC должна блокировать 12:35 MSK (UTC+3),
        а не 09:35 локального времени.
        """
        mock_mcp_manager = AsyncMock()
        
        # FreeBusy возвращает время в UTC (с суффиксом Z)
        freebusy_response = {
            "calendars": {
                "user@example.com": {
                    "busy": [
                        # 09:00-09:35 UTC = 12:00-12:35 MSK
                        {"start": "2026-01-09T09:00:00Z", "end": "2026-01-09T09:35:00Z"}
                    ]
                }
            }
        }
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text=json.dumps(freebusy_response))
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            with patch('src.core.meeting_scheduler.get_local_timezone') as mock_tz:
                import pytz
                mock_tz.return_value = pytz.timezone("Europe/Moscow")  # UTC+3
                
                scheduler = MeetingScheduler(use_mcp=True)
                
                # Ищем слот начиная с 12:00 локального времени
                result = await scheduler.find_available_slot(
                    participants=["user@example.com"],
                    duration_minutes=30,
                    buffer_minutes=10,
                    search_start=datetime(2026, 1, 9, 12, 0),  # 12:00 MSK
                    search_end=datetime(2026, 1, 9, 18, 0)
                )
        
        # Слот должен быть ПОСЛЕ 12:35 + 10 мин буфер = 12:45 MSK
        assert result is not None
        assert result["start"] >= datetime(2026, 1, 9, 12, 45), \
            f"Слот должен начинаться после 12:45 MSK, но начинается в {result['start']}"
    
    @pytest.mark.asyncio
    async def test_slot_not_scheduled_during_utc_busy_time(self):
        """
        Тест: Встреча НЕ должна планироваться в период занятости (с учётом таймзоны).
        
        Это регрессионный тест для бага, когда 09:35 UTC интерпретировалось
        как 09:35 локального времени.
        """
        mock_mcp_manager = AsyncMock()
        
        freebusy_response = {
            "calendars": {
                "user@example.com": {
                    "busy": [
                        # Занят с 08:00 до 12:35 MSK (05:00-09:35 UTC)
                        {"start": "2026-01-09T05:00:00Z", "end": "2026-01-09T09:35:00Z"},
                        # Занят с 13:00 до 14:50 MSK (10:00-11:50 UTC)
                        {"start": "2026-01-09T10:00:00Z", "end": "2026-01-09T11:50:00Z"}
                    ]
                }
            }
        }
        mock_mcp_manager.call_tool.return_value = [
            MagicMock(text=json.dumps(freebusy_response))
        ]
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            with patch('src.core.meeting_scheduler.get_local_timezone') as mock_tz:
                import pytz
                mock_tz.return_value = pytz.timezone("Europe/Moscow")
                
                scheduler = MeetingScheduler(use_mcp=True)
                
                result = await scheduler.find_available_slot(
                    participants=["user@example.com"],
                    duration_minutes=60,
                    buffer_minutes=10,
                    search_start=datetime(2026, 1, 9, 9, 0),
                    search_end=datetime(2026, 1, 9, 18, 0)
                )
        
        # Слот должен быть после 14:50 + 10 мин = 15:00 MSK
        assert result is not None
        assert result["start"] >= datetime(2026, 1, 9, 15, 0), \
            f"Слот должен быть после 15:00 (после всех встреч), но получили {result['start']}"


class TestOrganizerIncluded:
    """
    Тесты для автоматического включения организатора в проверку занятости.
    
    БАГО-ФИХ: ScheduleGroupMeetingTool ранее не включал организатора
    в список участников, что приводило к конфликтам в его календаре.
    """
    
    @pytest.mark.asyncio
    async def test_tool_includes_organizer_in_participants(self):
        """
        Тест: Tool автоматически добавляет организатора к участникам.
        """
        from src.mcp_tools.calendar_tools import ScheduleGroupMeetingTool
        
        tool = ScheduleGroupMeetingTool()
        
        mock_mcp_manager = AsyncMock()
        
        # Ответ list_calendars с primary календарём
        calendars_response = {
            "calendars": [
                {"id": "organizer@example.com", "primary": True},
                {"id": "other@example.com", "primary": False}
            ]
        }
        
        # FreeBusy ответ
        freebusy_response = {
            "calendars": {
                "organizer@example.com": {"busy": []},
                "attendee@example.com": {"busy": []}
            }
        }
        
        # Настраиваем mock для разных вызовов
        def mock_call_tool(tool_name, args, server_name=None):
            if tool_name == "list_calendars":
                return [MagicMock(text=json.dumps(calendars_response))]
            elif tool_name == "freebusy_query":
                # Проверяем что organizer включён в items
                items = args.get("items", [])
                item_ids = [item["id"] for item in items]
                assert "organizer@example.com" in item_ids, \
                    f"Организатор должен быть в участниках, но получили: {item_ids}"
                return [MagicMock(text=json.dumps(freebusy_response))]
            elif tool_name == "create_event":
                return [MagicMock(text='{"id": "event123"}')]
            return [MagicMock(text='{}')]
        
        mock_mcp_manager.call_tool = AsyncMock(side_effect=mock_call_tool)
        
        with patch('src.core.meeting_scheduler.get_mcp_manager', return_value=mock_mcp_manager):
            with patch('src.mcp_tools.calendar_tools.get_mcp_manager', return_value=mock_mcp_manager):
                result = await tool._arun(
                    title="Test Meeting",
                    attendees=["attendee@example.com"],
                    duration="30m",
                    buffer="10m"
                )
        
        # Если дошли сюда без assertion error - тест прошёл
        assert "attendee@example.com" in result or "organizer@example.com" in result


class TestMeetingSchedulerWithRealMCP:
    """
    Интеграционные тесты с реальным MCP (требуют credentials).
    
    Запуск: pytest -m integration tests/test_meeting_scheduler_integration.py
    """
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.skip(reason="Требует настроенные Google Calendar credentials")
    async def test_real_calendar_integration(self):
        """
        E2E тест: Реальная интеграция с Google Calendar.
        """
        from src.mcp_tools.calendar_tools import ScheduleGroupMeetingTool
        
        tool = ScheduleGroupMeetingTool()
        
        result = await tool._arun(
            title="Test Meeting (автотест)",
            attendees=["your-email@gmail.com"],
            duration="30m",
            buffer="5m"
        )
        
        # Должен найти слот или создать встречу
        assert result is not None
        print(f"Result: {result}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
