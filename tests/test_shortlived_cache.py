"""
Tests для Short-lived cache (formatted skill instructions).
Проверяет что отформатированные skill instructions кешируются с TTL.
"""
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_skill_instructions_cache_exists():
    """Test: Должен существовать класс SkillInstructionsCache"""
    try:
        from src.core.skills.skill_instructions_cache import SkillInstructionsCache
        cache = SkillInstructionsCache(ttl_seconds=300)
        assert hasattr(cache, 'get')
        assert hasattr(cache, 'set')
        assert hasattr(cache, 'invalidate')
        print("✅ test_skill_instructions_cache_exists PASSED")
    except ImportError:
        print("❌ test_skill_instructions_cache_exists FAILED: SkillInstructionsCache not found")
        raise


def test_skill_instructions_cache_get_set():
    """Test: Cache должен сохранять и возвращать значения"""
    from src.core.skills.skill_instructions_cache import SkillInstructionsCache
    
    cache = SkillInstructionsCache(ttl_seconds=300)
    
    # Set
    cache.set("calendar", "<skill_instructions>Calendar skill</skill_instructions>")
    
    # Get
    result = cache.get("calendar")
    assert result == "<skill_instructions>Calendar skill</skill_instructions>"
    
    print("✅ test_skill_instructions_cache_get_set PASSED")


def test_skill_instructions_cache_ttl_expiration():
    """Test: Cache должен удалять значения после истечения TTL"""
    from src.core.skills.skill_instructions_cache import SkillInstructionsCache
    
    cache = SkillInstructionsCache(ttl_seconds=1)  # 1 секунда TTL
    
    # Set
    cache.set("calendar", "test instructions")
    
    # Get immediately - should work
    result = cache.get("calendar")
    assert result == "test instructions"
    
    # Wait for TTL to expire
    time.sleep(1.1)
    
    # Get after expiration - should return None
    result = cache.get("calendar")
    assert result is None
    
    print("✅ test_skill_instructions_cache_ttl_expiration PASSED")


def test_skill_instructions_cache_invalidate():
    """Test: Cache должен удалять значения при invalidate"""
    from src.core.skills.skill_instructions_cache import SkillInstructionsCache
    
    cache = SkillInstructionsCache(ttl_seconds=300)
    
    # Set
    cache.set("calendar", "test instructions")
    
    # Get - should work
    result = cache.get("calendar")
    assert result == "test instructions"
    
    # Invalidate
    cache.invalidate("calendar")
    
    # Get after invalidation - should return None
    result = cache.get("calendar")
    assert result is None
    
    print("✅ test_skill_instructions_cache_invalidate PASSED")


def test_skill_instructions_cache_multiple_skills():
    """Test: Cache должен хранить несколько skills одновременно"""
    from src.core.skills.skill_instructions_cache import SkillInstructionsCache
    
    cache = SkillInstructionsCache(ttl_seconds=300)
    
    cache.set("calendar", "calendar instructions")
    cache.set("gmail", "gmail instructions")
    cache.set("sheets", "sheets instructions")
    
    assert cache.get("calendar") == "calendar instructions"
    assert cache.get("gmail") == "gmail instructions"
    assert cache.get("sheets") == "sheets instructions"
    
    print("✅ test_skill_instructions_cache_multiple_skills PASSED")


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ Short-lived Cache")
    print("=" * 70)
    
    try:
        test_skill_instructions_cache_exists()
        test_skill_instructions_cache_get_set()
        test_skill_instructions_cache_ttl_expiration()
        test_skill_instructions_cache_invalidate()
        test_skill_instructions_cache_multiple_skills()
        
        print("=" * 70)
        print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n❌ ТЕСТ ПРОВАЛЕН: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
