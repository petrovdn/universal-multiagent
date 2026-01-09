"""
SmartProgressGenerator - генерирует контекстные progress-сообщения на основе анализа задачи.

Цель: показывать пользователю конкретную информацию о текущей работе не реже одного раза в 5 секунд,
адаптированную к типу задачи (календарь, email, файлы и т.д.).
"""
import asyncio
import re
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

from src.api.websocket_manager import WebSocketManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class TaskPattern:
    """Паттерн задачи с соответствующими сообщениями."""
    keywords: List[str]
    messages: List[str]
    category: str


class SmartProgressGenerator:
    """Генерирует контекстные progress-сообщения на основе анализа задачи."""
    
    # Паттерны задач с соответствующими сообщениями
    TASK_PATTERNS: List[TaskPattern] = [
        TaskPattern(
            keywords=["назначь", "создай встречу", "запланируй", "встреча", "встречу"],
            messages=[
                "Анализирую параметры встречи...",
                "Проверяю доступность участников...",
                "Выбираю оптимальное время...",
                "Формирую приглашение...",
                "Создаю событие в календаре..."
            ],
            category="calendar_create"
        ),
        TaskPattern(
            keywords=["покажи встречи", "список встреч", "события", "календар"],
            messages=[
                "Проверяю календарь...",
                "Ищу события...",
                "Фильтрую по параметрам...",
                "Формирую список встреч..."
            ],
            category="calendar_read"
        ),
        TaskPattern(
            keywords=["отправь письмо", "напиши письмо", "email", "письм"],
            messages=[
                "Анализирую контекст письма...",
                "Формулирую текст сообщения...",
                "Подготавливаю отправку...",
                "Отправляю письмо..."
            ],
            category="email_send"
        ),
        TaskPattern(
            keywords=["найди письм", "покажи письм", "список писем"],
            messages=[
                "Ищу письма...",
                "Фильтрую по параметрам...",
                "Формирую список писем..."
            ],
            category="email_read"
        ),
        TaskPattern(
            keywords=["таблиц", "spreadsheet", "sheets", "ячейк"],
            messages=[
                "Анализирую таблицу...",
                "Читаю данные...",
                "Обрабатываю информацию..."
            ],
            category="sheets"
        ),
        TaskPattern(
            keywords=["документ", "document", "файл"],
            messages=[
                "Анализирую документ...",
                "Читаю содержимое...",
                "Обрабатываю информацию..."
            ],
            category="files"
        ),
        TaskPattern(
            keywords=["1с", "1c", "учёт", "баланс"],
            messages=[
                "Подключаюсь к 1С...",
                "Запрашиваю данные...",
                "Обрабатываю результаты..."
            ],
            category="accounting"
        ),
    ]
    
    # Дефолтные сообщения для неизвестных задач
    DEFAULT_MESSAGES = [
        "Анализирую задачу...",
        "Обрабатываю запрос...",
        "Выполняю действие...",
        "Завершаю обработку..."
    ]
    
    # Интервал между сообщениями (секунды)
    MESSAGE_INTERVAL = 4.0  # 4 секунды для гарантии "не реже одного раза в 5 секунд"
    
    # Интервал обновления таймера (секунды)
    TIMER_INTERVAL = 1.0
    
    def __init__(
        self,
        ws_manager: WebSocketManager,
        session_id: str
    ):
        """
        Args:
            ws_manager: WebSocket менеджер для отправки событий
            session_id: ID сессии
        """
        self.ws_manager = ws_manager
        self.session_id = session_id
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._timer_task: Optional[asyncio.Task] = None
        self._start_time: Optional[float] = None
        self._estimated_duration: Optional[int] = None
        self._current_messages: List[str] = []
        self._message_index = 0
    
    async def start(self, goal: str, estimated_duration_sec: int) -> None:
        """
        Запускает генерацию progress-сообщений.
        
        Args:
            goal: Цель задачи
            estimated_duration_sec: Оценочное время выполнения в секундах
        """
        if self._running:
            logger.warning("[SmartProgressGenerator] Already running, stopping first")
            self.stop()
        
        self._running = True
        self._start_time = time.time()
        self._estimated_duration = estimated_duration_sec
        self._message_index = 0
        
        # Определяем сообщения на основе цели
        self._current_messages = self._get_messages_for_goal(goal)
        
        # Отправляем start событие
        await self.ws_manager.send_event(
            self.session_id,
            "smart_progress_start",
            {
                "estimated_duration_sec": estimated_duration_sec,
                "goal": goal[:100]  # Первые 100 символов
            }
        )
        
        # Запускаем задачи
        self._task = asyncio.create_task(self._message_loop())
        self._timer_task = asyncio.create_task(self._timer_loop())
    
    def stop(self) -> None:
        """Останавливает генерацию progress-сообщений."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            self._task = None
        
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None
    
    def _get_messages_for_goal(self, goal: str) -> List[str]:
        """
        Определяет список сообщений на основе цели.
        
        Args:
            goal: Цель задачи
            
        Returns:
            Список сообщений для показа
        """
        goal_lower = goal.lower()
        
        # Ищем подходящий паттерн
        for pattern in self.TASK_PATTERNS:
            if any(keyword in goal_lower for keyword in pattern.keywords):
                return pattern.messages
        
        # Если паттерн не найден, используем дефолтные
        return self.DEFAULT_MESSAGES
    
    async def _message_loop(self) -> None:
        """Основной цикл отправки сообщений."""
        try:
            while self._running:
                if self._message_index < len(self._current_messages):
                    message = self._current_messages[self._message_index]
                    
                    await self.ws_manager.send_event(
                        self.session_id,
                        "smart_progress_message",
                        {
                            "message": message,
                            "index": self._message_index,
                            "total": len(self._current_messages)
                        }
                    )
                    
                    self._message_index += 1
                
                # Ждём интервал
                await asyncio.sleep(self.MESSAGE_INTERVAL)
                
                # Если все сообщения показаны, начинаем заново
                if self._message_index >= len(self._current_messages):
                    self._message_index = 0
                    
        except asyncio.CancelledError:
            logger.debug("[SmartProgressGenerator] Message loop cancelled")
        except Exception as e:
            logger.error(f"[SmartProgressGenerator] Error in message loop: {e}")
    
    async def _timer_loop(self) -> None:
        """Цикл обновления таймера."""
        try:
            while self._running:
                if self._start_time and self._estimated_duration:
                    elapsed = time.time() - self._start_time
                    
                    await self.ws_manager.send_event(
                        self.session_id,
                        "smart_progress_timer",
                        {
                            "elapsed_sec": int(elapsed),
                            "estimated_sec": self._estimated_duration,
                            "progress_percent": min(100, int((elapsed / self._estimated_duration) * 100))
                        }
                    )
                
                await asyncio.sleep(self.TIMER_INTERVAL)
                
        except asyncio.CancelledError:
            logger.debug("[SmartProgressGenerator] Timer loop cancelled")
        except Exception as e:
            logger.error(f"[SmartProgressGenerator] Error in timer loop: {e}")
