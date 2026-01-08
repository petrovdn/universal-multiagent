# src/core/meeting_scheduler.py
"""
Планировщик встреч для нескольких участников.

Находит первое свободное окно, когда все участники доступны,
с учётом буферного времени между встречами.

Пример использования:
    scheduler = MeetingScheduler(calendar_tools=get_calendar_tools())
    slot = await scheduler.find_available_slot(
        participants=["alice@example.com", "bob@example.com"],
        duration_minutes=50,
        buffer_minutes=10,  # 10 мин буфер по умолчанию
        search_start=datetime.now(),
        search_end=datetime.now() + timedelta(days=7)
    )
    # slot = {"start": datetime, "end": datetime} или None
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MeetingScheduler:
    """
    Планировщик встреч для нескольких участников.
    
    Находит первое свободное окно, когда ВСЕ участники доступны,
    с учётом буферного времени между встречами.
    """
    
    def __init__(self, calendar_tools=None):
        """
        Инициализация планировщика.
        
        Args:
            calendar_tools: MCP Calendar tools для получения событий календаря.
                           Если None, используется mock для тестов.
        """
        self.calendar_tools = calendar_tools
    
    async def find_available_slot(
        self,
        participants: List[str],
        duration_minutes: int,
        search_start: datetime,
        search_end: datetime,
        buffer_minutes: int = 10,
        working_hours: tuple = (9, 18)
    ) -> Optional[Dict[str, datetime]]:
        """
        Находит первое свободное окно для всех участников.
        
        Args:
            participants: Список email участников
            duration_minutes: Длительность встречи в минутах (например, 50)
            search_start: Начало периода поиска
            search_end: Конец периода поиска
            buffer_minutes: Буфер после встречи в минутах (по умолчанию 10)
            working_hours: Кортеж (start_hour, end_hour) рабочего дня
        
        Returns:
            {"start": datetime, "end": datetime} или None если слот не найден
        
        Note:
            При поиске учитывается полный блок: duration + buffer.
            Например, 50-мин встреча + 10-мин буфер = нужно 60 мин свободного времени.
        """
        logger.info(
            f"[MeetingScheduler] Searching slot for {len(participants)} participants, "
            f"duration={duration_minutes}min, buffer={buffer_minutes}min"
        )
        
        # 1. Получаем события всех участников
        calendars = await self._get_calendar_events(participants, search_start, search_end)
        
        # 2. Объединяем все занятые слоты (с учётом буфера после каждого)
        all_busy_slots = self._merge_busy_slots(calendars, buffer_minutes)
        
        # 3. Ищем первое свободное окно нужной длительности
        slot = self._find_first_free_slot(
            busy_slots=all_busy_slots,
            duration=timedelta(minutes=duration_minutes),
            buffer=timedelta(minutes=buffer_minutes),
            search_start=search_start,
            search_end=search_end,
            working_hours=working_hours
        )
        
        if slot:
            logger.info(f"[MeetingScheduler] Found slot: {slot['start']} - {slot['end']}")
        else:
            logger.info("[MeetingScheduler] No available slot found")
        
        return slot
    
    async def _get_calendar_events(
        self,
        participants: List[str],
        start: datetime,
        end: datetime
    ) -> Dict[str, List[Dict]]:
        """
        Получает события календарей участников.
        
        В реальном использовании вызывает MCP Calendar tools.
        В тестах этот метод мокается.
        
        Args:
            participants: Список email участников
            start: Начало периода
            end: Конец периода
        
        Returns:
            Словарь {email: [events]}
        """
        if self.calendar_tools:
            # Реальная интеграция с MCP Calendar
            # TODO: Реализовать через MCP tools
            calendars = {}
            for email in participants:
                try:
                    # events = await self.calendar_tools.list_events(
                    #     email=email,
                    #     time_min=start.isoformat(),
                    #     time_max=end.isoformat()
                    # )
                    # calendars[email] = events
                    calendars[email] = []
                except Exception as e:
                    logger.error(f"[MeetingScheduler] Error getting calendar for {email}: {e}")
                    calendars[email] = []
            return calendars
        
        # Без calendar_tools возвращаем пустой словарь (для тестов с моками)
        return {}
    
    def _merge_busy_slots(
        self,
        calendars: Dict[str, List[Dict]],
        buffer_minutes: int
    ) -> List[tuple]:
        """
        Объединяет и сортирует все занятые слоты от всех участников.
        
        Добавляет буфер после каждой встречи.
        
        Args:
            calendars: Словарь {email: [events]}
            buffer_minutes: Буфер после каждой встречи
        
        Returns:
            Список отсортированных и объединённых (start, end) кортежей
        """
        all_slots = []
        buffer = timedelta(minutes=buffer_minutes)
        
        for email, events in calendars.items():
            for event in events:
                # Парсим время начала и конца
                start = self._parse_datetime(event["start"])
                end = self._parse_datetime(event["end"])
                
                # Добавляем буфер после встречи
                end_with_buffer = end + buffer
                
                all_slots.append((start, end_with_buffer))
        
        if not all_slots:
            return []
        
        # Сортируем по времени начала
        all_slots.sort(key=lambda x: x[0])
        
        # Объединяем пересекающиеся/касающиеся слоты
        merged = []
        for start, end in all_slots:
            if merged and start <= merged[-1][1]:
                # Расширяем последний слот
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        
        return merged
    
    def _parse_datetime(self, dt_str: str) -> datetime:
        """
        Парсит строку datetime в объект datetime.
        
        Поддерживает форматы:
        - 2026-01-09T10:00:00
        - 2026-01-09T10:00:00Z
        - 2026-01-09T10:00:00+00:00
        """
        # Убираем Z и timezone для простоты
        dt_str = dt_str.replace("Z", "").split("+")[0]
        return datetime.fromisoformat(dt_str)
    
    def _find_first_free_slot(
        self,
        busy_slots: List[tuple],
        duration: timedelta,
        buffer: timedelta,
        search_start: datetime,
        search_end: datetime,
        working_hours: tuple
    ) -> Optional[Dict[str, datetime]]:
        """
        Находит первый свободный слот нужной длительности.
        
        Алгоритм:
        1. Начинаем с search_start (или начала рабочего дня)
        2. Для каждого занятого слота проверяем, есть ли место ДО него
        3. Если есть место для duration + buffer до следующей встречи — возвращаем
        4. Иначе двигаемся к концу занятого слота
        
        Args:
            busy_slots: Отсортированные занятые слоты (уже с буфером после)
            duration: Длительность встречи
            buffer: Буфер после встречи
            search_start: Начало поиска
            search_end: Конец поиска
            working_hours: (start_hour, end_hour)
        
        Returns:
            {"start": datetime, "end": datetime} или None
        """
        work_start_hour, work_end_hour = working_hours
        
        # Начинаем с search_start
        current = search_start
        
        # Корректируем на начало рабочего дня если нужно
        if current.hour < work_start_hour:
            current = current.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
        
        # Общее время которое нужно (встреча + буфер)
        total_needed = duration + buffer
        
        for busy_start, busy_end in busy_slots:
            # Проверяем, есть ли место до этого занятого слота
            potential_end = current + duration
            potential_end_with_buffer = current + total_needed
            
            # Проверяем что:
            # 1. Встреча + буфер помещается до начала занятого слота
            # 2. Конец встречи в пределах рабочих часов
            if (potential_end_with_buffer <= busy_start and
                potential_end.hour < work_end_hour or 
                (potential_end.hour == work_end_hour and potential_end.minute == 0)):
                
                # Дополнительная проверка: встреча не выходит за рабочие часы
                if self._slot_within_working_hours(current, potential_end, working_hours):
                    return {"start": current, "end": potential_end}
            
            # Двигаемся к концу занятого слота (уже включает буфер)
            if busy_end > current:
                current = busy_end
        
        # Проверяем время после последнего занятого слота
        potential_end = current + duration
        
        # Проверяем что встреча помещается до конца поиска и в рабочие часы
        if potential_end <= search_end:
            if self._slot_within_working_hours(current, potential_end, working_hours):
                return {"start": current, "end": potential_end}
        
        return None
    
    def _slot_within_working_hours(
        self,
        start: datetime,
        end: datetime,
        working_hours: tuple
    ) -> bool:
        """
        Проверяет, что слот полностью в пределах рабочих часов.
        
        Args:
            start: Начало слота
            end: Конец слота
            working_hours: (start_hour, end_hour)
        
        Returns:
            True если слот в рабочих часах
        """
        work_start_hour, work_end_hour = working_hours
        
        # Начало должно быть >= начала рабочего дня
        if start.hour < work_start_hour:
            return False
        
        # Конец должен быть <= конца рабочего дня
        if end.hour > work_end_hour:
            return False
        if end.hour == work_end_hour and end.minute > 0:
            return False
        
        return True


# Фабричная функция для создания планировщика с MCP tools
def get_meeting_scheduler(calendar_tools=None) -> MeetingScheduler:
    """
    Создаёт экземпляр MeetingScheduler.
    
    Args:
        calendar_tools: MCP Calendar tools (опционально)
    
    Returns:
        Экземпляр MeetingScheduler
    """
    return MeetingScheduler(calendar_tools=calendar_tools)
