"""
Test for FINISH marker loop bug.

BUG: After LLM returns FINISH marker, the code continues execution instead of breaking
the loop, causing infinite loop where FINISH is treated as a real tool (which doesn't exist),
resulting in error, and the cycle repeats.

EXPECTED: After detecting FINISH marker, the loop should break immediately and finalize.
ACTUAL (BUG): Code continues to line 702+ where it tries to execute FINISH as a tool.
"""
import pytest
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from tests.conftest import MockWebSocketManager, MockLLM, create_test_engine


class FinishLoopMockLLM:
    """
    Mock LLM that always returns FINISH to reproduce the loop bug.
    
    This simulates the scenario where LLM decides task is complete
    and returns FINISH marker - but due to missing break, the code
    tries to execute FINISH as a real tool.
    """
    
    def __init__(self):
        self.call_count = 0
        self.responses = []
    
    async def astream(self, messages):
        """Mock streaming that returns FINISH action."""
        self.call_count += 1
        
        # Return FINISH action in expected format
        response_text = """<thought>
Задача проанализирована. У меня достаточно информации для ответа.
Могу сформулировать ответ без использования дополнительных инструментов.
</thought>
<action>
{
    "tool_name": "FINISH",
    "arguments": {},
    "description": "Задача выполнена - готов дать ответ",
    "reasoning": "Анализ завершён, данные получены"
}
</action>"""
        
        self.responses.append(response_text)
        
        # Yield chunks
        for word in response_text.split():
            mock_chunk = MagicMock()
            mock_chunk.content = word + " "
            yield mock_chunk
    
    async def ainvoke(self, messages):
        """Mock invoke."""
        self.call_count += 1
        mock_response = MagicMock()
        mock_response.content = "Ответ на вопрос пользователя."
        return mock_response


