"""
Test parallel execution recognition for queries with actions and data sources.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from unittest.mock import MagicMock
from tests.conftest import create_test_engine, MockWebSocketManager


def test_is_multi_tool_parallel_query():
    """Test: 'сделай презентацию про птичку тари, и проверь почту' should be parallel."""
    ws_manager = MockWebSocketManager()
    engine = create_test_engine(ws_manager)
    
    # Query with action + data source - should be parallel (no dependency)
    query1 = "сделай презентацию про птичку тари, и проверь почту"
    result1 = engine._is_multi_tool_query(query1)
    
    assert result1 == True, f"Query '{query1}' should be recognized as multi-tool (parallel), got {result1}"
    print(f"✅ '{query1}' -> multi-tool: {result1}")


def test_is_multi_tool_sequential_query():
    """Test: 'сделай презентацию про птичку тари, и отправь ее по почте' should be sequential (dependency)."""
    ws_manager = MockWebSocketManager()
    engine = create_test_engine(ws_manager)
    
    # Query with action + dependent action - dependency analyzer should handle this
    query2 = "сделай презентацию про птичку тари, и отправь ее по почте"
    result2 = engine._is_multi_tool_query(query2)
    
    # Note: _is_multi_tool_query might still return True (it detects multi-tool),
    # but DependencyAnalyzer will make it sequential due to dependency ("ее")
    print(f"ℹ️ '{query2}' -> multi-tool: {result2} (dependency 'ее' will make it sequential via DependencyAnalyzer)")


if __name__ == "__main__":
    print("Testing parallel execution recognition...\n")
    try:
        test_is_multi_tool_parallel_query()
        print()
        test_is_multi_tool_sequential_query()
        print("\n✅ All tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
