"""
TDD тесты для стриминга Python кода в реальном времени.

КРИТЕРИИ:
1. StreamingThoughtParser должен находить паттерн execute_python_code в буфере
2. При обнаружении execute_python_code должен отправляться code_display_start
3. Код должен стримиться через code_chunk по мере поступления токенов
4. Правильно обрабатывать экранированные символы (\n, \t, \", \\)
5. При завершении кода должен отправляться code_display_complete
6. Код должен стримиться инкрементально (накопленный код в каждом chunk)
7. Код должен правильно стримиться когда приходит в нескольких chunks
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from tests.conftest import MockWebSocketManager


class TestCodeStreamingRealtime:
    """Тесты для стриминга Python кода в реальном времени."""
    
    @pytest.mark.asyncio
    async def test_detects_execute_python_code_pattern(self):
        """
        Тест: Парсер должен находить паттерн "tool_name": "execute_python_code" в буфере.
        """
        # Arrange
        mock_ws = MockWebSocketManager()
        
        from src.core.unified_react_engine import UnifiedReActEngine
        
        parser = UnifiedReActEngine.StreamingThoughtParser(
            ws_manager=mock_ws,
            session_id="test-session"
        )
        
        # Act: Симулируем поступление JSON с execute_python_code
        await parser.process_chunk('{"tool_name": "execute_python_code"')
        
        # Assert: Парсер должен обнаружить паттерн (проверяем через внутреннее состояние)
        # После реализации, code_streaming_started должен быть True
        assert hasattr(parser, 'code_streaming_started'), \
            "Parser должен иметь поле code_streaming_started"
    
    @pytest.mark.asyncio
    async def test_sends_code_display_start(self):
        """
        Тест: При обнаружении execute_python_code должен отправляться code_display_start
        с правильными полями (filename: "analysis.py", language: "python").
        """
        # Arrange
        mock_ws = MockWebSocketManager()
        
        from src.core.unified_react_engine import UnifiedReActEngine
        
        parser = UnifiedReActEngine.StreamingThoughtParser(
            ws_manager=mock_ws,
            session_id="test-session"
        )
        
        # Act: Симулируем поступление JSON с execute_python_code и началом кода
        await parser.process_chunk('{"tool_name": "execute_python_code", "arguments": {"code": "')
        
        # Assert: Должно быть отправлено событие code_display_start
        code_display_start_events = [
            e for e in mock_ws.events 
            if e["type"] == "code_display_start"
        ]
        
        assert len(code_display_start_events) > 0, \
            "Должно быть отправлено событие code_display_start"
        
        event_data = code_display_start_events[0]["data"]
        assert event_data["filename"] == "analysis.py", \
            f"filename должен быть 'analysis.py', получен '{event_data.get('filename')}'"
        assert event_data["language"] == "python", \
            f"language должен быть 'python', получен '{event_data.get('language')}'"
    
    @pytest.mark.asyncio
    async def test_streams_code_in_realtime(self):
        """
        Тест: Код должен стримиться через code_chunk по мере поступления токенов, а не все разом.
        """
        # Arrange
        mock_ws = MockWebSocketManager()
        
        from src.core.unified_react_engine import UnifiedReActEngine
        
        parser = UnifiedReActEngine.StreamingThoughtParser(
            ws_manager=mock_ws,
            session_id="test-session"
        )
        
        # Act: Симулируем поступление кода по частям
        await parser.process_chunk('{"tool_name": "execute_python_code", "arguments": {"code": "import json')
        code_chunks_1 = [e for e in mock_ws.events if e["type"] == "code_chunk"]
        
        await parser.process_chunk('\\n')
        code_chunks_2 = [e for e in mock_ws.events if e["type"] == "code_chunk"]
        
        await parser.process_chunk('result = {}"}')
        code_chunks_3 = [e for e in mock_ws.events if e["type"] == "code_chunk"]
        
        # Assert: Код должен стримиться инкрементально
        assert len(code_chunks_2) > len(code_chunks_1), \
            "Код должен стримиться по мере поступления токенов"
        assert len(code_chunks_3) > len(code_chunks_2), \
            "Код должен продолжать стримиться"
    
    @pytest.mark.asyncio
    async def test_handles_escaped_characters(self):
        """
        Тест: Правильно обрабатывать экранированные символы.
        - \\n → \\n (новая строка)
        - \\t → \\t (табуляция)
        - \\r → \\r (возврат каретки)
        - \\" → " (кавычка внутри строки)
        - \\\\ → \\ (обратный слэш)
        """
        # Arrange
        mock_ws = MockWebSocketManager()
        
        from src.core.unified_react_engine import UnifiedReActEngine
        
        parser = UnifiedReActEngine.StreamingThoughtParser(
            ws_manager=mock_ws,
            session_id="test-session"
        )
        
        # Act: Симулируем поступление кода с экранированными символами
        code_with_escapes = '{"tool_name": "execute_python_code", "arguments": {"code": "line1\\nline2\\ttabbed\\"quote\\\\backslash"}'
        await parser.process_chunk(code_with_escapes)
        
        # Assert: Найти последний code_chunk и проверить что экранированные символы обработаны
        code_chunks = [e for e in mock_ws.events if e["type"] == "code_chunk"]
        
        assert len(code_chunks) > 0, \
            "Должен быть хотя бы один code_chunk"
        
        last_code = code_chunks[-1]["data"]["code"]
        
        # Проверяем что экранированные символы правильно обработаны
        assert "\n" in last_code, \
            "\\n должен быть преобразован в новую строку"
        assert "\t" in last_code, \
            "\\t должен быть преобразован в табуляцию"
        assert '"' in last_code, \
            '\\" должен быть преобразован в кавычку'
        assert "\\" in last_code or last_code.count("\\") > 0, \
            "\\\\ должен быть преобразован в обратный слэш"
    
    @pytest.mark.asyncio
    async def test_sends_code_display_complete(self):
        """
        Тест: При завершении кода (найдена закрывающая кавычка) должен отправляться code_display_complete.
        """
        # Arrange
        mock_ws = MockWebSocketManager()
        
        from src.core.unified_react_engine import UnifiedReActEngine
        
        parser = UnifiedReActEngine.StreamingThoughtParser(
            ws_manager=mock_ws,
            session_id="test-session"
        )
        
        # Act: Симулируем полный цикл стриминга кода
        await parser.process_chunk('{"tool_name": "execute_python_code", "arguments": {"code": "import json')
        await parser.process_chunk('\\nresult = {}"}')
        
        # Assert: Должно быть отправлено событие code_display_complete
        code_display_complete_events = [
            e for e in mock_ws.events 
            if e["type"] == "code_display_complete"
        ]
        
        assert len(code_display_complete_events) > 0, \
            "Должно быть отправлено событие code_display_complete"
        
        event_data = code_display_complete_events[0]["data"]
        assert event_data["filename"] == "analysis.py", \
            f"filename должен быть 'analysis.py', получен '{event_data.get('filename')}'"
        assert "code" in event_data, \
            "code_display_complete должен содержать поле code"
    
    @pytest.mark.asyncio
    async def test_streams_code_incrementally(self):
        """
        Тест: Код должен стримиться инкрементально (каждый code_chunk содержит накопленный код).
        """
        # Arrange
        mock_ws = MockWebSocketManager()
        
        from src.core.unified_react_engine import UnifiedReActEngine
        
        parser = UnifiedReActEngine.StreamingThoughtParser(
            ws_manager=mock_ws,
            session_id="test-session"
        )
        
        # Act: Симулируем поступление кода по частям
        await parser.process_chunk('{"tool_name": "execute_python_code", "arguments": {"code": "a')
        chunk_1 = [e for e in mock_ws.events if e["type"] == "code_chunk"]
        
        await parser.process_chunk('b')
        chunk_2 = [e for e in mock_ws.events if e["type"] == "code_chunk"]
        
        await parser.process_chunk('c"}')
        chunk_3 = [e for e in mock_ws.events if e["type"] == "code_chunk"]
        
        # Assert: Каждый последующий chunk должен содержать больше кода
        if len(chunk_1) > 0:
            code_1 = chunk_1[-1]["data"]["code"]
            if len(chunk_2) > 0:
                code_2 = chunk_2[-1]["data"]["code"]
                assert len(code_2) >= len(code_1), \
                    "Второй chunk должен содержать больше или столько же кода, как первый"
                assert "a" in code_2, \
                    "Второй chunk должен содержать код из первого chunk"
                assert "b" in code_2, \
                    "Второй chunk должен содержать новый код"
        
        if len(chunk_3) > 0:
            code_3 = chunk_3[-1]["data"]["code"]
            assert "a" in code_3 and "b" in code_3 and "c" in code_3, \
                "Третий chunk должен содержать весь накопленный код"
    
    @pytest.mark.asyncio
    async def test_handles_code_across_multiple_chunks(self):
        """
        Тест: Код должен правильно стримиться когда приходит в нескольких chunks.
        """
        # Arrange
        mock_ws = MockWebSocketManager()
        
        from src.core.unified_react_engine import UnifiedReActEngine
        
        parser = UnifiedReActEngine.StreamingThoughtParser(
            ws_manager=mock_ws,
            session_id="test-session"
        )
        
        # Act: Симулируем поступление JSON и кода в разных chunks
        await parser.process_chunk('{"tool_name": "execute_python_code", "arguments": {"code": "')
        await parser.process_chunk('import json')
        await parser.process_chunk('\\n')
        await parser.process_chunk('result = {}')
        await parser.process_chunk('"}')
        
        # Assert: Должны быть отправлены события для всех частей кода
        code_chunks = [e for e in mock_ws.events if e["type"] == "code_chunk"]
        
        assert len(code_chunks) > 0, \
            "Должен быть хотя бы один code_chunk"
        
        # Последний chunk должен содержать весь код
        final_code = code_chunks[-1]["data"]["code"]
        assert "import json" in final_code, \
            "Финальный код должен содержать 'import json'"
        assert "\n" in final_code, \
            "Финальный код должен содержать новую строку"
        assert "result = {}" in final_code, \
            "Финальный код должен содержать 'result = {}'"
        
        # Должно быть отправлено code_display_complete
        complete_events = [e for e in mock_ws.events if e["type"] == "code_display_complete"]
        assert len(complete_events) > 0, \
            "Должно быть отправлено code_display_complete"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
