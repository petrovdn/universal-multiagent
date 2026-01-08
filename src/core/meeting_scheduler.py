# src/core/meeting_scheduler.py
"""
Планировщик встреч для нескольких участников.

Находит первое свободное окно, когда все участники доступны,
с учётом буферного времени между встречами.

Пример использования:
    scheduler = MeetingScheduler(use_mcp=True)
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
import json
import pytz

logger = logging.getLogger(__name__)


def get_local_timezone():
    """Получает локальную таймзону из конфига."""
    try:
        from src.utils.config_loader import get_config
        return pytz.timezone(get_config().timezone)
    except:
        return pytz.timezone("Europe/Moscow")


def get_mcp_manager():
    """Ленивый импорт MCP manager для избежания циклических зависимостей."""
    from src.utils.mcp_loader import get_mcp_manager as _get_mcp_manager
    return _get_mcp_manager()


class MeetingScheduler:
    """
    Планировщик встреч для нескольких участников.
    
    Находит первое свободное окно, когда ВСЕ участники доступны,
    с учётом буферного времени между встречами.
    """
    
    def __init__(self, calendar_tools=None, use_mcp: bool = False):
        """
        Инициализация планировщика.
        
        Args:
            calendar_tools: MCP Calendar tools для получения событий календаря.
                           Если None, используется mock для тестов.
            use_mcp: Использовать MCP для получения календарных данных.
        """
        self.calendar_tools = calendar_tools
        self.use_mcp = use_mcp
    
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
        
        # Нормализуем datetime к naive для консистентности
        if search_start.tzinfo is not None:
            search_start = search_start.replace(tzinfo=None)
        if search_end.tzinfo is not None:
            search_end = search_end.replace(tzinfo=None)
        
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
        calendars = {}
        
        if self.use_mcp:
            # Используем FreeBusy API для проверки занятости ВСЕХ участников
            try:
                mcp_manager = get_mcp_manager()
                
                # FreeBusy запрос для всех участников
                freebusy_args = {
                    "timeMin": start.isoformat() + "Z" if "+" not in start.isoformat() else start.isoformat(),
                    "timeMax": end.isoformat() + "Z" if "+" not in end.isoformat() else end.isoformat(),
                    "items": [{"id": email} for email in participants]
                }
                
                logger.info(f"[MeetingScheduler] Querying FreeBusy for {len(participants)} participants")
                result = await mcp_manager.call_tool("freebusy_query", freebusy_args, server_name="calendar")
                
                # Парсим результат FreeBusy
                calendars = self._parse_freebusy_result(result, participants)
                
                logger.info(f"[MeetingScheduler] FreeBusy returned busy slots for {len(calendars)} calendars")
                    
            except ValueError as e:
                # ValueError означает недоступность календарей - НЕ используем fallback!
                logger.error(f"[MeetingScheduler] Calendar access denied: {e}")
                raise  # Пробрасываем ошибку наверх
                
            except Exception as e:
                # Другие ошибки (сеть, etc.) - пробуем fallback
                logger.warning(f"[MeetingScheduler] FreeBusy failed: {e}, falling back to list_events")
                # Fallback: запрашиваем свой календарь (старое поведение)
                try:
                    args = {
                        "timeMin": start.isoformat(),
                        "timeMax": end.isoformat(),
                        "maxResults": 100
                    }
                    result = await mcp_manager.call_tool("list_events", args, server_name="calendar")
                    events = self._parse_mcp_result(result)
                    # В fallback режиме присваиваем всем один календарь (текущего пользователя)
                    for email in participants:
                        calendars[email] = events
                except Exception as e2:
                    logger.error(f"[MeetingScheduler] Fallback also failed: {e2}")
                    for email in participants:
                        calendars[email] = []
                    
        elif self.calendar_tools:
            # Legacy: через переданные calendar_tools
            for email in participants:
                try:
                    calendars[email] = []
                except Exception as e:
                    logger.error(f"[MeetingScheduler] Error getting calendar for {email}: {e}")
                    calendars[email] = []
        
        # Без calendar_tools и use_mcp возвращаем пустой словарь (для тестов с моками)
        if not calendars:
            calendars = {email: [] for email in participants}
            
        return calendars
    
    def _parse_freebusy_result(
        self, 
        result, 
        participants: List[str]
    ) -> Dict[str, List[Dict]]:
        """
        Парсит результат FreeBusy API в словарь календарей.
        
        Args:
            result: Результат от MCP freebusy_query
            participants: Список email участников
        
        Returns:
            Словарь {email: [{"start": ..., "end": ...}, ...]}
            
        Raises:
            ValueError: Если календарь участника недоступен (notFound, etc.)
        """
        calendars = {email: [] for email in participants}
        unavailable_calendars = []
        
        try:
            # Handle MCP result format
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result_text = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result_text = first_item['text']
                else:
                    result_text = str(first_item)
                
                parsed = json.loads(result_text)
            elif isinstance(result, str):
                parsed = json.loads(result)
            elif isinstance(result, dict):
                parsed = result
            else:
                logger.warning(f"[MeetingScheduler] Unknown FreeBusy result type: {type(result)}")
                return calendars
            
            # Extract calendars data from FreeBusy response
            freebusy_calendars = parsed.get("calendars", {})
            
            for email in participants:
                calendar_data = freebusy_calendars.get(email, {})
                busy_slots = calendar_data.get("busy", [])
                
                # Check for errors FIRST - calendar might be unavailable
                errors = calendar_data.get("errors", [])
                if errors:
                    for error in errors:
                        if error.get("reason") in ("notFound", "notAuthorized", "forbidden"):
                            unavailable_calendars.append(email)
                            logger.warning(f"[MeetingScheduler] Calendar unavailable for {email}: {error}")
                            break
                    else:
                        # Other errors - just log warning
                        logger.warning(f"[MeetingScheduler] FreeBusy errors for {email}: {errors}")
                
                # Convert FreeBusy format to our format
                events = []
                for slot in busy_slots:
                    events.append({
                        "start": slot.get("start"),
                        "end": slot.get("end")
                    })
                
                calendars[email] = events
            
            # If any calendars are unavailable, raise an error
            if unavailable_calendars:
                raise ValueError(
                    f"Не удалось проверить календари участников: {', '.join(unavailable_calendars)}. "
                    f"Участники должны открыть доступ к своему календарю или находиться в том же домене Google Workspace."
                )
            
            return calendars
            
        except ValueError:
            # Re-raise ValueError (calendar unavailable)
            raise
        except Exception as e:
            logger.error(f"[MeetingScheduler] Error parsing FreeBusy result: {e}")
            return calendars
    
    def _parse_mcp_result(self, result) -> List[Dict]:
        """
        Парсит результат MCP call_tool в список событий.
        
        Args:
            result: Результат от MCP (может быть list, dict, str)
        
        Returns:
            Список событий [{"start": ..., "end": ...}, ...]
        """
        events = []
        
        try:
            # Handle MCP result format (TextContent list or dict)
            if isinstance(result, list) and len(result) > 0:
                first_item = result[0]
                if hasattr(first_item, 'text'):
                    result_text = first_item.text
                elif isinstance(first_item, dict) and 'text' in first_item:
                    result_text = first_item['text']
                else:
                    result_text = str(first_item)
                
                # Parse JSON string
                try:
                    parsed = json.loads(result_text)
                    events = parsed.get("items", [])
                except json.JSONDecodeError:
                    pass
                    
            elif isinstance(result, str):
                try:
                    parsed = json.loads(result)
                    events = parsed.get("items", [])
                except json.JSONDecodeError:
                    pass
                    
            elif isinstance(result, dict):
                events = result.get("items", [])
            
            # Преобразуем в нужный формат
            formatted_events = []
            for event in events:
                if isinstance(event, dict):
                    start_data = event.get("start", {})
                    end_data = event.get("end", {})
                    
                    start_time = start_data.get("dateTime") or start_data.get("date")
                    end_time = end_data.get("dateTime") or end_data.get("date")
                    
                    if start_time and end_time:
                        formatted_events.append({
                            "start": start_time,
                            "end": end_time,
                            "summary": event.get("summary", "")
                        })
            
            return formatted_events
            
        except Exception as e:
            logger.error(f"[MeetingScheduler] Error parsing MCP result: {e}")
            return []
    
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
        Парсит строку datetime в объект datetime (naive, LOCAL timezone).
        
        Поддерживает форматы:
        - 2026-01-09T10:00:00
        - 2026-01-09T10:00:00Z
        - 2026-01-09T10:00:00+00:00
        - 2026-01-09T10:00:00+03:00
        
        ВАЖНО: Конвертирует UTC в локальную таймзону перед удалением tzinfo!
        Это гарантирует корректное сравнение с локальным временем.
        """
        local_tz = get_local_timezone()
        
        # Убираем Z и заменяем на +00:00
        dt_str = dt_str.replace("Z", "+00:00")
        
        # Парсим как aware если есть timezone
        try:
            dt = datetime.fromisoformat(dt_str)
            
            # Если есть timezone — конвертируем в локальную, затем убираем tzinfo
            if dt.tzinfo is not None:
                # Конвертируем в локальную таймзону
                dt_local = dt.astimezone(local_tz)
                # Убираем tzinfo для naive сравнений
                dt = dt_local.replace(tzinfo=None)
            
            return dt
        except ValueError:
            # Если не удалось — пробуем без timezone
            dt_str_naive = dt_str.split("+")[0]
            if "T" in dt_str_naive:
                return datetime.fromisoformat(dt_str_naive)
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
