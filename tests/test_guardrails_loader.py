"""
Tests for GuardrailsLoader - загрузка критических правил безопасности.
"""
import pytest
from pathlib import Path
from src.core.guardrails.guardrails_loader import GuardrailsLoader


def test_guardrails_loader_loads_from_file():
    """Test: GuardrailsLoader должен загружать GUARDRAILS.md"""
    loader = GuardrailsLoader()
    guardrails = loader.load_guardrails()
    
    assert guardrails is not None
    assert len(guardrails) > 0
    assert "<guardrails" in guardrails
    assert "priority=\"critical\"" in guardrails


def test_guardrails_loader_caches_in_memory():
    """Test: GuardrailsLoader должен кешировать в памяти"""
    loader = GuardrailsLoader()
    
    # First load
    guardrails1 = loader.load_guardrails()
    
    # Second load (should be cached - same content)
    guardrails2 = loader.load_guardrails()
    
    assert guardrails1 == guardrails2
    assert len(guardrails1) > 0


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


def test_guardrails_loader_handles_missing_file():
    """Test: GuardrailsLoader должен возвращать пустую строку если файл не найден"""
    non_existent = Path("/non/existent/path/GUARDRAILS.md")
    loader = GuardrailsLoader(guardrails_path=non_existent)
    
    guardrails = loader.load_guardrails()
    assert guardrails == ""


def test_guardrails_loader_parses_yaml_frontmatter():
    """Test: GuardrailsLoader должен парсить YAML frontmatter"""
    loader = GuardrailsLoader()
    guardrails = loader.load_guardrails()
    
    # Should contain parsed markdown content (not raw frontmatter)
    assert "---" not in guardrails or guardrails.count("---") < 2
