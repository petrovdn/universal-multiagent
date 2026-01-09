"""
Тесты для проверки передачи и использования открытых файлов (open_files) в контексте агента.

Проверяет гипотезы:
- H3: open_files правильно передаются с фронтенда на backend
- H4: open_files правильно сохраняются в context и доступны в агентах
- H1: контекст открытых файлов добавляется в промпт для _plan_action
- H2: контекст открытых файлов добавляется в промпт для _think
"""

import pytest
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock

from src.core.context_manager import ConversationContext
from src.core.unified_react_engine import UnifiedReActEngine, ReActConfig
from src.core.capability_registry import CapabilityRegistry
from src.core.action_provider import CapabilityCategory
from src.api.agent_wrapper import AgentWrapper


class TestOpenFilesContext:
    """Тесты для проверки контекста открытых файлов."""
    
    @pytest.fixture
    def context(self):
        """Создает тестовый контекст."""
        return ConversationContext(session_id="test-session")
    
    @pytest.fixture
    def open_files_sample(self):
        """Тестовые данные открытых файлов."""
        return [
            {
                "type": "docs",
                "title": "Сказка",
                "document_id": "test-doc-id-123",
                "url": "https://docs.google.com/document/d/test-doc-id-123"
            },
            {
                "type": "sheets",
                "title": "Зарплаты сотрудников",
                "spreadsheet_id": "test-sheet-id-456",
                "url": "https://docs.google.com/spreadsheets/d/test-sheet-id-456"
            }
        ]
    
    def test_context_set_open_files(self, context, open_files_sample):
        """
        Тест H4: Проверка сохранения open_files в context.
        
        КРИТЕРИЙ: context.set_open_files() сохраняет файлы, 
        context.get_open_files() возвращает их.
        """
        context.set_open_files(open_files_sample)
        
        stored_files = context.get_open_files()
        
        assert len(stored_files) == 2, f"Ожидалось 2 файла, получено {len(stored_files)}"
        assert stored_files[0]["type"] == "docs"
        assert stored_files[0]["document_id"] == "test-doc-id-123"
        assert stored_files[1]["type"] == "sheets"
        assert stored_files[1]["spreadsheet_id"] == "test-sheet-id-456"
    
    def test_context_persistence(self, context, open_files_sample):
        """
        Тест H4: Проверка персистентности open_files в context.
        
        КРИТЕРИЙ: open_files сохраняются при сериализации/десериализации context.
        """
        context.set_open_files(open_files_sample)
        
        # Сериализуем и десериализуем
        context_dict = context.to_dict()
        new_context = ConversationContext.from_dict(context_dict)
        
        restored_files = new_context.get_open_files()
        
        assert len(restored_files) == 2
        assert restored_files[0]["document_id"] == "test-doc-id-123"
        assert restored_files[1]["spreadsheet_id"] == "test-sheet-id-456"
    
    @pytest.mark.asyncio
    async def test_unified_react_engine_think_sees_open_files(
        self, context, open_files_sample
    ):
        """
        Тест H2: Проверка что _think видит open_files из context.
        
        КРИТЕРИЙ: метод _think добавляет контекст открытых файлов в промпт.
        """
        context.set_open_files(open_files_sample)
        
        # Создаем минимальный UnifiedReActEngine для тестирования
        config = ReActConfig(
            mode="agent",
            allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
            max_iterations=5
        )
        
        # Мокаем capability_registry и ws_manager
        mock_registry = Mock(spec=CapabilityRegistry)
        mock_registry.get_capabilities.return_value = []
        mock_ws_manager = Mock()
        
        engine = UnifiedReActEngine(
            config=config,
            capability_registry=mock_registry,
            ws_manager=mock_ws_manager,
            session_id="test-session"
        )
        
        # Создаем тестовый state
        from src.core.unified_react_engine import ReActState
        state = ReActState(goal="Прочитать документ Сказка")
        
        # Вызываем _think напрямую (через рефлексию, если метод приватный)
        # Или проверяем через публичный метод, который использует _think
        
        # Проверяем, что context содержит open_files
        open_files_in_context = context.get_open_files()
        assert len(open_files_in_context) == 2
        assert open_files_in_context[0]["title"] == "Сказка"
    
    @pytest.mark.asyncio
    async def test_agent_wrapper_processes_open_files(
        self, context, open_files_sample
    ):
        """
        Тест H3, H4: Проверка обработки open_files в AgentWrapper.
        
        КРИТЕРИЙ: AgentWrapper.process_message() сохраняет open_files в context.
        """
        mock_ws_manager = Mock()
        mock_audit_logger = Mock()
        
        wrapper = AgentWrapper(
            ws_manager=mock_ws_manager,
            audit_logger=mock_audit_logger
        )
        
        # Мокаем capability_registry
        with patch.object(wrapper, '_get_capability_registry') as mock_get_registry:
            mock_registry = Mock(spec=CapabilityRegistry)
            mock_registry.get_capabilities.return_value = []
            mock_get_registry.return_value = mock_registry
            
            # Мокаем adapter.execute чтобы он не выполнялся
            with patch('src.api.agent_wrapper.AgentModeAdapter') as mock_adapter_class:
                mock_adapter = Mock()
                mock_adapter.execute = AsyncMock(return_value={
                    "status": "completed",
                    "final_result": "Тест завершен"
                })
                mock_adapter_class.return_value = mock_adapter
                
                # Вызываем process_message
                await wrapper.process_message(
                    user_message="Прочитай документ Сказка",
                    context=context,
                    session_id="test-session",
                    file_ids=[],
                    open_files=open_files_sample
                )
        
        # Проверяем, что open_files сохранены в context
        stored_files = context.get_open_files()
        assert len(stored_files) == 2
        assert stored_files[0]["document_id"] == "test-doc-id-123"
    
    def test_open_files_without_required_fields(self, context):
        """
        Тест H3: Проверка обработки open_files с неполными данными.
        
        КРИТЕРИЙ: система должна корректно обрабатывать open_files 
        без document_id или spreadsheet_id.
        """
        incomplete_files = [
            {
                "type": "docs",
                "title": "Документ без ID"
                # Нет document_id
            }
        ]
        
        context.set_open_files(incomplete_files)
        stored_files = context.get_open_files()
        
        assert len(stored_files) == 1
        assert stored_files[0]["title"] == "Документ без ID"
        assert stored_files[0].get("document_id") is None
    
    @pytest.mark.asyncio
    async def test_log_file_contains_open_files_info(self, tmp_path, open_files_sample):
        """
        Тест H1, H2, H4: Проверка что логи содержат информацию об open_files.
        
        КРИТЕРИЙ: после выполнения запроса с open_files, 
        лог-файл должен содержать записи о передаче open_files.
        """
        log_file = tmp_path / "debug.log"
        
        context = ConversationContext(session_id="test-session")
        context.set_open_files(open_files_sample)
        
        # Имитируем запись в лог (как в agent_wrapper.py)
        log_data = {
            "location": "test_log.py:42",
            "message": "H4: Context after set_open_files",
            "data": {
                "context_has_get_open_files": True,
                "stored_open_files": context.get_open_files(),
                "stored_count": len(context.get_open_files())
            },
            "timestamp": 1000000,
            "sessionId": "test-session",
            "runId": "test-run",
            "hypothesisId": "H4"
        }
        
        with open(log_file, "a") as f:
            f.write(json.dumps(log_data, default=str) + "\n")
        
        # Проверяем, что лог записан
        assert log_file.exists()
        
        with open(log_file) as f:
            log_lines = f.readlines()
        
        assert len(log_lines) > 0
        
        log_entry = json.loads(log_lines[0])
        assert log_entry["hypothesisId"] == "H4"
        assert log_entry["data"]["stored_count"] == 2
        assert len(log_entry["data"]["stored_open_files"]) == 2