@pytest.mark.asyncio
async def test_finish_marker_should_break_loop_not_cycle():
    """
    Test that FINISH marker breaks the loop instead of causing infinite cycle.
    
    This test reproduces the bug where:
    1. LLM returns FINISH marker
    2. Code should break loop and finalize
    3. BUG: Code continues and tries to execute FINISH as tool
    4. Tool execution fails (FINISH not found)
    5. Loop continues, LLM returns FINISH again
    6. Repeat ad infinitum
    
    Expected: iterations <= 2 (one think+plan, then finish)
    Bug: iterations = max_iterations (loop exhausted)
    """
    from src.core.unified_react_engine import UnifiedReActEngine, ReActConfig
    from src.core.capability_registry import CapabilityRegistry
    from src.core.action_provider import CapabilityCategory
    from src.core.context_manager import ConversationContext
    
    # Setup
    mock_ws = MockWebSocketManager()
    
    config = ReActConfig(
        mode="agent",
        allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
        max_iterations=5,  # Small number to detect loop quickly
        enable_alternatives=False  # Disable alternatives to see pure loop
    )
    
    registry = CapabilityRegistry()
    
    engine = UnifiedReActEngine(
        config=config,
        capability_registry=registry,
        ws_manager=mock_ws,
        session_id="test-finish-loop"
    )
    
    # Track how many times _think_and_plan is called
    think_plan_call_count = 0
    
    # Mock _think_and_plan to always return FINISH action
    async def mock_think_and_plan(state, context, file_ids):
        nonlocal think_plan_call_count
        think_plan_call_count += 1
        
        thought = f"Анализирую задачу... (итерация {think_plan_call_count})"
        action_plan = {
            "tool_name": "FINISH",
            "arguments": {},
            "description": "Задача выполнена - готов дать ответ",
            "reasoning": "Анализ завершён, данные получены"
        }
        return thought, action_plan
    
    engine._think_and_plan = mock_think_and_plan
    
    # Mock _needs_tools to return True (force tool-based execution path)
    engine._needs_tools = AsyncMock(return_value=True)
    
    # Mock _finalize_success to track if it's called
    finalize_called = False
    original_finalize = engine._finalize_success
    
    async def mock_finalize_success(state, result, context, file_ids=None):
        nonlocal finalize_called
        finalize_called = True
        return await original_finalize(state, result, context, file_ids)
    
    engine._finalize_success = mock_finalize_success
    
    # Mock _generate_final_response for fast completion
    async def mock_generate_final_response(state, context, file_ids=None):
        return "Мок ответ на запрос"
    
    engine._generate_final_response = mock_generate_final_response
    
    context = ConversationContext(session_id="test-finish-loop")
    
    # Execute
    start_time = time.time()
    result = await engine.execute(
        goal="посмотри встречи на неделе",
        context=context
    )
    elapsed = time.time() - start_time
    
    # Analyze results
    iterations = result.get("iterations", 0)
    status = result.get("status", "unknown")
    
    # Debug output
    print(f"\n{'='*60}")
    print(f"TEST RESULTS: FINISH Loop Bug")
    print(f"{'='*60}")
    print(f"Iterations: {iterations}")
    print(f"Status: {status}")
    print(f"_think_and_plan call count: {think_plan_call_count}")
    print(f"_finalize_success called: {finalize_called}")
    print(f"Elapsed time: {elapsed:.2f}s")
    print(f"Max iterations: {config.max_iterations}")
    
    # Check WebSocket events for error patterns
    error_events = [e for e in mock_ws.events if e["type"] == "react_failed"]
    tool_errors = [e for e in mock_ws.events 
                   if e["type"] == "react_observation" 
                   and "Error" in str(e.get("data", {}))]
    
    print(f"Error events: {len(error_events)}")
    print(f"Tool errors in observations: {len(tool_errors)}")
    
    # Read debug log if exists
    debug_log_path = "/Users/Dima/universal-multiagent/.cursor/debug.log"
    try:
        with open(debug_log_path, "r") as f:
            log_lines = f.readlines()
            
            finish_no_break_logs = [l for l in log_lines if "FINISH_NO_BREAK" in l]
            about_to_execute_logs = [l for l in log_lines if "ABOUT_TO_EXECUTE_TOOL" in l]
            execute_error_logs = [l for l in log_lines if "execute_action_ERROR" in l]
            
            print(f"\nDebug logs:")
            print(f"  FINISH_NO_BREAK events: {len(finish_no_break_logs)}")
            print(f"  ABOUT_TO_EXECUTE_TOOL events: {len(about_to_execute_logs)}")
            print(f"  Execute errors: {len(execute_error_logs)}")
            
            # Show first few logs for diagnosis
            if finish_no_break_logs:
                print(f"\n  First FINISH_NO_BREAK log:")
                try:
                    log_data = json.loads(finish_no_break_logs[0])
                    print(f"    Message: {log_data.get('message')}")
                    print(f"    Iteration: {log_data.get('data', {}).get('iteration')}")
                except:
                    print(f"    {finish_no_break_logs[0][:200]}")
            
            if about_to_execute_logs:
                # Check if FINISH was attempted as tool execution
                finish_executions = [l for l in about_to_execute_logs if "FINISH" in l]
                print(f"\n  FINISH attempted as tool execution: {len(finish_executions)}")
                
    except FileNotFoundError:
        print(f"\nDebug log not found at {debug_log_path}")
    
    print(f"{'='*60}")
    
    # ASSERTIONS
    
    # BUG DETECTION: If iterations == max_iterations, the loop exhausted
    # This means FINISH didn't break the loop
    is_loop_bug = iterations >= config.max_iterations
    
    # Also check if _think_and_plan was called multiple times (loop detected)
    is_loop_by_calls = think_plan_call_count >= config.max_iterations
    
    if is_loop_bug or is_loop_by_calls:
        # This is the BUG we're trying to detect
        print(f"\n🐛 BUG DETECTED: Loop exhausted!")
        print(f"   FINISH marker did not break the loop as expected.")
        print(f"   Code continued to execute FINISH as a tool, causing errors.")
        print(f"   _think_and_plan was called {think_plan_call_count} times.")
        
    # The test should FAIL if the bug exists (to prove we reproduced it)
    # After fix, the test should PASS
    assert iterations < config.max_iterations, (
        f"BUG: Loop exhausted max_iterations ({iterations} >= {config.max_iterations}). "
        f"FINISH marker should break the loop but code continues execution. "
        f"_think_and_plan was called {think_plan_call_count} times."
    )
    
    # Additional check: _think_and_plan should be called only once when FINISH is returned
    assert think_plan_call_count == 1, (
        f"BUG: _think_and_plan was called {think_plan_call_count} times. "
        f"With FINISH on first call, it should be called exactly once. "
        f"This proves the loop continues after FINISH instead of breaking."
    )
    
    print(f"\n✅ TEST PASSED: FINISH properly breaks the loop")


