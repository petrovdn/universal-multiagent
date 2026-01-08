# tests/test_meeting_scheduler.py
"""
TDD-тесты для планировщика встреч с несколькими участниками.

Функциональность:
- Поиск первого свободного окна для всех участников
- Учёт буферного времени между встречами (по умолчанию 10 мин)
- Учёт рабочих часов

Создано по TDD-подходу: тесты написаны ДО реализации функции.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

# Импорт будущей функции (пока не существует — тесты должны падать)
# from src.core.meeting_scheduler import MeetingScheduler


# ============================================================================
# ТЕСТЫ: Базовый поиск свободного окна
# ============================================================================

class TestFindAvailableSlotBasic:
    """Базовые тесты для поиска свободного окна."""
    
    @pytest.mark.asyncio
    async def test_finds_slot_for_two_participants(self):
        """
        Тест: Находит первое свободное окно для двух участников.
        
        Участник A занят: 10:00-11:00
        Участник B занят: 11:00-12:00
        Ожидаем: первое общее свободное окно с 9:00 (до занятости A)
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["alice@example.com", "bob@example.com"]
        
        mock_calendars = {
            "alice@example.com": [
                {"start": "2026-01-09T10:00:00", "end": "2026-01-09T11:00:00"}
            ],
            "bob@example.com": [
                {"start": "2026-01-09T11:00:00", "end": "2026-01-09T12:00:00"}
            ]
        }
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                buffer_minutes=10,
                search_start=datetime(2026, 1, 9, 9, 0),
                search_end=datetime(2026, 1, 9, 18, 0)
            )
        
        assert result is not None, "Должен найти свободное окно"
        assert result["start"] == datetime(2026, 1, 9, 9, 0)
        assert result["end"] == datetime(2026, 1, 9, 9, 50)
    
    @pytest.mark.asyncio
    async def test_finds_earliest_slot_for_three_participants(self):
        """
        Тест: Для 3 участников находит самое раннее общее окно.
        
        A занят: 9:00-10:00
        B занят: 9:30-10:30
        C занят: 10:00-10:30
        
        Все свободны с 10:30 (+ буфер 10 мин = с 10:40)
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["a@test.com", "b@test.com", "c@test.com"]
        
        mock_calendars = {
            "a@test.com": [{"start": "2026-01-09T09:00:00", "end": "2026-01-09T10:00:00"}],
            "b@test.com": [{"start": "2026-01-09T09:30:00", "end": "2026-01-09T10:30:00"}],
            "c@test.com": [{"start": "2026-01-09T10:00:00", "end": "2026-01-09T10:30:00"}]
        }
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                buffer_minutes=10,
                search_start=datetime(2026, 1, 9, 9, 0),
                search_end=datetime(2026, 1, 9, 18, 0)
            )
        
        # Последняя встреча заканчивается в 10:30 + буфер 10 мин = 10:40
        assert result is not None
        assert result["start"] == datetime(2026, 1, 9, 10, 40)
        assert result["end"] == datetime(2026, 1, 9, 11, 30)  # 50 мин встреча


# ============================================================================
# ТЕСТЫ: Нет свободного времени
# ============================================================================

class TestNoAvailableSlot:
    """Тесты для случаев, когда нет свободного времени."""
    
    @pytest.mark.asyncio
    async def test_returns_none_when_no_slot_available(self):
        """
        Тест: Возвращает None, если нет общего свободного времени.
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["a@test.com", "b@test.com"]
        
        # Оба заняты весь день
        mock_calendars = {
            "a@test.com": [{"start": "2026-01-09T09:00:00", "end": "2026-01-09T18:00:00"}],
            "b@test.com": [{"start": "2026-01-09T09:00:00", "end": "2026-01-09T18:00:00"}]
        }
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                buffer_minutes=10,
                search_start=datetime(2026, 1, 9, 9, 0),
                search_end=datetime(2026, 1, 9, 18, 0)
            )
        
        assert result is None, "Должен вернуть None, когда нет свободного времени"
    
    @pytest.mark.asyncio
    async def test_returns_none_when_slot_too_short(self):
        """
        Тест: Возвращает None, если свободный слот слишком короткий.
        
        Свободно только 30 минут, а нужно 50 + 10 буфер = 60 минут.
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["a@test.com"]
        
        mock_calendars = {
            "a@test.com": [
                {"start": "2026-01-09T09:00:00", "end": "2026-01-09T09:30:00"},
                {"start": "2026-01-09T10:00:00", "end": "2026-01-09T18:00:00"}
            ]
        }
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                buffer_minutes=10,
                search_start=datetime(2026, 1, 9, 9, 0),
                search_end=datetime(2026, 1, 9, 18, 0)
            )
        
        # Между 9:30 и 10:00 только 30 минут — недостаточно для 50+10
        assert result is None


# ============================================================================
# ТЕСТЫ: Рабочие часы
# ============================================================================

class TestWorkingHours:
    """Тесты для учёта рабочих часов."""
    
    @pytest.mark.asyncio
    async def test_respects_working_hours_start(self):
        """
        Тест: Не предлагает время раньше начала рабочего дня.
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["a@test.com"]
        mock_calendars = {"a@test.com": []}
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                buffer_minutes=10,
                search_start=datetime(2026, 1, 9, 7, 0),  # Ищем с 7:00
                search_end=datetime(2026, 1, 9, 18, 0),
                working_hours=(9, 18)  # Рабочий день с 9:00
            )
        
        # Должен предложить с 9:00, не раньше
        assert result is not None
        assert result["start"].hour >= 9
    
    @pytest.mark.asyncio
    async def test_respects_working_hours_end(self):
        """
        Тест: Не предлагает время, которое выходит за конец рабочего дня.
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["a@test.com"]
        
        # Занят с 9:00 до 17:30, рабочий день до 18:00
        # Остаётся только 30 минут — недостаточно для 50-мин встречи
        mock_calendars = {
            "a@test.com": [{"start": "2026-01-09T09:00:00", "end": "2026-01-09T17:30:00"}]
        }
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                buffer_minutes=10,
                search_start=datetime(2026, 1, 9, 9, 0),
                search_end=datetime(2026, 1, 9, 18, 0),
                working_hours=(9, 18)
            )
        
        assert result is None, "Не должен предлагать время за пределами рабочих часов"
    
    @pytest.mark.asyncio
    async def test_custom_working_hours(self):
        """
        Тест: Поддерживает кастомные рабочие часы (например, 10:00-19:00).
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["a@test.com"]
        mock_calendars = {"a@test.com": []}
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                buffer_minutes=10,
                search_start=datetime(2026, 1, 9, 8, 0),  # Ищем с 8:00
                search_end=datetime(2026, 1, 9, 20, 0),
                working_hours=(10, 19)  # Рабочий день 10:00-19:00
            )
        
        assert result is not None
        assert result["start"].hour >= 10
        assert result["end"].hour <= 19