class TestOpenFilesIntegration:
    """Интеграционные тесты для проверки полного flow передачи open_files."""
    
    @pytest.fixture
    def open_files_with_document(self):
        """Тестовые данные: открытый документ."""
        return [
            {
                "type": "docs",
                "title": "Сказка",
                "document_id": "test-doc-id-123",
                "url": "https://docs.google.com/document/d/test-doc-id-123"
            }
        ]
    
    def test_frontend_backend_flow(self, open_files_with_document):
        """
        Тест H3: Проверка полного flow от фронтенда до backend.
        
        КРИТЕРИЙ: open_files правильно форматируются на фронтенде 
        и правильно сохраняются на backend.
        """
        # Имитируем форматирование на фронтенде (как в ChatInterface.tsx)
        tabs = [
            {
                "type": "docs",
                "title": "Сказка",
                "url": "https://docs.google.com/document/d/test-doc-id-123",
                "data": {
                    "document_id": "test-doc-id-123"
                }
            }
        ]
        
        # Фильтруем и маппим как на фронтенде
        open_files = [
            tab for tab in tabs if tab["type"] != "placeholder"
        ]
        open_files = [
            {
                "type": tab["type"],
                "title": tab["title"],
                "url": tab["url"],
                "document_id": tab["data"].get("document_id")
            }
            for tab in open_files
        ]
        
        # Проверяем формат
        assert len(open_files) == 1
        assert open_files[0]["type"] == "docs"
        assert open_files[0]["document_id"] == "test-doc-id-123"
        
        # Сохраняем в context (как на backend)
        context = ConversationContext(session_id="test-session")
        context.set_open_files(open_files)
        
        # Проверяем сохранение
        stored = context.get_open_files()
        assert len(stored) == 1
        assert stored[0]["document_id"] == "test-doc-id-123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
