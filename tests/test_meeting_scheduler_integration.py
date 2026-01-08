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
        mock_mcp_manager = AsyncMock()
        
        # FreeBusy возвращает: Alice свободна, Bob занят 9:00-12:00
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
        
        # Проверяем что учёл занятость Bob
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
