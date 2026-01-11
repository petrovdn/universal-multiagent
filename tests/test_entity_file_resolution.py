"""
TDD Tests for Entity-based File Resolution.

These tests verify that:
1. When files are uploaded, they are added to entity_memory with keywords/description
2. When user asks a follow-up question, the system identifies the relevant file
3. Only relevant files are passed to LLM for processing

Test scenarios:
- "расскажи о страховке" → should identify insurance PDF, not all files
- "про девушку" → should identify image file
- "что в налоговом уведомлении" → should identify tax PDF
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any, List, Optional

# Import modules under test
from src.core.entity_memory import EntityMemory, EntityReference
from src.core.context_manager import ConversationContext
from src.core.file_reference_resolver import (
    resolve_file_reference,
    extract_keywords_from_text,
    add_file_with_keywords,
    get_relevant_file_ids,
)


class TestEntityMemoryForFiles:
    """Tests for adding uploaded files to entity_memory."""
    
    def test_add_uploaded_file_to_entity_memory(self):
        """
        When a file is uploaded, it should be added to entity_memory
        with extracted keywords from its content.
        """
        memory = EntityMemory()
        
        # Simulate adding an uploaded file with keywords
        memory.add_reference(
            entity_type="file",
            entity_id="file_123",
            name="9190016821.pdf",
            metadata={
                "type": "application/pdf",
                "keywords": ["страхов", "полис", "автомобиль", "kia", "sportage"],
                "description": "Страховой полис для автомобиля Kia Sportage"
            }
        )
        
        # Verify file was added
        assert memory.has_entities_of_type("file")
        latest = memory.get_latest("file")
        assert latest is not None
        assert latest.entity_id == "file_123"
        assert "страхов" in latest.metadata.get("keywords", [])
    
    def test_add_multiple_files_with_different_keywords(self):
        """
        Multiple files should be stored with their own keywords.
        """
        memory = EntityMemory()
        
        # Add insurance PDF
        memory.add_reference(
            entity_type="file",
            entity_id="file_1",
            name="insurance.pdf",
            metadata={
                "keywords": ["страхов", "полис", "автомобиль"],
                "description": "Страховой полис"
            }
        )
        
        # Add tax document
        memory.add_reference(
            entity_type="file",
            entity_id="file_2", 
            name="tax_notice.pdf",
            metadata={
                "keywords": ["налог", "уведомление", "ндфл", "доход"],
                "description": "Налоговое уведомление"
            }
        )
        
        # Add image
        memory.add_reference(
            entity_type="file",
            entity_id="file_3",
            name="photo.jpg",
            metadata={
                "keywords": ["изображение", "фото", "девушка", "теннис"],
                "description": "Фото девушки играющей в теннис"
            }
        )
        
        # All three should be stored
        entities = memory._entities.get("file", [])
        assert len(entities) == 3


class TestFileReferenceResolution:
    """Tests for resolving file references from user queries."""
    
    def setup_method(self):
        """Setup entity memory with test files."""
        self.memory = EntityMemory()
        
        # Add test files
        self.memory.add_reference(
            entity_type="file",
            entity_id="insurance_file",
            name="9190016821.pdf",
            metadata={
                "keywords": ["страхов", "полис", "автомобиль", "kia"],
                "description": "Страховой полис для автомобиля"
            }
        )
        
        self.memory.add_reference(
            entity_type="file",
            entity_id="tax_file",
            name="uved-871688686.pdf",
            metadata={
                "keywords": ["налог", "уведомление", "ндфл", "перечень"],
                "description": "Налоговое уведомление с перечнем налогов"
            }
        )
        
        self.memory.add_reference(
            entity_type="file",
            entity_id="image_file",
            name="unnamed.jpg",
            metadata={
                "keywords": ["фото", "девушка", "теннис", "спорт"],
                "description": "Фото девушки играющей в настольный теннис"
            }
        )
        
        self.memory.add_reference(
            entity_type="file",
            entity_id="strategy_file",
            name="Методология работы со стратегией.docx",
            metadata={
                "keywords": ["методология", "стратегия", "okr", "цели"],
                "description": "Документ о методологии работы со стратегией"
            }
        )
    
    def test_resolve_insurance_query(self):
        """
        Query "расскажи о страховке" should resolve to insurance PDF.
        """
        query = "расскажи о страховке"
        
        resolved_file_id = resolve_file_reference(query, self.memory)
        
        assert resolved_file_id == "insurance_file"
    
    def test_resolve_tax_query(self):
        """
        Query "что за перечень налогов?" should resolve to tax PDF.
        """
        query = "что за перечень налогов? на какую сумму?"
        
        resolved_file_id = resolve_file_reference(query, self.memory)
        
        assert resolved_file_id == "tax_file"
    
    def test_resolve_girl_image_query(self):
        """
        Query "про девушку расскажи" should resolve to image file.
        """
        query = "про девушку расскажи, является ли она профессиональным игроком?"
        
        resolved_file_id = resolve_file_reference(query, self.memory)
        
        assert resolved_file_id == "image_file"
    
    def test_resolve_strategy_query(self):
        """
        Query "что в документе про стратегию?" should resolve to strategy doc.
        """
        query = "что в документе про стратегию?"
        
        resolved_file_id = resolve_file_reference(query, self.memory)
        
        assert resolved_file_id == "strategy_file"
    
    def test_no_match_returns_none(self):
        """
        Query with no matching keywords should return None.
        """
        query = "какая погода завтра?"
        
        resolved_file_id = resolve_file_reference(query, self.memory)
        
        assert resolved_file_id is None
    
    def test_partial_keyword_match(self):
        """
        Partial keyword matches should work (e.g., "налог" matches "налоговое").
        """
        query = "покажи налоговые данные"
        
        resolved_file_id = resolve_file_reference(query, self.memory)
        
        assert resolved_file_id == "tax_file"


class TestKeywordExtraction:
    """Tests for extracting keywords from file content."""
    
    def test_extract_keywords_from_insurance_text(self):
        """
        Should extract relevant keywords from insurance document text.
        """
        text = """
        СТРАХОВОЙ ПОЛИС
        Транспортное средство: Kia Sportage
        Страховая премия: 45000 руб.
        Покрытие: КАСКО
        """
        
        keywords = extract_keywords_from_text(text)
        
        assert "страхов" in keywords or "страховой" in keywords
        assert "kia" in keywords or "транспорт" in keywords
    
    def test_extract_keywords_from_tax_text(self):
        """
        Should extract relevant keywords from tax document.
        """
        text = """
        НАЛОГОВОЕ УВЕДОМЛЕНИЕ
        Налог на доходы физических лиц (НДФЛ)
        Сумма к уплате: 15000 руб.
        Перечень налогов за 2023 год
        """
        
        keywords = extract_keywords_from_text(text)
        
        assert "налог" in keywords or "налоговое" in keywords
        assert "ндфл" in keywords or "доход" in keywords


class TestIntegrationWithContext:
    """Integration tests with ConversationContext."""
    
    def test_context_stores_file_with_keywords(self):
        """
        When file is added to context, keywords should be stored in entity_memory.
        """
        context = ConversationContext(session_id="test-session")
        
        # Add file to context (simulating upload)
        file_id = "test_file_1"
        file_data = {
            "filename": "insurance.pdf",
            "type": "application/pdf",
            "text": "Страховой полис для автомобиля Kia Sportage"
        }
        
        # This should also add to entity_memory with keywords
        add_file_with_keywords(context, file_id, file_data)
        
        # Verify entity_memory has the file
        assert context.entity_memory.has_entities_of_type("file")
        latest = context.entity_memory.get_latest("file")
        assert latest is not None
        assert latest.entity_id == file_id
        assert "keywords" in latest.metadata
    
    def test_follow_up_uses_relevant_file_only(self):
        """
        Follow-up question should identify and use only the relevant file.
        """
        context = ConversationContext(session_id="test-session")
        
        # Add multiple files
        add_file_with_keywords(context, "file_1", {
            "filename": "insurance.pdf",
            "type": "application/pdf",
            "text": "Страховой полис автомобиля"
        })
        
        add_file_with_keywords(context, "file_2", {
            "filename": "tax.pdf",
            "type": "application/pdf", 
            "text": "Налоговое уведомление НДФЛ"
        })
        
        # Query about insurance
        query = "расскажи подробнее о страховке"
        
        relevant_ids = get_relevant_file_ids(query, context)
        
        assert len(relevant_ids) == 1
        assert relevant_ids[0] == "file_1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