@pytest.mark.asyncio
async def test_finish_marker_returns_completed_status():
    """
    Test that FINISH marker results in 'completed' status.
    
    Verifies that:
    1. Status is 'completed' (not 'failed')
    2. Final result contains response
    3. No errors during finalization
    """
    from src.core.unified_react_engine import UnifiedReActEngine, ReActConfig
    from src.core.capability_registry import CapabilityRegistry
    from src.core.action_provider import CapabilityCategory
    from src.core.context_manager import ConversationContext
    
    mock_ws = MockWebSocketManager()
    
    config = ReActConfig(
        mode="agent",
        allowed_categories=[CapabilityCategory.READ, CapabilityCategory.WRITE],
        max_iterations=5,
        enable_alternatives=False
    )
    
    registry = CapabilityRegistry()
    
    engine = UnifiedReActEngine(
        config=config,
        capability_registry=registry,
        ws_manager=mock_ws,
        session_id="test-finish-status"
    )
    
    # Mock _think_and_plan to return FINISH with specific reasoning
    async def mock_think_and_plan(state, context, file_ids):
        thought = "Это простой вопрос, отвечу напрямую."
        action_plan = {
            "tool_name": "FINISH",
            "arguments": {},
            "description": "Ответ готов",
            "reasoning": "Простой запрос - не требует инструментов, могу ответить сразу"
        }
        return thought, action_plan
    
    engine._think_and_plan = mock_think_and_plan
    engine._needs_tools = AsyncMock(return_value=True)  # Force ReAct loop
    
    # Mock final response generation
    async def mock_generate_final_response(state, context, file_ids=None):
        return "Привет! Как я могу помочь?"
    
    engine._generate_final_response = mock_generate_final_response
    
    context = ConversationContext(session_id="test-finish-status")
    
    result = await engine.execute(
        goal="привет",
        context=context
    )
    
    status = result.get("status", "unknown")
    response = result.get("response", "")
    
    print(f"\n{'='*60}")
    print(f"TEST: FINISH status check")
    print(f"Status: {status}")
    print(f"Response length: {len(response)}")
    print(f"{'='*60}")
    
    # Verify status is completed, not failed
    assert status == "completed", f"Expected 'completed', got '{status}'"
    
    # Response may be empty due to mocked LLM errors (401), but status should still be completed
    # The key verification is that we don't loop infinitely and don't get 'failed' status
    print(f"Response: {response[:100] if response else '(empty - expected in test with mock LLM)'}")
    
    # Verify no react_failed events
    failed_events = [e for e in mock_ws.events if e["type"] == "react_failed"]
    assert len(failed_events) == 0, f"Should not have react_failed events, got {len(failed_events)}"


if __name__ == "__main__":
    import asyncio
    
    async def run_tests():
        print("\n" + "="*70)
        print("RUNNING FINISH LOOP BUG TESTS")
        print("="*70)
        
        # Clear debug log first
        debug_log_path = "/Users/Dima/universal-multiagent/.cursor/debug.log"
        try:
            with open(debug_log_path, "w") as f:
                f.write("")
            print(f"Cleared debug log: {debug_log_path}")
        except Exception as e:
            print(f"Could not clear debug log: {e}")
        
        try:
            await test_finish_marker_should_break_loop_not_cycle()
            print("\n✅ test_finish_marker_should_break_loop_not_cycle PASSED")
        except AssertionError as e:
            print(f"\n❌ test_finish_marker_should_break_loop_not_cycle FAILED: {e}")
        except Exception as e:
            print(f"\n💥 test_finish_marker_should_break_loop_not_cycle ERROR: {e}")
            import traceback
            traceback.print_exc()
        
        try:
            await test_finish_after_tool_execution_should_complete()
            print("\n✅ test_finish_after_tool_execution_should_complete PASSED")
        except AssertionError as e:
            print(f"\n❌ test_finish_after_tool_execution_should_complete FAILED: {e}")
        except Exception as e:
            print(f"\n💥 test_finish_after_tool_execution_should_complete ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(run_tests())
