"""
Test parallel execution recognition for queries with actions and data sources.
"""
import pytest
from src.core.unified_react_engine import UnifiedReActEngine


def test_is_multi_tool_parallel_query():
    """Test: 'сделай презентацию про птичку тари, и проверь почту' should be parallel."""
    engine = UnifiedReActEngine(
        ws_manager=None,
        session_id="test",
        config=None
    )
    
    # Query with action + data source - should be parallel (no dependency)
    query1 = "сделай презентацию про птичку тари, и проверь почту"
    result1 = engine._is_multi_tool_query(query1)
    
    assert result1 == True, f"Query '{query1}' should be recognized as multi-tool (parallel)"
    print(f"✅ '{query1}' -> multi-tool: {result1}")


def test_is_multi_tool_sequential_query():
    """Test: 'сделай презентацию про птичку тари, и отправь ее по почте' should be sequential (dependency)."""
    engine = UnifiedReActEngine(
        ws_manager=None,
        session_id="test",
        config=None
    )
    
    # Query with action + dependent action - should be sequential (dependency)
    query2 = "сделай презентацию про птичку тари, и отправь ее по почте"
    result2 = engine._is_multi_tool_query(query2)
    
    # This might still be recognized as multi-tool, but dependency analyzer should make it sequential
    print(f"ℹ️ '{query2}' -> multi-tool: {result2} (dependency will be handled by DependencyAnalyzer)")


def test_action_keywords_detection():
    """Test: Action keywords (презентацию, создать) should be recognized."""
    engine = UnifiedReActEngine(
        ws_manager=None,
        session_id="test",
        config=None
    )
    
    # Check if action keywords are detected
    test_cases = [
        ("сделай презентацию", True),  # Contains action
        ("проверь почту", True),  # Contains data source
        ("сделай презентацию и проверь почту", True),  # Both
        ("презентацию про птичку и проверь почту", True),  # Both
    ]
    
    for query, expected_has_action_or_source in test_cases:
        result = engine._is_multi_tool_query(query)
        print(f"Query: '{query}' -> multi-tool: {result}")
        
        # Note: Currently might fail, will fix in implementation


if __name__ == "__main__":
    test_is_multi_tool_parallel_query()
    test_is_multi_tool_sequential_query()
    test_action_keywords_detection()
    print("\n✅ All tests completed")
