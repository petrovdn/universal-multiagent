"""
TDD Tests for Conversation-based Reference Resolution.

These tests verify that:
1. When agent responds about files, the response is saved with source_files metadata
2. When user asks a follow-up question, the system finds the source file from conversation history
3. The correct file is then used for the follow-up response

Test scenario:
- User: "что в файлах?" + [image.jpg, doc.pdf]
- Agent: "На изображении человек играет в теннис. Документ содержит..."
  → saved with source_files: ["image.jpg", "doc.pdf"]
- User: "расскажи про человека подробнее"
  → find "человек" in history → get source_files → use image.jpg
"""

import pytest
from typing import List, Optional
from src.core.context_manager import ConversationContext
from src.core.file_reference_resolver import (
    extract_keywords_from_text,
    find_source_for_reference,
    extract_entities_from_response,
)


class TestFindSourceForReference:
    """Tests for finding source files from conversation history."""
    
    def setup_method(self):
        """Setup context with conversation history."""
        self.context = ConversationContext(session_id="test-session")
        
        # Simulate first exchange: user asks about files
        self.context.add_message("user", "что в файлах?")
        
        # Agent responds with file analysis - WITH source_files metadata
        self.context.add_message(
            "assistant",
            "**Изображение 'unnamed.jpg'**: На изображении человек играет в настольный теннис. "
            "Он сосредоточен, держа в руках ракетку.\n\n"
            "**PDF '9190016821.pdf'**: Документ является страховым полисом для автомобиля.",
            metadata={
                "source_files": ["unnamed.jpg", "9190016821.pdf"],
                "extracted_entities": ["человек", "теннис", "страхов", "полис", "автомобиль"]
            }
        )
    
    def test_find_source_for_person_query(self):
        """
        Query "расскажи про человека" should find image file from history.
        """
        query = "расскажи про человека подробнее"
        
        source_files = find_source_for_reference(query, self.context)
        
        # Should find the message that mentioned "человек" and return its source_files
        assert len(source_files) > 0
        assert "unnamed.jpg" in source_files
    
    def test_find_source_for_insurance_query(self):
        """
        Query "расскажи о страховке" should find PDF from history.
        """
        query = "расскажи о страховке подробнее"
        
        source_files = find_source_for_reference(query, self.context)
        
        assert len(source_files) > 0
        assert "9190016821.pdf" in source_files
    
    def test_find_source_for_tennis_query(self):
        """
        Query "он профессионал в теннисе?" should find image from history.
        """
        query = "он профессионал в теннисе?"
        
        source_files = find_source_for_reference(query, self.context)
        
        assert len(source_files) > 0
        assert "unnamed.jpg" in source_files
    
    def test_no_match_returns_empty(self):
        """
        Query with no matching terms in history should return empty list.
        """
        query = "какая погода завтра?"
        
        source_files = find_source_for_reference(query, self.context)
        
        assert source_files == []
    
    def test_finds_most_recent_match(self):
        """
        Should find the most recent message that matches the query.
        """
        # Add another message about a different person
        self.context.add_message(
            "assistant",
            "На втором фото человек в деловом костюме на совещании.",
            metadata={
                "source_files": ["meeting.jpg"],
                "extracted_entities": ["человек", "костюм", "совещание"]
            }
        )
        
        query = "расскажи про человека"
        
        source_files = find_source_for_reference(query, self.context)
        
        # Should find the MOST RECENT message mentioning "человек"
        assert "meeting.jpg" in source_files


class TestExtractEntitiesFromResponse:
    """Tests for extracting entities from agent responses."""
    
    def test_extract_entities_from_image_description(self):
        """
        Should extract relevant entities from image description.
        """
        response = "На изображении человек играет в настольный теннис. Он сосредоточен."
        
        entities = extract_entities_from_response(response)
        
        assert "человек" in entities or any("человек" in e for e in entities)
        assert "теннис" in entities or any("теннис" in e for e in entities)
    
    def test_extract_entities_from_document_description(self):
        """
        Should extract entities from document description.
        """
        response = "Документ является страховым полисом для автомобиля Kia Sportage."
        
        entities = extract_entities_from_response(response)
        
        assert any("страхов" in e.lower() for e in entities)
        assert any("автомобиль" in e.lower() or "kia" in e.lower() for e in entities)


class TestConversationHistoryWithMetadata:
    """Tests for saving and retrieving messages with source_files metadata."""
    
    def test_add_message_with_source_files(self):
        """
        Messages should be saved with source_files in metadata.
        """
        context = ConversationContext(session_id="test")
        
        context.add_message(
            "assistant",
            "На фото девушка играет в теннис.",
            metadata={"source_files": ["photo.jpg"]}
        )
        
        # Retrieve the message
        messages = context.get_recent_messages(1)
        assert len(messages) == 1
        assert messages[0]["metadata"]["source_files"] == ["photo.jpg"]
    
    def test_get_source_files_from_metadata(self):
        """
        Should be able to extract source_files from message metadata.
        """
        context = ConversationContext(session_id="test")
        
        context.add_message("assistant", "Response 1", metadata={"source_files": ["a.pdf"]})
        context.add_message("assistant", "Response 2", metadata={"source_files": ["b.jpg"]})
        
        # Get all source files from conversation
        all_sources = []
        for msg in context.messages:
            if msg.get("metadata", {}).get("source_files"):
                all_sources.extend(msg["metadata"]["source_files"])
        
        assert "a.pdf" in all_sources
        assert "b.jpg" in all_sources


class TestIntegrationWithFileResolution:
    """Integration tests combining history search with file resolution."""
    
    def test_follow_up_finds_correct_file(self):
        """
        Full flow: first query → response with source → follow-up finds source.
        """
        context = ConversationContext(session_id="test")
        
        # Simulate uploaded files
        context.add_file("img_001", {
            "filename": "photo.jpg",
            "type": "image/jpeg",
            "text": ""
        })
        context.add_file("doc_001", {
            "filename": "report.pdf",
            "type": "application/pdf",
            "text": "Отчёт о продажах за квартал"
        })
        
        # First response - agent describes files
        context.add_message(
            "assistant",
            "На фото молодая женщина занимается йогой на пляже. "
            "Отчёт содержит данные о продажах.",
            metadata={
                "source_files": ["img_001", "doc_001"],
                "extracted_entities": ["женщина", "йога", "пляж", "продаж", "отчёт"]
            }
        )
        
        # Follow-up query
        query = "расскажи подробнее о женщине, она профессионал?"
        
        source_files = find_source_for_reference(query, context)
        
        # Should find image as source
        assert "img_001" in source_files


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
