"""
TDD тесты для parse_date_range() - расширенный парсинг диапазонов дат.

Тестирует поддержку:
- "в текущем месяце", "в этом месяце"
- "в прошлом месяце"
- "в следующем месяце"
- "в январе", "в феврале" (текущий год)
- "в январе 2026" (конкретный год)
- "в первом квартале", "во втором квартале" (текущий год)
- "в первом квартале 2026" (конкретный год)
- "в 2026", "в 2025" (весь год)
"""
import pytest
import pytz
from datetime import datetime
from calendar import monthrange


class TestParseDateRange:
    """Тесты для parse_date_range()."""
    
    @pytest.fixture
    def timezone(self):
        """Timezone для тестов."""
        return "Europe/Moscow"
    
    def test_parse_current_month_range(self, timezone):
        """Тест: 'в текущем месяце', 'в этом месяце' -> весь текущий месяц."""
        try:
            from src.utils.validators import parse_date_range
        except (ImportError, AttributeError):
            pytest.skip("parse_date_range() not yet implemented")
        
        # Получаем текущую дату
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        current_year = now.year
        current_month = now.month
        days_in_month = monthrange(current_year, current_month)[1]
        
        # Тест "в текущем месяце"
        start, end = parse_date_range("в текущем месяце", timezone)
        
        assert start.year == current_year
        assert start.month == current_month
        assert start.day == 1
        assert start.hour == 0
        assert start.minute == 0
        assert start.second == 0
        
        assert end.year == current_year
        assert end.month == current_month
        assert end.day == days_in_month
        assert end.hour == 23
        assert end.minute == 59
        assert end.second == 59
        
        # Тест "в этом месяце"
        start2, end2 = parse_date_range("в этом месяце", timezone)
        assert start2 == start
        assert end2 == end
    
    def test_parse_last_month_range(self, timezone):
        """Тест: 'в прошлом месяце' -> весь предыдущий месяц."""
        try:
            from src.utils.validators import parse_date_range
        except (ImportError, AttributeError):
            pytest.skip("parse_date_range() not yet implemented")
        
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        
        # Вычисляем предыдущий месяц
        if now.month == 1:
            prev_month = 12
            prev_year = now.year - 1
        else:
            prev_month = now.month - 1
            prev_year = now.year
        
        days_in_prev_month = monthrange(prev_year, prev_month)[1]
        
        start, end = parse_date_range("в прошлом месяце", timezone)
        
        assert start.year == prev_year
        assert start.month == prev_month
        assert start.day == 1
        assert start.hour == 0
        assert start.minute == 0
        
        assert end.year == prev_year
        assert end.month == prev_month
        assert end.day == days_in_prev_month
        assert end.hour == 23
        assert end.minute == 59
        assert end.second == 59
    
    def test_parse_next_month_range(self, timezone):
        """Тест: 'в следующем месяце' -> весь следующий месяц."""
        try:
            from src.utils.validators import parse_date_range
        except (ImportError, AttributeError):
            pytest.skip("parse_date_range() not yet implemented")
        
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        
        # Вычисляем следующий месяц
        if now.month == 12:
            next_month = 1
            next_year = now.year + 1
        else:
            next_month = now.month + 1
            next_year = now.year
        
        days_in_next_month = monthrange(next_year, next_month)[1]
        
        start, end = parse_date_range("в следующем месяце", timezone)
        
        assert start.year == next_year
        assert start.month == next_month
        assert start.day == 1
        assert start.hour == 0
        assert start.minute == 0
        
        assert end.year == next_year
        assert end.month == next_month
        assert end.day == days_in_next_month
        assert end.hour == 23
        assert end.minute == 59
        assert end.second == 59
    
    def test_parse_named_month_range(self, timezone):
        """Тест: 'в январе', 'в феврале' -> весь указанный месяц текущего года."""
        try:
            from src.utils.validators import parse_date_range
        except (ImportError, AttributeError):
            pytest.skip("parse_date_range() not yet implemented")
        
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        current_year = now.year
        
        # Январь
        start, end = parse_date_range("в январе", timezone)
        assert start.year == current_year
        assert start.month == 1
        assert start.day == 1
        assert end.year == current_year
        assert end.month == 1
        assert end.day == 31
        
        # Февраль
        start, end = parse_date_range("в феврале", timezone)
        assert start.year == current_year
        assert start.month == 2
        assert start.day == 1
        assert end.year == current_year
        assert end.month == 2
        days_feb = 29 if (current_year % 4 == 0 and current_year % 100 != 0) or (current_year % 400 == 0) else 28
        assert end.day == days_feb
        
        # Март
        start, end = parse_date_range("в марте", timezone)
        assert start.year == current_year
        assert start.month == 3
        assert start.day == 1
        assert end.year == current_year
        assert end.month == 3
        assert end.day == 31
    
    def test_parse_named_month_with_year(self, timezone):
        """Тест: 'в январе 2026' -> весь указанный месяц указанного года."""
        try:
            from src.utils.validators import parse_date_range
        except (ImportError, AttributeError):
            pytest.skip("parse_date_range() not yet implemented")
        
        # Январь 2025
        start, end = parse_date_range("в январе 2025", timezone)
        assert start.year == 2025
        assert start.month == 1
        assert start.day == 1
        assert end.year == 2025
        assert end.month == 1
        assert end.day == 31
        
        # Февраль 2024 (високосный год)
        start, end = parse_date_range("в феврале 2024", timezone)
        assert start.year == 2024
        assert start.month == 2
        assert start.day == 1
        assert end.year == 2024
        assert end.month == 2
        assert end.day == 29  # 2024 високосный
    
    def test_parse_quarter_range(self, timezone):
        """Тест: 'в первом квартале', 'во втором квартале' -> весь квартал."""
        try:
            from src.utils.validators import parse_date_range
        except (ImportError, AttributeError):
            pytest.skip("parse_date_range() not yet implemented")
        
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        current_year = now.year
        
        # Первый квартал (январь-март)
        start, end = parse_date_range("в первом квартале", timezone)
        assert start.year == current_year
        assert start.month == 1
        assert start.day == 1
        assert end.year == current_year
        assert end.month == 3
        assert end.day == 31
        
        # Второй квартал (апрель-июнь)
        start, end = parse_date_range("во втором квартале", timezone)
        assert start.year == current_year
        assert start.month == 4
        assert start.day == 1
        assert end.year == current_year
        assert end.month == 6
        assert end.day == 30
        
        # Третий квартал (июль-сентябрь)
        start, end = parse_date_range("в третьем квартале", timezone)
        assert start.year == current_year
        assert start.month == 7
        assert start.day == 1
        assert end.year == current_year
        assert end.month == 9
        assert end.day == 30
        
        # Четвертый квартал (октябрь-декабрь)
        start, end = parse_date_range("в четвертом квартале", timezone)
        assert start.year == current_year
        assert start.month == 10
        assert start.day == 1
        assert end.year == current_year
        assert end.month == 12
        assert end.day == 31
    
    def test_parse_quarter_with_year(self, timezone):
        """Тест: 'в первом квартале 2025' -> весь квартал указанного года."""
        try:
            from src.utils.validators import parse_date_range
        except (ImportError, AttributeError):
            pytest.skip("parse_date_range() not yet implemented")
        
        start, end = parse_date_range("в первом квартале 2025", timezone)
        assert start.year == 2025
        assert start.month == 1
        assert start.day == 1
        assert end.year == 2025
        assert end.month == 3
        assert end.day == 31
    
    def test_parse_year_range(self, timezone):
        """Тест: 'в 2026', 'в 2025' -> весь указанный год."""
        try:
            from src.utils.validators import parse_date_range
        except (ImportError, AttributeError):
            pytest.skip("parse_date_range() not yet implemented")
        
        # Текущий год (для примера используем 2026, но проверим динамически)
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        current_year = now.year
        
        start, end = parse_date_range(f"в {current_year}", timezone)
        assert start.year == current_year
        assert start.month == 1
        assert start.day == 1
        assert start.hour == 0
        assert end.year == current_year
        assert end.month == 12
        assert end.day == 31
        assert end.hour == 23
        assert end.minute == 59
        assert end.second == 59
        
        # Прошлый год
        past_year = current_year - 1
        start, end = parse_date_range(f"в {past_year}", timezone)
        assert start.year == past_year
        assert start.month == 1
        assert start.day == 1
        assert end.year == past_year
        assert end.month == 12
        assert end.day == 31
    
    def test_parse_date_range_invalid_format(self, timezone):
        """Тест: неверный формат должен вызывать ValidationError."""
        try:
            from src.utils.validators import parse_date_range
            from src.utils.exceptions import ValidationError
        except (ImportError, AttributeError):
            pytest.skip("parse_date_range() not yet implemented")
        
        with pytest.raises(ValidationError):
            parse_date_range("неверный формат", timezone)
        
        with pytest.raises(ValidationError):
            parse_date_range("", timezone)
    
    def test_parse_datetime_still_works(self, timezone):
        """Тест: существующий parse_datetime() всё еще работает (обратная совместимость)."""
        from src.utils.validators import parse_datetime
        
        # Тест существующих форматов
        dt = parse_datetime("сегодня", timezone)
        assert isinstance(dt, datetime)
        
        dt = parse_datetime("завтра", timezone)
        assert isinstance(dt, datetime)
        
        dt = parse_datetime("2026-01-15 14:30", timezone)
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 15