# ============================================================================
# ТЕСТЫ: Буферное время
# ============================================================================

class TestBufferTime:
    """Тесты для буферного времени между встречами."""
    
    @pytest.mark.asyncio
    async def test_default_buffer_is_10_minutes(self):
        """
        Тест: По умолчанию буфер = 10 минут.
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["alice@example.com"]
        
        mock_calendars = {
            "alice@example.com": [
                {"start": "2026-01-09T09:00:00", "end": "2026-01-09T10:00:00"}
            ]
        }
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            # Не передаём buffer_minutes — должен использовать 10 по умолчанию
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                search_start=datetime(2026, 1, 9, 9, 0),
                search_end=datetime(2026, 1, 9, 18, 0)
            )
        
        # 10:00 (конец встречи) + 10 мин буфер по умолчанию = 10:10
        assert result is not None
        assert result["start"] == datetime(2026, 1, 9, 10, 10)
    
    @pytest.mark.asyncio
    async def test_adds_buffer_after_existing_meeting(self):
        """
        Тест: Добавляет буфер после существующей встречи.
        
        Предыдущая встреча: 10:00-10:50
        Буфер: 10 минут
        Ожидаем: новая встреча начнётся с 11:00
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["alice@example.com"]
        
        mock_calendars = {
            "alice@example.com": [
                {"start": "2026-01-09T10:00:00", "end": "2026-01-09T10:50:00"}
            ]
        }
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                buffer_minutes=10,
                search_start=datetime(2026, 1, 9, 10, 30),  # Ищем с 10:30
                search_end=datetime(2026, 1, 9, 18, 0)
            )
        
        # 10:50 + 10 мин буфер = 11:00
        assert result is not None
        assert result["start"] == datetime(2026, 1, 9, 11, 0)
        assert result["end"] == datetime(2026, 1, 9, 11, 50)
    
    @pytest.mark.asyncio
    async def test_buffer_before_next_meeting(self):
        """
        Тест: Учитывает буфер перед следующей встречей.
        
        Следующая встреча: 12:00
        Нужно: 50 мин встреча + 10 мин буфер = 60 мин
        Максимальное время начала: 12:00 - 60 мин = 11:00
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["alice@example.com"]
        
        mock_calendars = {
            "alice@example.com": [
                {"start": "2026-01-09T12:00:00", "end": "2026-01-09T13:00:00"}
            ]
        }
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                buffer_minutes=10,
                search_start=datetime(2026, 1, 9, 9, 0),
                search_end=datetime(2026, 1, 9, 18, 0)
            )
        
        # Должен найти слот 9:00-9:50 (с буфером до 10:00, до 12:00 ещё много времени)
        assert result is not None
        assert result["start"] == datetime(2026, 1, 9, 9, 0)
        assert result["end"] == datetime(2026, 1, 9, 9, 50)
    
    @pytest.mark.asyncio
    async def test_no_slot_when_buffer_doesnt_fit(self):
        """
        Тест: Не ставит встречу, если нет места для буфера.
        
        Встреча A: 9:00-10:00
        Встреча B: 10:30-11:30
        Свободно: 10:00-10:30 (30 мин)
        
        Запрос: 50-мин встреча + 10-мин буфер = нужно 60 мин
        Ожидаем: НЕ ставит в 10:00-10:30
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["alice@example.com"]
        
        mock_calendars = {
            "alice@example.com": [
                {"start": "2026-01-09T09:00:00", "end": "2026-01-09T10:00:00"},
                {"start": "2026-01-09T10:30:00", "end": "2026-01-09T11:30:00"}
            ]
        }
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                buffer_minutes=10,
                search_start=datetime(2026, 1, 9, 9, 0),
                search_end=datetime(2026, 1, 9, 18, 0)
            )
        
        # НЕ должен поставить в 10:00-10:50 (конец + буфер = 11:00, но в 10:30 встреча)
        # Должен поставить после 11:30 + 10 мин буфер = 11:40
        assert result is not None
        assert result["start"] == datetime(2026, 1, 9, 11, 40)
    
    @pytest.mark.asyncio
    async def test_zero_buffer_works(self):
        """
        Тест: Можно отключить буфер (buffer_minutes=0).
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["alice@example.com"]
        
        mock_calendars = {
            "alice@example.com": [
                {"start": "2026-01-09T09:00:00", "end": "2026-01-09T10:00:00"}
            ]
        }
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                buffer_minutes=0,  # Без буфера
                search_start=datetime(2026, 1, 9, 9, 0),
                search_end=datetime(2026, 1, 9, 18, 0)
            )
        
        # Без буфера может поставить сразу после 10:00
        assert result is not None
        assert result["start"] == datetime(2026, 1, 9, 10, 0)
    
    @pytest.mark.asyncio
    async def test_custom_buffer_5_minutes(self):
        """
        Тест: Работает с буфером 5 минут.
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["alice@example.com"]
        
        mock_calendars = {
            "alice@example.com": [
                {"start": "2026-01-09T09:00:00", "end": "2026-01-09T10:00:00"}
            ]
        }
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                buffer_minutes=5,
                search_start=datetime(2026, 1, 9, 9, 0),
                search_end=datetime(2026, 1, 9, 18, 0)
            )
        
        # 10:00 + 5 мин буфер = 10:05
        assert result is not None
        assert result["start"] == datetime(2026, 1, 9, 10, 5)
    
    @pytest.mark.asyncio
    async def test_custom_buffer_15_minutes(self):
        """
        Тест: Работает с буфером 15 минут.
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        participants = ["alice@example.com"]
        
        mock_calendars = {
            "alice@example.com": [
                {"start": "2026-01-09T09:00:00", "end": "2026-01-09T10:00:00"}
            ]
        }
        
        scheduler = MeetingScheduler()
        with patch.object(scheduler, '_get_calendar_events', return_value=mock_calendars):
            result = await scheduler.find_available_slot(
                participants=participants,
                duration_minutes=50,
                buffer_minutes=15,
                search_start=datetime(2026, 1, 9, 9, 0),
                search_end=datetime(2026, 1, 9, 18, 0)
            )
        
        # 10:00 + 15 мин буфер = 10:15
        assert result is not None
        assert result["start"] == datetime(2026, 1, 9, 10, 15)


# ============================================================================
# ТЕСТЫ: Интеграция (пропускаются без реальных credentials)
# ============================================================================

class TestMeetingSchedulerIntegration:
    """Интеграционные тесты с реальным MCP Calendar."""
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Требует настроенные MCP credentials")
    async def test_fetches_real_calendars(self):
        """
        Тест: Получает реальные данные календарей через MCP.
        """
        from src.core.meeting_scheduler import MeetingScheduler
        
        scheduler = MeetingScheduler()
        # Реальный запрос к календарям
        result = await scheduler.find_available_slot(
            participants=["user1@gmail.com", "user2@gmail.com"],
            duration_minutes=50,
            buffer_minutes=10,
            search_start=datetime.now(),
            search_end=datetime.now() + timedelta(days=7)
        )
        
        # Просто проверяем, что не упало
        assert result is None or isinstance(result, dict)


# ============================================================================
# Запуск тестов напрямую
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
