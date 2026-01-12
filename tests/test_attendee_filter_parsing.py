"""
TDD тесты для parse_attendee_filter() - парсинг фильтров участников из естественного языка.

Тестирует поддержку:
- "Марат и Аня" (AND оператор)
- "Марат или Аня" (OR оператор)
- "marat@", "petrov@" (частичные email)
- "@lad24.ru" (частичный домен)
- "Марат и anna@lad24.ru" (смешанные имена и email)
- "Марат" (одиночный участник)
"""
import pytest


class TestParseAttendeeFilter:
    """Тесты для parse_attendee_filter()."""
    
    def test_parse_and_filter(self):
        """Тест: 'Марат и Аня' -> оператор AND, паттерны ['марат', 'аня']."""
        try:
            from src.utils.validators import parse_attendee_filter
        except (ImportError, AttributeError):
            pytest.skip("parse_attendee_filter() not yet implemented")
        
        result = parse_attendee_filter("Марат и Аня")
        
        assert result["operator"] == "AND"
        assert "марат" in result["patterns"]
        assert "аня" in result["patterns"]
        assert len(result["patterns"]) == 2
        
        # Также с email
        result = parse_attendee_filter("marat@ и anna@")
        assert result["operator"] == "AND"
        assert "marat@" in result["patterns"]
        assert "anna@" in result["patterns"]
    
    def test_parse_or_filter(self):
        """Тест: 'Марат или Аня' -> оператор OR, паттерны ['марат', 'аня']."""
        try:
            from src.utils.validators import parse_attendee_filter
        except (ImportError, AttributeError):
            pytest.skip("parse_attendee_filter() not yet implemented")
        
        result = parse_attendee_filter("Марат или Аня")
        
        assert result["operator"] == "OR"
        assert "марат" in result["patterns"]
        assert "аня" in result["patterns"]
        assert len(result["patterns"]) == 2
        
        # Также с email
        result = parse_attendee_filter("marat@ или anna@")
        assert result["operator"] == "OR"
        assert "marat@" in result["patterns"]
        assert "anna@" in result["patterns"]
    
    def test_parse_partial_email(self):
        """Тест: 'marat@', 'petrov@', '@lad24.ru' -> частичные email."""
        try:
            from src.utils.validators import parse_attendee_filter
        except (ImportError, AttributeError):
            pytest.skip("parse_attendee_filter() not yet implemented")
        
        # Частичный email до @
        result = parse_attendee_filter("marat@")
        assert result["operator"] == "OR"  # По умолчанию OR для одного паттерна
        assert "marat@" in result["patterns"]
        
        # Частичный домен после @
        result = parse_attendee_filter("@lad24.ru")
        assert "@lad24.ru" in result["patterns"]
        
        # Несколько частичных email
        result = parse_attendee_filter("marat@ или petrov@")
        assert result["operator"] == "OR"
        assert "marat@" in result["patterns"]
        assert "petrov@" in result["patterns"]
    
    def test_parse_mixed_names_and_emails(self):
        """Тест: 'Марат и anna@lad24.ru' -> смешанные имена и email."""
        try:
            from src.utils.validators import parse_attendee_filter
        except (ImportError, AttributeError):
            pytest.skip("parse_attendee_filter() not yet implemented")
        
        result = parse_attendee_filter("Марат и anna@lad24.ru")
        
        assert result["operator"] == "AND"
        assert "марат" in result["patterns"]
        assert "anna@lad24.ru" in result["patterns"]
    
    def test_parse_complex_filter(self):
        """Тест: 'Марат и (Аня или Петров)' -> сложные комбинации."""
        try:
            from src.utils.validators import parse_attendee_filter
        except (ImportError, AttributeError):
            pytest.skip("parse_attendee_filter() not yet implemented")
        
        # Простая версия - пока не поддерживаем скобки, только простые AND/OR
        # Для простоты тестируем простые комбинации
        result = parse_attendee_filter("Марат и Аня и Петров")
        assert result["operator"] == "AND"
        assert len(result["patterns"]) == 3
    
    def test_parse_single_attendee(self):
        """Тест: 'Марат', 'marat@lad24.ru' -> одиночный участник."""
        try:
            from src.utils.validators import parse_attendee_filter
        except (ImportError, AttributeError):
            pytest.skip("parse_attendee_filter() not yet implemented")
        
        # Имя
        result = parse_attendee_filter("Марат")
        assert result["operator"] == "OR"  # По умолчанию OR
        assert "марат" in result["patterns"]
        assert len(result["patterns"]) == 1
        
        # Полный email
        result = parse_attendee_filter("marat@lad24.ru")
        assert "marat@lad24.ru" in result["patterns"]
        assert len(result["patterns"]) == 1
    
    def test_parse_empty_or_invalid(self):
        """Тест: пустая или неверная строка должна вызывать ValidationError."""
        try:
            from src.utils.validators import parse_attendee_filter
            from src.utils.exceptions import ValidationError
        except (ImportError, AttributeError):
            pytest.skip("parse_attendee_filter() not yet implemented")
        
        with pytest.raises(ValidationError):
            parse_attendee_filter("")
        
        with pytest.raises(ValidationError):
            parse_attendee_filter("   ")
