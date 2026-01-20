"""
Изолированные тесты для GuardrailsLoader (без conftest).
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.guardrails.guardrails_loader import GuardrailsLoader


def test_guardrails_loader_loads_from_file():
    """Test: GuardrailsLoader должен загружать GUARDRAILS.md"""
    loader = GuardrailsLoader()
    guardrails = loader.load_guardrails()
    
    assert guardrails is not None
    assert len(guardrails) > 0
    assert "<guardrails" in guardrails
    assert "priority=\"critical\"" in guardrails
    print("✅ test_guardrails_loader_loads_from_file PASSED")


def test_guardrails_loader_caches_in_memory():
    """Test: GuardrailsLoader должен кешировать в памяти"""
    loader = GuardrailsLoader()
    
    # First load
    guardrails1 = loader.load_guardrails()
    
    # Second load (should be cached - same content)
    guardrails2 = loader.load_guardrails()
    
    assert guardrails1 == guardrails2
    assert len(guardrails1) > 0
    print("✅ test_guardrails_loader_caches_in_memory PASSED")


def test_guardrails_loader_invalidates_on_file_change(tmp_path):
    """Test: Cache инвалидируется при изменении файла"""
    test_file = tmp_path / "GUARDRAILS.md"
    test_file.write_text("---\n---\n# Test v1")
    
    loader = GuardrailsLoader(guardrails_path=test_file)
    guardrails1 = loader.load_guardrails()
    
    # Modify file
    import time
    time.sleep(0.1)  # Ensure mtime changes
    test_file.write_text("---\n---\n# Test v2")
    
    guardrails2 = loader.load_guardrails()
    assert guardrails1 != guardrails2
    assert "Test v2" in guardrails2
    print("✅ test_guardrails_loader_invalidates_on_file_change PASSED")


def test_guardrails_loader_handles_missing_file():
    """Test: GuardrailsLoader должен возвращать пустую строку если файл не найден"""
    non_existent = Path("/non/existent/path/GUARDRAILS.md")
    loader = GuardrailsLoader(guardrails_path=non_existent)
    
    guardrails = loader.load_guardrails()
    assert guardrails == ""
    print("✅ test_guardrails_loader_handles_missing_file PASSED")


def test_guardrails_loader_parses_yaml_frontmatter():
    """Test: GuardrailsLoader должен парсить YAML frontmatter"""
    loader = GuardrailsLoader()
    guardrails = loader.load_guardrails()
    
    # Should contain parsed markdown content (not raw frontmatter)
    # Frontmatter should be removed
    assert guardrails.count("---") < 2  # Only in XML tags if any
    print("✅ test_guardrails_loader_parses_yaml_frontmatter PASSED")


if __name__ == "__main__":
    import tempfile
    
    print("=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ GuardrailsLoader")
    print("=" * 70)
    
    # Run tests
    test_guardrails_loader_loads_from_file()
    test_guardrails_loader_caches_in_memory()
    
    # Test with tmp_path
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_guardrails_loader_invalidates_on_file_change(tmp_path)
    
    test_guardrails_loader_handles_missing_file()
    test_guardrails_loader_parses_yaml_frontmatter()
    
    print("=" * 70)
    print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    print("=" * 70)
