"""
TDD тесты для streaming thinking → intent_detail.

КРИТЕРИИ:
1. StreamingThoughtParser должен отправлять intent_detail при получении thinking chunk
2. SmartProgress и IntentBlocks должны показываться вместе (не либо/или)
3. Thinking chunks должны появляться как intent_detail с типом "analyze"
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


class TestStreamingThoughtParserSendsIntentDetail:
    """
    КРИТЕРИЙ 1: StreamingThoughtParser должен отправлять intent_detail 
    при получении thinking chunk.
    """
    
    @pytest.mark.asyncio
    async def test_parser_sends_intent_detail_for_thought_chunks(self):
        """
        Тест: При стриминге thought, парсер должен отправлять intent_detail
        с типом 'analyze' для каждого chunk.
        """
        # Arrange
        mock_ws = AsyncMock()
        mock_ws.send_event = AsyncMock()
        
        from src.core.unified_react_engine import UnifiedReActEngine
        
        # Создаём парсер с intent_id
        parser = UnifiedReActEngine.StreamingThoughtParser(
            ws_manager=mock_ws, 
            session_id="test-session",
            intent_id="intent-123"  # NEW: intent_id parameter должен быть добавлен
        )
        
        # Act: Симулируем стриминг thought
        await parser.process_chunk("<thought>Анализирую ")
        await parser.process_chunk("параметры встречи...")
        await parser.process_chunk("</thought>")
        
        # Assert: Должны быть вызовы intent_detail
        intent_detail_calls = [
            call for call in mock_ws.send_event.call_args_list
            if call[0][1] == "intent_detail"
        ]
        
        assert len(intent_detail_calls) > 0, \
            "StreamingThoughtParser должен отправлять intent_detail для thinking chunks"
        
        # Проверяем структуру первого вызова
        call_data = intent_detail_calls[0][0][2]
        assert call_data["intent_id"] == "intent-123", \
            "intent_detail должен содержать правильный intent_id"
        assert call_data["type"] == "analyze", \
            "intent_detail должен иметь тип 'analyze'"
        assert "🤔" in call_data["description"], \
            "intent_detail должен содержать emoji 🤔 для thinking"
    
    @pytest.mark.asyncio
    async def test_parser_sends_intent_detail_incrementally(self):
        """
        Тест: Intent_detail должны отправляться по мере поступления chunks,
        а не все разом в конце.
        """
        # Arrange
        mock_ws = AsyncMock()
        call_timestamps = []
        
        async def capture_call(session_id, event_type, data):
            import time
            call_timestamps.append({
                "time": time.time(),
                "event_type": event_type,
                "data": data
            })
        
        mock_ws.send_event = capture_call
        
        from src.core.unified_react_engine import UnifiedReActEngine
        
        parser = UnifiedReActEngine.StreamingThoughtParser(
            ws_manager=mock_ws, 
            session_id="test-session",
            intent_id="intent-123"
        )
        
        # Act: Стримим с задержками
        await parser.process_chunk("<thought>Первая мысль. ")
        first_count = len([c for c in call_timestamps if c["event_type"] == "intent_detail"])
        
        await asyncio.sleep(0.01)  # Небольшая задержка
        
        await parser.process_chunk("Вторая мысль. ")
        second_count = len([c for c in call_timestamps if c["event_type"] == "intent_detail"])
        
        await parser.process_chunk("</thought>")
        
        # Assert: intent_detail отправляются инкрементально
        assert second_count > first_count, \
            "intent_detail должны отправляться по мере поступления chunks, не в конце"
    
    @pytest.mark.asyncio
    async def test_parser_works_without_intent_id_fallback(self):
        """
        Тест: Парсер должен работать даже если intent_id не передан (backwards compatibility).
        В этом случае не отправляет intent_detail, только thinking_chunk.
        """
        mock_ws = AsyncMock()
        mock_ws.send_event = AsyncMock()
        
        from src.core.unified_react_engine import UnifiedReActEngine
        
        # Создаём парсер БЕЗ intent_id (старое поведение)
        parser = UnifiedReActEngine.StreamingThoughtParser(
            ws_manager=mock_ws, 
            session_id="test-session"
            # intent_id не передан
        )
        
        # Act
        await parser.process_chunk("<thought>Test</thought>")
        
        # Assert: thinking_chunk должен отправляться
        thinking_calls = [
            call for call in mock_ws.send_event.call_args_list
            if call[0][1] == "thinking_chunk"
        ]
        
        assert len(thinking_calls) > 0, \
            "thinking_chunk должен отправляться даже без intent_id"


class TestThinkAndPlanPassesIntentId:
    """
    КРИТЕРИЙ 2: _think_and_plan должен передавать intent_id в StreamingThoughtParser.
    """
    
    @pytest.mark.asyncio
    async def test_think_and_plan_creates_parser_with_intent_id(self):
        """
        Тест: _think_and_plan должен создавать StreamingThoughtParser с intent_id
        из текущего контекста выполнения.
        
        Это unit-тест, проверяющий что при вызове _think_and_plan
        парсер получает intent_id из self._current_intent_id.
        """
        from src.core.unified_react_engine import UnifiedReActEngine
        
        # Arrange: Патчим StreamingThoughtParser чтобы захватить аргументы
        original_parser_class = UnifiedReActEngine.StreamingThoughtParser
        parser_init_calls = []
        
        class CapturingParser:
            """Мок-парсер для захвата аргументов инициализации."""
            def __init__(self, ws_manager, session_id, intent_id=None):
                parser_init_calls.append({
                    "ws_manager": ws_manager,
                    "session_id": session_id,
                    "intent_id": intent_id
                })
                self.thought_content = ""
                self.buffer = ""
            
            async def process_chunk(self, chunk):
                pass
            
            def get_thought(self):
                return "test thought"
            
            def get_remaining_buffer(self):
                return '{"tool_name": "FINISH", "arguments": {}, "description": "test", "reasoning": "test"}'
        
        UnifiedReActEngine.StreamingThoughtParser = CapturingParser
        
        try:
            # Создаём минимальный engine для теста
            mock_ws = AsyncMock()
            mock_ws.send_event = AsyncMock()
            
            # Создаём экземпляр engine напрямую с минимальными зависимостями
            # Используем объект без полной инициализации
            engine = object.__new__(UnifiedReActEngine)
            engine.ws_manager = mock_ws
            engine.session_id = "test-session"
            engine._current_intent_id = "intent-456"  # Это мы тестируем
            engine.capabilities = []
            
            # Мокаем LLM
            mock_llm = AsyncMock()
            
            async def mock_astream(messages):
                # Возвращаем минимальный ответ
                class MockChunk:
                    content = "<thought>test</thought><action>{}</action>"
                yield MockChunk()
            
            mock_llm.astream = mock_astream
            engine.llm = mock_llm
            
            from src.core.react_state import ReActState
            from src.core.context_manager import ConversationContext
            
            state = ReActState(goal="тестовая цель")
            context = ConversationContext(session_id="test-session")
            
            # Act - вызываем _think_and_plan
            try:
                await engine._think_and_plan(state, context, [])
            except Exception:
                pass  # Ошибки парсинга ожидаемы, нам важно что парсер был создан
            
            # Assert: Парсер должен быть создан с intent_id
            assert len(parser_init_calls) > 0, \
                "_think_and_plan должен создавать StreamingThoughtParser"
            
            assert parser_init_calls[0]["intent_id"] == "intent-456", \
                f"StreamingThoughtParser должен получать intent_id='intent-456', получил: {parser_init_calls[0].get('intent_id')}"
                
        finally:
            # Восстанавливаем оригинальный класс
            UnifiedReActEngine.StreamingThoughtParser = original_parser_class


class TestIntentDetailStructure:
    """
    КРИТЕРИЙ 3: intent_detail должен иметь правильную структуру.
    """
    
    @pytest.mark.asyncio
    async def test_intent_detail_has_correct_structure(self):
        """
        Тест: intent_detail должен содержать intent_id, type='analyze', description с 🤔.
        """
        mock_ws = AsyncMock()
        captured_events = []
        
        async def capture(session_id, event_type, data):
            captured_events.append({"type": event_type, "data": data})
        
        mock_ws.send_event = capture
        
        from src.core.unified_react_engine import UnifiedReActEngine
        
        parser = UnifiedReActEngine.StreamingThoughtParser(
            ws_manager=mock_ws,
            session_id="test-session",
            intent_id="intent-789"
        )
        
        # Act
        await parser.process_chunk("<thought>Анализирую ситуацию</thought>")
        
        # Assert
        intent_details = [e for e in captured_events if e["type"] == "intent_detail"]
        
        assert len(intent_details) > 0, "Должен быть хотя бы один intent_detail"
        
        detail = intent_details[0]["data"]
        
        # Проверяем все обязательные поля
        assert "intent_id" in detail, "intent_detail должен содержать intent_id"
        assert "type" in detail, "intent_detail должен содержать type"
        assert "description" in detail, "intent_detail должен содержать description"
        
        assert detail["type"] == "analyze", f"type должен быть 'analyze', получили '{detail['type']}'"
        assert detail["intent_id"] == "intent-789", "intent_id должен совпадать"
        assert "Анализирую" in detail["description"], "description должен содержать текст thinking"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
