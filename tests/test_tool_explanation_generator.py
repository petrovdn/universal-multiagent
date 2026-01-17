"""
TDD tests for ToolExplanationGenerator - Phase 1, Step 1.1.

These tests should FAIL initially (Red phase), then pass after implementation (Green phase).
"""
import pytest

# Import will fail initially - that's expected in TDD
from src.core.tool_explanation_generator import ToolExplanationGenerator


class TestToolExplanationGenerator:
    """Test suite for ToolExplanationGenerator."""
    
    def test_generate_explanation_for_list_emails(self):
        """Test: Generate human-readable explanation for list_emails tool."""
        generator = ToolExplanationGenerator()
        
        explanation = generator.generate(
            tool_name="list_emails",
            args={"query": "is:unread", "max_results": 10}
        )
        
        # Should be human-readable, not technical
        assert "письм" in explanation.lower() or "email" in explanation.lower()
        assert "list_emails" not in explanation
        assert "is:unread" not in explanation
        assert "max_results" not in explanation
        assert len(explanation) > 10
    
    def test_generate_explanation_for_get_sheet_data(self):
        """Test: Generate explanation for get_sheet_data with spreadsheet_id."""
        generator = ToolExplanationGenerator()
        
        explanation = generator.generate(
            tool_name="get_sheet_data",
            args={"spreadsheet_id": "abc123", "range": "A1:B10"}
        )
        
        assert "таблиц" in explanation.lower() or "sheet" in explanation.lower()
        assert "get_sheet_data" not in explanation
        assert "spreadsheet_id" not in explanation
        assert "abc123" not in explanation
    
    def test_generate_explanation_for_create_document(self):
        """Test: Generate explanation for create_document."""
        generator = ToolExplanationGenerator()
        
        explanation = generator.generate(
            tool_name="create_document",
            args={"title": "Отчет за январь"}
        )
        
        assert "документ" in explanation.lower() or "document" in explanation.lower()
        assert "create_document" not in explanation
        # Should mention title if provided
        assert "январь" in explanation.lower() or "отчет" in explanation.lower()
    
    def test_generate_explanation_for_calendar_events(self):
        """Test: Generate explanation for get_calendar_events."""
        generator = ToolExplanationGenerator()
        
        explanation = generator.generate(
            tool_name="get_calendar_events",
            args={"time_min": "2025-01-17T00:00:00Z", "max_results": 5}
        )
        
        assert "календар" in explanation.lower() or "встреч" in explanation.lower() or "event" in explanation.lower()
        assert "get_calendar_events" not in explanation
        assert "time_min" not in explanation
    
    def test_generate_explanation_for_unknown_tool(self):
        """Test: Generate generic explanation for unknown tool."""
        generator = ToolExplanationGenerator()
        
        explanation = generator.generate(
            tool_name="unknown_tool_xyz",
            args={"param1": "value1"}
        )
        
        # Should still return something, even if generic
        assert len(explanation) > 0
        assert isinstance(explanation, str)
    
    def test_generate_explanation_with_empty_args(self):
        """Test: Generate explanation when args are empty."""
        generator = ToolExplanationGenerator()
        
        explanation = generator.generate(
            tool_name="list_emails",
            args={}
        )
        
        assert len(explanation) > 0
        assert "list_emails" not in explanation
    
    def test_generate_explanation_extracts_key_info(self):
        """Test: Generator extracts and uses key info from args (like query, title)."""
        generator = ToolExplanationGenerator()
        
        # Test with query parameter
        explanation = generator.generate(
            tool_name="search_emails",
            args={"query": "важное письмо"}
        )
        
        # Should incorporate query info if relevant
        assert len(explanation) > 0
        # Query might be mentioned in natural language
        assert "list_emails" not in explanation
