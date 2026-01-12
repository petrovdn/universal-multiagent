"""
TDD тесты для filter_events_by_attendees() - фильтрация событий календаря по участникам.

Тестирует:
- Фильтрацию событий по участникам (AND логика)
- Фильтрацию событий по участникам (OR логика)
- Фильтрацию по частичным email
- События без совпадений
- События со всеми совпадениями
- Проверку всех участников встречи
"""
import pytest


class TestFilterEventsByAttendees:
    """Тесты для filter_events_by_attendees()."""
    
    @pytest.fixture
    def sample_events(self):
        """Примеры событий для тестов."""
        return [
            {
                "summary": "Meeting 1",
                "attendees": [
                    {"email": "marat@lad24.ru", "displayName": "Марат"},
                    {"email": "anna@lad24.ru", "displayName": "Аня"}
                ]
            },
            {
                "summary": "Meeting 2",
                "attendees": [
                    {"email": "marat@lad24.ru", "displayName": "Марат"}
                ]
            },
            {
                "summary": "Meeting 3",
                "attendees": [
                    {"email": "petrov@lad24.ru", "displayName": "Петров"},
                    {"email": "anna@lad24.ru", "displayName": "Аня"}
                ]
            },
            {
                "summary": "Meeting 4",
                "attendees": [
                    {"email": "other@example.com", "displayName": "Other"}
                ]
            },
            {
                "summary": "Meeting 5",
                "attendees": []  # Нет участников
            }
        ]
    
    def test_filter_events_by_attendee_and(self, sample_events):
        """Тест: события где есть Марат И Аня."""
        try:
            from src.mcp_tools.calendar_tools import filter_events_by_attendees
        except (ImportError, AttributeError):
            pytest.skip("filter_events_by_attendees() not yet implemented")
        
        filter_config = {
            "operator": "AND",
            "patterns": ["марат", "аня"]
        }
        
        result = filter_events_by_attendees(sample_events, filter_config)
        
        # Только Meeting 1 содержит и Марата, и Аню
        assert len(result) == 1
        assert result[0]["summary"] == "Meeting 1"
    
    def test_filter_events_by_attendee_or(self, sample_events):
        """Тест: события где есть Марат ИЛИ Аня."""
        try:
            from src.mcp_tools.calendar_tools import filter_events_by_attendees
        except (ImportError, AttributeError):
            pytest.skip("filter_events_by_attendees() not yet implemented")
        
        filter_config = {
            "operator": "OR",
            "patterns": ["марат", "аня"]
        }
        
        result = filter_events_by_attendees(sample_events, filter_config)
        
        # Meeting 1 (Марат и Аня), Meeting 2 (Марат), Meeting 3 (Аня)
        assert len(result) == 3
        summaries = [e["summary"] for e in result]
        assert "Meeting 1" in summaries
        assert "Meeting 2" in summaries
        assert "Meeting 3" in summaries
    
    def test_filter_events_by_partial_email(self, sample_events):
        """Тест: события с 'marat@' в email участника."""
        try:
            from src.mcp_tools.calendar_tools import filter_events_by_attendees
        except (ImportError, AttributeError):
            pytest.skip("filter_events_by_attendees() not yet implemented")
        
        filter_config = {
            "operator": "OR",
            "patterns": ["marat@"]
        }
        
        result = filter_events_by_attendees(sample_events, filter_config)
        
        # Meeting 1 и Meeting 2 содержат marat@lad24.ru
        assert len(result) == 2
        summaries = [e["summary"] for e in result]
        assert "Meeting 1" in summaries
        assert "Meeting 2" in summaries
    
    def test_filter_events_no_match(self, sample_events):
        """Тест: нет событий, соответствующих фильтру."""
        try:
            from src.mcp_tools.calendar_tools import filter_events_by_attendees
        except (ImportError, AttributeError):
            pytest.skip("filter_events_by_attendees() not yet implemented")
        
        filter_config = {
            "operator": "OR",
            "patterns": ["nonexistent@example.com"]
        }
        
        result = filter_events_by_attendees(sample_events, filter_config)
        
        assert len(result) == 0
    
    def test_filter_events_all_match(self, sample_events):
        """Тест: все события соответствуют фильтру."""
        try:
            from src.mcp_tools.calendar_tools import filter_events_by_attendees
        except (ImportError, AttributeError):
            pytest.skip("filter_events_by_attendees() not yet implemented")
        
        # Фильтр, который совпадает со всеми (пустой или очень широкий)
        # Но в реальности лучше использовать фильтр, который действительно совпадает со всеми
        filter_config = {
            "operator": "OR",
            "patterns": ["@"]  # Частичный паттерн, который может совпадать со всеми email
        }
        
        result = filter_events_by_attendees(sample_events, filter_config)
        
        # Все события с участниками должны совпадать
        # Meeting 5 без участников не должен совпадать
        assert len(result) == 4  # Meeting 1-4
    
    def test_filter_events_with_multiple_attendees(self, sample_events):
        """Тест: проверка всех участников встречи."""
        try:
            from src.mcp_tools.calendar_tools import filter_events_by_attendees
        except (ImportError, AttributeError):
            pytest.skip("filter_events_by_attendees() not yet implemented")
        
        # Тест AND логики: должно проверять ВСЕХ участников
        filter_config = {
            "operator": "AND",
            "patterns": ["petrov@", "аня"]
        }
        
        result = filter_events_by_attendees(sample_events, filter_config)
        
        # Только Meeting 3 содержит и Петрова, и Аню
        assert len(result) == 1
        assert result[0]["summary"] == "Meeting 3"
    
    def test_filter_events_with_domain_pattern(self, sample_events):
        """Тест: фильтрация по домену '@lad24.ru'."""
        try:
            from src.mcp_tools.calendar_tools import filter_events_by_attendees
        except (ImportError, AttributeError):
            pytest.skip("filter_events_by_attendees() not yet implemented")
        
        filter_config = {
            "operator": "OR",
            "patterns": ["@lad24.ru"]
        }
        
        result = filter_events_by_attendees(sample_events, filter_config)
        
        # Meeting 1, 2, 3 содержат участников с @lad24.ru
        assert len(result) == 3
        summaries = [e["summary"] for e in result]
        assert "Meeting 1" in summaries
        assert "Meeting 2" in summaries
        assert "Meeting 3" in summaries
