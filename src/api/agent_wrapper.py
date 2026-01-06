"""
Wrapper for agent execution that emits WebSocket events.
Captures intermediate steps and streams them to frontend.
"""

from typing import Dict, Any, Optional, List
import asyncio
import logging
import json
import time

from src.agents.main_agent import MainAgent
from src.agents.base_agent import StreamEvent
from src.core.context_manager import ConversationContext
from src.core.step_orchestrator import StepOrchestrator
from src.core.react_orchestrator import ReActOrchestrator
from src.core.task_classifier import TaskClassifier, TaskType
from src.api.websocket_manager import get_websocket_manager
from src.utils.audit import get_audit_logger
from src.utils.config_loader import get_config

logger = logging.getLogger(__name__)


class AgentWrapper:
    """
    Wraps agent execution to emit WebSocket events for real-time updates.
    """
    
    def __init__(self):
        """
Initialize agent wrapper."""
        # MainAgent will be created per request with model from context
        self._main_agent_cache: Dict[str, MainAgent] = {}
        self.ws_manager = get_websocket_manager()
        self.audit_logger = get_audit_logger()
        # Store active orchestrators for plan confirmation
        self._active_orchestrators: Dict[str, StepOrchestrator] = {}
        # Task classifier for determining task complexity
        self.task_classifier = TaskClassifier()
        # Store tool arguments for workspace events (key: run_id, value: {tool_name, arguments})
        self._tool_args_cache: Dict[str, Dict[str, Any]] = {}
        # Track sent workspace events to prevent duplicates (key: (session_id, tool_name, spreadsheet_id), value: timestamp)
        self._sent_workspace_events: Dict[str, float] = {}
    
    def get_main_agent(self, model_name: Optional[str] = None) -> MainAgent:
        """
        Get MainAgent instance for a specific model.
        Uses caching to reuse agents with the same model.
        
        Args:
            model_name: Model identifier (optional)
            
        Returns:
            MainAgent instance
        """
        cache_key = model_name or "default"
        if cache_key not in self._main_agent_cache:
            self._main_agent_cache[cache_key] = MainAgent(model_name=model_name)
        return self._main_agent_cache[cache_key]
    
    async def process_message(
        self,
        user_message: str,
        context: ConversationContext,
        session_id: str,
        file_ids: Optional[List[str]] = None,
        open_files: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Process user message through agent and emit events.
        
        Args:
            user_message: User's message
            context: Conversation context
            session_id: Session identifier
            file_ids: Optional list of file IDs to attach to the message
            
        Returns:
            Final execution result
        """
        file_ids = file_ids or []
        open_files = open_files or []
        
        # Store open files in context
        context.set_open_files(open_files)
        
        # Wait for WebSocket connection BEFORE sending any events
        # This ensures events can be sent to the frontend
        import logging
        logger = logging.getLogger(__name__)
        max_wait = 5  # Maximum wait time in seconds
        wait_interval = 0.1  # Check every 100ms
        waited = 0
        logger.info(f"[AgentWrapper] Waiting for WebSocket connection for session {session_id}...")
        while self.ws_manager.get_connection_count(session_id) == 0 and waited < max_wait:
            await asyncio.sleep(wait_interval)
            waited += wait_interval
        
        if self.ws_manager.get_connection_count(session_id) == 0:
            logger.warning(f"[AgentWrapper] No WebSocket connection for session {session_id} after {max_wait}s, proceeding anyway")
        else:
            logger.info(f"[AgentWrapper] WebSocket connected for session {session_id} (connections: {self.ws_manager.get_connection_count(session_id)})")
        
        # Send user message event
        await self.ws_manager.send_event(
            session_id,
            "message",
            {
                "role": "user",
                "content": user_message
            }
        )
        
        # Log user interaction
        self.audit_logger.log_user_interaction(
            "message",
            user_message,
            session_id=session_id
        )
        
        # Add message to context
        context.add_message("user", user_message)
        # Send thinking event
        await self.ws_manager.send_event(
            session_id,
            "thinking",
            {
                "step": "parsing_intent",
                "message": "Analyzing your request..."
            }
        )
        try:
            
            # Classify task complexity
            task_type = await self.task_classifier.classify_task(user_message, context)
            
            
            # Simple tasks always use direct streaming (no plan shown), regardless of mode
            if task_type == TaskType.SIMPLE:
                logger.info(f"[AgentWrapper] Simple task detected, executing directly without workflow")
                result = await self._execute_simple_task(
                    user_message,
                    context,
                    session_id,
                    file_ids
                )
                return result
            
            # Complex tasks use orchestrator (StepOrchestrator or ReActOrchestrator)
            # Check execution mode to determine which orchestrator to use
            use_react = context.execution_mode == "react"
            
            if use_react:
                logger.info(f"[AgentWrapper] Complex task detected, using ReActOrchestrator")
                
                
                # Create ReActOrchestrator
                react_orchestrator = ReActOrchestrator(
                    ws_manager=self.ws_manager,
                    session_id=session_id,
                    model_name=context.model_name
                )
                
                
                # Store orchestrator for stop handling
                self._active_orchestrators[session_id] = react_orchestrator
                
                
                # Execute ReAct orchestrator
                result = await react_orchestrator.execute(
                    user_request=user_message,
                    context=context,
                    file_ids=file_ids
                )
                
            else:
                logger.info(f"[AgentWrapper] Complex task detected, using StepOrchestrator")
                
                # Check if there's an existing orchestrator for this session
                # If previous request is completed, we can reuse the orchestrator
                # Otherwise, stop it to prevent mixing context
                if session_id in self._active_orchestrators:
                    old_orchestrator = self._active_orchestrators[session_id]
                    # Check if previous orchestrator is still running
                    is_running = (
                        hasattr(old_orchestrator, '_streaming_task') and 
                        old_orchestrator._streaming_task and 
                        not old_orchestrator._streaming_task.done()
                    ) or (
                        hasattr(old_orchestrator, '_confirmation_event') and
                        old_orchestrator._confirmation_event and
                        not old_orchestrator._confirmation_event.is_set()
                    )
                    
                    if is_running:
                        # Previous request is still running - stop it
                        logger.info(f"[AgentWrapper] Stopping active orchestrator for session {session_id}")
                        old_orchestrator.stop()
                        del self._active_orchestrators[session_id]
                    else:
                        # Previous request is completed - reuse orchestrator
                        logger.info(f"[AgentWrapper] Reusing orchestrator for session {session_id}")
                        # Clean up state for new request
                        old_orchestrator._confirmation_event = None
                        old_orchestrator._confirmation_result = None
                        old_orchestrator._stop_requested = False
                        old_orchestrator._streaming_task = None
                        # Use existing orchestrator instead of creating new one
                        orchestrator = old_orchestrator
                
                if context.execution_mode == "approval":
                    orchestrator_mode = "plan_and_confirm"
                else:
                    orchestrator_mode = "plan_and_execute"
                
                # Create StepOrchestrator for this session (only if not reusing existing)
                if 'orchestrator' not in locals():
                    orchestrator = StepOrchestrator(
                        ws_manager=self.ws_manager,
                        session_id=session_id,
                        model_name=context.model_name
                    )
                    # Store orchestrator for confirmation handling
                    self._active_orchestrators[session_id] = orchestrator
                
                # Execute orchestrator
                # For plan_and_confirm: this will generate plan, wait for confirmation, then execute steps
                # For plan_and_execute: this will generate plan and execute immediately
                result = await orchestrator.execute(
                    user_request=user_message,
                    mode=orchestrator_mode,
                    context=context,
                    file_ids=file_ids
                )
            
            # Log the action
            orchestrator_type = "ReActOrchestrator" if use_react else "StepOrchestrator"
            execution_mode_str = "react" if use_react else (orchestrator_mode if 'orchestrator_mode' in locals() else "plan_and_execute")
            self.audit_logger.log_agent_action(
                orchestrator_type,
                "execute",
                {"message": user_message, "mode": execution_mode_str, "result": result.get("status", "unknown")},
                session_id=session_id
            )
            
            # Clean up orchestrator after execution is complete
            if result.get("status") in ("completed", "rejected", "timeout"):
                if session_id in self._active_orchestrators:
                    del self._active_orchestrators[session_id]
            
            return result
            
        except Exception as e:
            
            # Extract detailed error message
            import traceback
            error_message = str(e)
            if not error_message or error_message.strip() == "":
                # Try to get message from exception attributes
                if hasattr(e, 'message'):
                    error_message = str(e.message)
                elif hasattr(e, 'args') and len(e.args) > 0:
                    error_message = str(e.args[0])
                else:
                    error_message = "Произошла ошибка: {type}".format(type=type(e).__name__)

            # Keep traceback in standard logs (no NDJSON debug instrumentation)
            error_traceback = traceback.format_exc()
            logger.error(f"[AgentWrapper] Error processing message:\n{error_traceback}")
            
            # Escape braces in error message to avoid f-string syntax errors
            def _escape_braces(text: str) -> str:
                return text.replace("{", "{{").replace("}", "}}")
            escaped_error_message = _escape_braces(error_message)
            
            # Check for API credit balance error (Anthropic API)
            error_lower = error_message.lower()
            is_credit_error = (
                "credit balance" in error_lower or
                "balance is too low" in error_lower or
                "insufficient credits" in error_lower or
                "недостаточно средств" in error_lower
            )
            
            # Create user-friendly message
            if is_credit_error:
                friendly_error_message = "⚠️ Недостаточно средств на балансе API ключа Anthropic. Пожалуйста, пополните баланс в разделе Plans & Billing на сайте Anthropic."
            else:
                friendly_error_message = error_message
            
            # Send error event
            await self.ws_manager.send_event(
                session_id,
                "error",
                {
                    "message": friendly_error_message,  # Send friendly message
                    "type": type(e).__name__
                }
            )
            
            # Also send as system message for better visibility
            await self.ws_manager.send_event(
                session_id,
                "message",
                {
                    "role": "system",
                    "content": friendly_error_message  # Use friendly message directly
                }
            )
            
            raise
    
    async def _execute_with_streaming(
        self,
        user_message: str,
        context: ConversationContext,
        session_id: str,
        stream_to_final_result: bool = False
    ) -> Dict[str, Any]:
        """
        Execute agent with real-time streaming of tokens and events.
        
        Args:
            user_message: User's message
            context: Conversation context
            session_id: Session identifier
            stream_to_final_result: If True, stream tokens directly to final_result events instead of message_chunk
            
        Returns:
            Execution result
        """
        # Log before execution
        self.audit_logger.log_agent_action(
            "AgentWrapper",
            "execute_with_streaming",
            {"message": user_message, "session_id": session_id},
            session_id=session_id
        )
        
        session_id_val = getattr(context, 'session_id', 'NOT SET')
        logger.info(f"[AgentWrapper] Starting streaming execution, context.session_id: {session_id_val}, stream_to_final_result={stream_to_final_result}")
        try:
            # Execute agent with real-time event streaming
            # Events are sent directly to WebSocket via callback in _execute_with_event_streaming
            result = await self._execute_with_event_streaming(
                user_message,
                context,
                session_id,
                stream_to_final_result=stream_to_final_result
            )
            logger.info(f"[AgentWrapper] Streaming execution SUCCESS")
            
            # Add agent response to context
            context.add_message("assistant", result.get("response", ""))
            return result
            
        except Exception as e:
            logger.error(f"[AgentWrapper] Streaming execution FAILED: {e}")
            
            # Extract detailed error message
            error_message = str(e)
            if not error_message or error_message.strip() == "":
                if hasattr(e, 'message'):
                    error_message = str(e.message)
                elif hasattr(e, 'args') and len(e.args) > 0:
                    error_message = str(e.args[0])
                else:
                    error_message = f"Произошла ошибка: {type(e).__name__}"
            
            # Escape braces in error message to avoid f-string syntax errors
            def _escape_braces(text: str) -> str:
                return text.replace("{", "{{").replace("}", "}}")
            escaped_error_message = _escape_braces(error_message)
            
            # Import exception types
            from src.utils.exceptions import ToolExecutionError, MCPError
            
            # Check for API credit balance error (Anthropic API)
            error_lower = error_message.lower()
            is_credit_error = (
                "credit balance" in error_lower or
                "balance is too low" in error_lower or
                "insufficient credits" in error_lower or
                "недостаточно средств" in error_lower
            )
            
            # Create user-friendly error message using .format() instead of f-string to avoid issues with escaped content
            if is_credit_error:
                friendly_message = "⚠️ Недостаточно средств на балансе API ключа Anthropic. Пожалуйста, пополните баланс в разделе Plans & Billing на сайте Anthropic."
            elif isinstance(e, ToolExecutionError):
                friendly_message = "Не удалось выполнить операцию: {error}".format(error=escaped_error_message)
            elif isinstance(e, MCPError):
                friendly_message = "Ошибка подключения к сервису: {error}".format(error=escaped_error_message)
            else:
                friendly_message = "Ошибка: {error}".format(error=escaped_error_message)
            
            # Error events are already sent from base_agent and stream_event_callback
            # But if error occurs before execute_with_streaming is called, we need to send message_complete here
            
            # Send system message with error (already escaped in friendly_message)
            await self.ws_manager.send_event(
                session_id,
                "message",
                {
                    "role": "system",
                    "content": friendly_message
                }
            )
            
            # Send message_complete to ensure frontend knows streaming is done
            # Use the message_id from the streaming session if available
            try:
                message_id = getattr(self, '_current_streaming_message_id', None)
                if not message_id:
                    import asyncio
                    message_id = f"stream_{session_id}_{asyncio.get_event_loop().time()}"
                
                logger.info(f"[AgentWrapper] Sending message_complete after exception in _execute_with_streaming, message_id: {message_id}")
                await self.ws_manager.send_event(
                    session_id,
                    "message_complete",
                    {
                        "role": "assistant",
                        "message_id": message_id,
                        "content": ""
                    }
                )
            except Exception as send_error:
                logger.error(f"[AgentWrapper] Failed to send message_complete after error: {send_error}")
            finally:
                # Clean up
                if hasattr(self, '_current_streaming_message_id'):
                    delattr(self, '_current_streaming_message_id')
            
            raise Exception(friendly_message) from e
    
    async def _execute_simple_task(
        self,
        user_message: str,
        context: ConversationContext,
        session_id: str,
        file_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute simple task directly without workflow/planning.
        
        Args:
            user_message: User's message
            context: Conversation context
            session_id: Session identifier
            file_ids: Optional list of file IDs to attach
            
        Returns:
            Execution result
        """
        file_ids = file_ids or []
        logger.info(f"[AgentWrapper] Executing simple task: {user_message[:50]}")
        
        # Check if context is needed for simple task (NEW)
        needs_context = self._needs_context_for_simple(user_message, context)
        if needs_context:
            logger.info(f"[AgentWrapper] Adding minimal context for simple task")
        
        # Use direct streaming execution (no workflow) - stream directly to final_result
        # Context will be automatically included via base_agent.execute which uses get_context_for_simple_task
        result = await self._execute_with_streaming(
            user_message,
            context,
            session_id,
            stream_to_final_result=True
        )
        
        # Log the action
        self.audit_logger.log_agent_action(
            "AgentWrapper",
            "execute_simple_task",
            {"message": user_message, "result": "completed"},
            session_id=session_id
        )
        return {
            "status": "completed",
            "response": result.get("response", ""),
            "type": "simple_execution"
        }
    
    def _needs_context_for_simple(
        self,
        user_message: str,
        context: ConversationContext
    ) -> bool:
        """
        Check if context is needed for simple task.
        
        Args:
            user_message: User's message
            context: Conversation context
            
        Returns:
            True if context is needed, False otherwise
        """
        # Check for reference keywords
        reference_keywords = ["этот", "тот", "его", "её", "там", "this", "that"]
        for keyword in reference_keywords:
            if keyword in user_message.lower():
                return True
        
        # Check if there are recent messages
        if len(context.messages) > 0:
            return True
        
        return False
    
    async def _generate_simple_task_result(
        self,
        user_request: str,
        response: str,
        context: ConversationContext
    ) -> str:
        """
        Generate final result summary for simple task.
        
        Args:
            user_request: Original user request
            response: Agent response
            context: Conversation context
            
        Returns:
            Final result text
        """
        from langchain_core.messages import SystemMessage, HumanMessage
        from src.agents.model_factory import create_llm
        
        system_prompt = """Ты эксперт по созданию финальных ответов пользователям. Создай прямой и информативный ответ на исходный запрос пользователя.

⚠️ ВАЖНО: ВСЕ ответы должны быть на РУССКОМ языке! ⚠️

Твоя задача:
1. Проанализировать исходный запрос пользователя
2. Использовать предоставленные данные как контекст для формирования ответа
3. Создать понятный финальный ответ, который напрямую отвечает на запрос пользователя
4. НЕ упоминай процесс выполнения, попытки, инструменты или технические детали
5. НЕ создавай отчет о выполнении - создай именно ответ на запрос

Формат ответа:
- Используй Markdown для форматирования (жирный текст **текст**, списки, эмодзи и т.д.)
- Прямой ответ на запрос пользователя
- Ключевая информация, которая была запрошена
- Если нужно, структурируй информацию для удобства чтения (используй списки, заголовки, выделение)

Будь конкретным, информативным и отвечай именно на то, что спросил пользователь."""

        # Escape braces in user_request and response to avoid f-string syntax errors
        def _escape_braces_for_fstring(text: str) -> str:
            """
Escape curly braces in text to safely use in f-strings."""
            return text.replace("{", "{{").replace("}", "}}")
        
        escaped_user_request = _escape_braces_for_fstring(user_request)
        escaped_response = _escape_braces_for_fstring(response) if response else ""
        # Use .format() instead of f-string to avoid issues with escaped content containing {...}
        user_prompt = """Исходный запрос пользователя: {user_request}

Данные, полученные в результате выполнения запроса:
{response}

Создай финальный ответ пользователю, который напрямую отвечает на его запрос. Используй предоставленные данные для формирования ответа. НЕ упоминай процесс выполнения или технические детали - просто ответь на запрос.""".format(
            user_request=escaped_user_request,
            response=escaped_response
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            # Use fast model for result generation
            llm = create_llm("claude-3-haiku")
            llm_response = await llm.ainvoke(messages)
            final_result = llm_response.content.strip()
            logger.info(f"[AgentWrapper] Generated final result for simple task, length: {len(final_result)}")
            return final_result
        except Exception as e:
            logger.error(f"[AgentWrapper] Error generating final result: {e}")
            # Fallback: return the response directly as final answer (without "Исходный запрос" header)
            if response and response.strip():
                escaped_response = _escape_braces_for_fstring(response[:1000] if len(response) > 1000 else response)
                response_suffix = "..." if len(response) > 1000 else ""
                return escaped_response + response_suffix
            else:
                return "Запрос выполнен."
    
    async def _execute_with_event_streaming(
        self,
        user_message: str,
        context: ConversationContext,
        session_id: str,
        stream_to_final_result: bool = False
    ) -> Dict[str, Any]:
        """
        Execute agent with real-time event streaming.
        
        Uses astream_events to get real-time tokens, tool calls, and results
        from the LLM and sends them to the frontend via WebSocket.
        
        Args:
            user_message: User's message
            context: Conversation context
            session_id: Session identifier
            stream_to_final_result: If True, stream tokens directly to final_result events instead of message_chunk
            
        Returns:
            Execution result
        """
        logger.info(f"[AgentWrapper] Starting real-time streaming for session {session_id}, stream_to_final_result={stream_to_final_result}")
        
        # Generate unique message ID for this streaming response
        message_id = f"stream_{session_id}_{asyncio.get_event_loop().time()}"
        
        # Store message_id so exception handler can access it
        self._current_streaming_message_id = message_id
        
        # Track if we've sent message_start or final_result_start
        message_started = False
        final_result_started = False
        accumulated_tokens = ""
        accumulated_thinking = ""
        
        async def stream_event_callback(event_type: str, data: Dict[str, Any]):
            """
Callback to handle streaming events and send to WebSocket."""
            nonlocal message_started, accumulated_tokens, message_id, final_result_started, accumulated_thinking
            
            logger.debug(f"[AgentWrapper] Stream event: {event_type}, data keys: {list(data.keys())}")
            
            # For Cursor-like behavior: always send thinking events to show full process
            if event_type == StreamEvent.THINKING:
                thinking_message = data.get("message", data.get("step", "Обрабатываю..."))
                accumulated_thinking = thinking_message
                
                if stream_to_final_result:
                    # In final_result mode, send thinking as a separate event for logging
                    # Frontend can optionally display this in a collapsible section
                    await self.ws_manager.send_event(
                        session_id,
                        "thinking",
                        {
                            "step": data.get("step", "reasoning"),
                            "message": thinking_message,
                            "mode": "simple_task"  # Mark as simple task thinking
                        }
                    )
                else:
                    # Normal mode: send thinking/reasoning step
                    await self.ws_manager.send_event(
                        session_id,
                        "thinking",
                        {
                            "step": data.get("step", "reasoning"),
                            "message": thinking_message
                        }
                    )
            
            elif event_type == StreamEvent.TOKEN:
                # Send streaming token
                token = data.get("token", "")
                accumulated_tokens = data.get("accumulated", accumulated_tokens + token)
                
                if stream_to_final_result:
                    # Stream directly to final_result block
                    if not final_result_started:
                        await self.ws_manager.send_event(
                            session_id,
                            "final_result_start",
                            {}
                        )
                        final_result_started = True
                    
                    # Send as final_result_chunk (with accumulated content)
                    await self.ws_manager.send_event(
                        session_id,
                        "final_result_chunk",
                        {
                            "content": accumulated_tokens
                        }
                    )
                else:
                    # Normal mode: stream to message_chunk
                    # Start message if not started
                    if not message_started:
                        await self.ws_manager.send_event(
                            session_id,
                            "message_start",
                            {
                                "role": "assistant",
                                "message_id": message_id,
                                "content": ""
                            }
                        )
                        message_started = True
                    
                    # Send token chunk
                    await self.ws_manager.send_event(
                        session_id,
                        "message_chunk",
                        {
                            "role": "assistant",
                            "message_id": message_id,
                            "chunk": token,
                            "content": accumulated_tokens
                        }
                    )
            
            elif event_type == StreamEvent.TOOL_CALL:
                # Send tool call event
                tool_name = data.get("tool_name", "unknown")
                tool_args_raw = data.get("arguments", "")
                run_id = data.get("run_id", "")
                
                # Parse arguments from JSON string if needed
                tool_args = {}
                if isinstance(tool_args_raw, str):
                    try:
                        import json
                        tool_args = json.loads(tool_args_raw)
                    except:
                        # If not JSON, treat as plain string
                        tool_args = {"input": tool_args_raw}
                elif isinstance(tool_args_raw, dict):
                    tool_args = tool_args_raw
                
                # Cache tool arguments for use in TOOL_RESULT (use run_id as key)
                if run_id:
                    self._tool_args_cache[run_id] = {
                        "tool_name": tool_name,
                        "arguments": tool_args
                    }
                
                await self.ws_manager.send_event(
                    session_id,
                    "tool_call",
                    {
                        "tool_name": tool_name,
                        "arguments": tool_args,
                        "status": data.get("status", "calling")
                    }
                )
                
                # Send email preview event when preparing to send email
                if tool_name == "send_email":
                    try:
                        await self.ws_manager.send_event(
                            session_id,
                            "email_preview",
                            {
                                "to": tool_args.get("to", ""),
                                "subject": tool_args.get("subject", ""),
                                "body": tool_args.get("body", ""),
                                "cc": tool_args.get("cc"),
                                "bcc": tool_args.get("bcc"),
                                "attachments": []
                            }
                        )
                        logger.info(f"[AgentWrapper] Sent email_preview event for email to {tool_args.get('to')}")
                    except Exception as e:
                        logger.warning(f"[AgentWrapper] Failed to send email_preview event: {e}")
                
                # Also send as thinking step for visibility (skip if streaming to final_result)
                if not stream_to_final_result:
                    await self.ws_manager.send_event(
                        session_id,
                        "thinking",
                        {
                            "step": "tool_call",
                            "message": f"Вызываю: {tool_name}"
                        }
                    )
            
            elif event_type == StreamEvent.TOOL_RESULT:
                # Send tool result event with compact formatting
                result = data.get("result", "")
                run_id = data.get("run_id", "")
                
                # Get cached tool name and arguments using run_id
                cached_data = self._tool_args_cache.pop(run_id, {}) if run_id else {}
                tool_name = cached_data.get("tool_name", "unknown")
                tool_args = cached_data.get("arguments", {})
                
                
                # Make result more compact if it's too long
                if len(result) > 2000:
                    result = result[:2000] + "\n\n... (результат обрезан, показаны первые 2000 символов) ..."
                
                await self.ws_manager.send_event(
                    session_id,
                    "tool_result",
                    {
                        "tool_name": tool_name,
                        "result": result
                    }
                )
                
                # Send workspace panel events based on tool results
                try:
                    
                    logger.info(f"[AgentWrapper] Calling _handle_workspace_events for tool: {tool_name}")
                    await self._handle_workspace_events(session_id, tool_name, result, tool_args)
                    logger.info(f"[AgentWrapper] _handle_workspace_events completed for tool: {tool_name}")
                    
                except Exception as e:
                    logger.error(f"[AgentWrapper] Failed to handle workspace events: {e}", exc_info=True)
            
            elif event_type == StreamEvent.DONE:
                # Complete the streaming message
                response = data.get("response", accumulated_tokens)
                logger.info(f"[AgentWrapper] DONE event received, response length: {len(response)}, message_started: {message_started}, final_result_started: {final_result_started}")
                
                if stream_to_final_result:
                    # Stream to final_result mode: send final_result_complete
                    if final_result_started:
                        logger.info(f"[AgentWrapper] Sending final_result_complete event")
                        await self.ws_manager.send_event(
                            session_id,
                            "final_result_complete",
                            {
                                "content": response
                            }
                        )
                    else:
                        # If no tokens were streamed, still send final_result with content
                        logger.info(f"[AgentWrapper] Sending final_result event (no streaming)")
                        await self.ws_manager.send_event(
                            session_id,
                            "final_result",
                            {
                                "content": response if response else "Запрос выполнен."
                            }
                        )
                else:
                    # Normal mode: send message_complete
                    # Always send response, even if empty or no tokens were streamed
                    if message_started:
                        logger.info(f"[AgentWrapper] Sending message_complete event")
                        await self.ws_manager.send_event(
                            session_id,
                            "message_complete",
                            {
                                "role": "assistant",
                                "message_id": message_id,
                                "content": response
                            }
                        )
                    else:
                        # If no tokens were streamed, send as regular message
                        logger.info(f"[AgentWrapper] Sending regular message (no streaming)")
                        await self.ws_manager.send_event(
                            session_id,
                            "message",
                            {
                                "role": "assistant",
                                "content": response if response else "Извините, не удалось получить ответ."
                            }
                        )
            
            elif event_type == StreamEvent.ERROR:
                # Send error
                error_msg = data.get("error", "Unknown error")
                await self.ws_manager.send_event(
                    session_id,
                    "error",
                    {
                        "message": error_msg
                    }
                )# Always send completion event after error to signal end of streaming
                # This ensures the frontend knows streaming is done even after error
                if stream_to_final_result:
                    if final_result_started:
                        logger.info(f"[AgentWrapper] Sending final_result_complete after error")
                        await self.ws_manager.send_event(
                            session_id,
                            "final_result_complete",
                            {
                                "content": accumulated_tokens if accumulated_tokens else ""
                            }
                        )
                else:
                    logger.info(f"[AgentWrapper] Sending message_complete after error, message_id: {message_id}, message_started: {message_started}")
                    await self.ws_manager.send_event(
                        session_id,
                        "message_complete",
                        {
                            "role": "assistant",
                            "message_id": message_id,
                            "content": accumulated_tokens if accumulated_tokens else ""
                        }
                    )
        
        # Execute with streaming
        logger.info(f"[AgentWrapper] Calling main_agent.execute_with_streaming")
        # Get MainAgent instance with model from context
        main_agent = self.get_main_agent(context.model_name)
        try:
            result = await main_agent.execute_with_streaming(
                user_message,
                context,
                event_callback=stream_event_callback
            )
            logger.info(f"[AgentWrapper] Streaming execution complete, response length: {len(result.get('response', ''))}")
        finally:
            # Clean up message_id after streaming is done
            if hasattr(self, '_current_streaming_message_id'):
                delattr(self, '_current_streaming_message_id')
        return result
    
    async def _stream_message(
        self,
        session_id: str,
        full_text: str,
        chunk_size: int = 5
    ) -> None:
        """
        Stream message text in chunks to create typing effect.
        
        Args:
            session_id: Session identifier
            full_text: Full message text to stream
            chunk_size: Number of characters per chunk
        """
        import logging
        logger = logging.getLogger(__name__)
        try:
            message_id = f"stream_{asyncio.get_event_loop().time()}"
            logger.error(f"[AgentWrapper] Starting to stream message, length: {len(full_text)}, session: {session_id}")
            
            # Send message start event
            await self.ws_manager.send_event(
                session_id,
                "message_start",
                {
                    "role": "assistant",
                    "message_id": message_id,
                    "content": ""
                }
            )
            logger.error(f"[AgentWrapper] Sent message_start event")
            
            # Stream text in chunks
            accumulated = ""
            chunk_count = 0
            for i in range(0, len(full_text), chunk_size):
                chunk = full_text[i:i + chunk_size]
                accumulated += chunk
                chunk_count += 1
                
                await self.ws_manager.send_event(
                    session_id,
                    "message_chunk",
                    {
                        "role": "assistant",
                        "message_id": message_id,
                        "chunk": chunk,
                        "content": accumulated
                    }
                )
                
                # Small delay to create smooth streaming effect
                await asyncio.sleep(0.03)  # ~30ms delay per chunk
            
            logger.error(f"[AgentWrapper] Sent {chunk_count} chunks")
            
            # Send completion event
            await self.ws_manager.send_event(
                session_id,
                "message_complete",
                {
                    "role": "assistant",
                    "message_id": message_id,
                    "content": full_text
                }
            )
            logger.error(f"[AgentWrapper] Sent message_complete event")
        except Exception as e:
            logger.error(f"[AgentWrapper] Error in _stream_message: {e}")
            import traceback
            logger.error(f"[AgentWrapper] Traceback: {traceback.format_exc()}")
            # Fallback: send message normally
            await self.ws_manager.send_event(
                session_id,
                "message",
                {
                    "role": "assistant",
                    "content": full_text
                }
            )
    
    async def approve_plan(
        self,
        confirmation_id: str,
        context: ConversationContext,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Execute an approved plan using StepOrchestrator.
        
        Args:
            confirmation_id: Confirmation ID
            context: Conversation context
            session_id: Session identifier
            
        Returns:
            Execution result
        """
        # Get active orchestrator for this session
        orchestrator = self._active_orchestrators.get(session_id)
        if orchestrator:
            # Verify confirmation_id matches
            if orchestrator.get_confirmation_id() != confirmation_id:
                logger.warning(f"[AgentWrapper] Confirmation ID mismatch: expected {orchestrator.get_confirmation_id()}, got {confirmation_id}")
            
            # Confirm the plan in orchestrator
            # This will unblock the execute() method that is waiting for confirmation
            orchestrator.confirm_plan()
            # The orchestrator.execute() method is already running (was called from process_message)
            # and is waiting for confirmation. Now that we've confirmed, it will continue execution.
            # We return immediately - the execution continues in the background
            return {
                "status": "approved",
                "message": "Plan approved, execution started"
            }
        else:
            # Fallback to old logic if orchestrator not found
            logger.warning(f"[AgentWrapper] No active orchestrator for session {session_id}, using fallback")
            await self.ws_manager.send_event(
                session_id,
                "thinking",
                {
                    "step": "executing_plan",
                    "message": "Executing approved plan..."
                }
            )
            
            # Get MainAgent instance with model from context
            main_agent = self.get_main_agent(context.model_name)
            
            # Try to execute approved plan (if MainAgent supports it)
            try:
                if hasattr(main_agent, 'execute_approved_plan'):
                    result = await main_agent.execute_approved_plan(
                        confirmation_id,
                        context
                    )
                else:
                    result = {"status": "not_supported"}
            except Exception as e:
                logger.error(f"[AgentWrapper] Error executing approved plan: {e}")
                result = {"status": "error", "message": str(e)}
            
            await self.ws_manager.send_event(
                session_id,
                "message",
                {
                    "role": "assistant",
                    "content": "Plan executed successfully"
                }
            )
            return result
    
    async def reject_plan(
        self,
        confirmation_id: str,
        context: ConversationContext,
        session_id: str
    ) -> None:
        """
        Reject a plan using StepOrchestrator.
        
        Args:
            confirmation_id: Confirmation ID
            context: Conversation context
            session_id: Session identifier
        """
        # Get active orchestrator for this session
        orchestrator = self._active_orchestrators.get(session_id)
        if orchestrator:
            # Verify confirmation_id matches
            if orchestrator.get_confirmation_id() != confirmation_id:
                logger.warning(f"[AgentWrapper] Confirmation ID mismatch: expected {orchestrator.get_confirmation_id()}, got {confirmation_id}")
            
            # Reject the plan in orchestrator
            # This will unblock the execute() method that is waiting for confirmation
            orchestrator.reject_plan()
            
            # Clean up orchestrator after rejection
            # The execute() method will return with status="rejected"
            if session_id in self._active_orchestrators:
                del self._active_orchestrators[session_id]
        else:
            # Fallback to old logic
            logger.warning(f"[AgentWrapper] No active orchestrator for session {session_id}, using fallback")
            context.resolve_confirmation(confirmation_id, approved=False)
            
            await self.ws_manager.send_event(
                session_id,
                "message",
                {
                    "role": "assistant",
                    "content": "Plan rejected. How would you like to proceed?"
                }
            )
    
    async def resolve_user_assistance(
        self,
        assistance_id: str,
        user_response: str,
        context: ConversationContext,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Resolve a user assistance request with user's selection.
        
        Args:
            assistance_id: Assistance request ID
            user_response: User's response (number, ordinal, label, etc.)
            context: Conversation context
            session_id: Session identifier
            
        Returns:
            Status dict
        """
        
        # Get active orchestrator for this session
        orchestrator = self._active_orchestrators.get(session_id)
        
        
        if orchestrator:
            # Verify assistance_id matches
            expected_id = orchestrator.get_user_assistance_id()
            
            
            if expected_id != assistance_id:
                logger.warning(f"[AgentWrapper] Assistance ID mismatch: expected {expected_id}, got {assistance_id}")
                return {"status": "error", "message": "Assistance ID mismatch"}
            
            # Resolve the assistance request in orchestrator
            # This will unblock the _execute_step method that is waiting for assistance
            
            
            orchestrator.resolve_user_assistance(assistance_id, user_response)
            
            
            # The orchestrator.execute() method is already running and waiting for assistance.
            # Now that we've resolved it, execution will continue.
            return {
                "status": "resolved",
                "message": "User assistance resolved, execution continuing"
            }
        else:
            logger.warning(f"[AgentWrapper] No active orchestrator for session {session_id}")
            return {
                "status": "error",
                "message": "No active orchestrator found"
            }
    
    async def stop_generation(self, session_id: str) -> None:
        """
        Stop generation for a session.
        
        Args:
            session_id: Session identifier
        """
        # Get active orchestrator for this session
        orchestrator = self._active_orchestrators.get(session_id)
        if orchestrator:
            logger.info(f"[AgentWrapper] Stopping generation for session {session_id}")
            orchestrator.stop()
            
            # Send stop event to client
            await self.ws_manager.send_event(
                session_id,
                "workflow_stopped",
                {
                    "reason": "Остановлено пользователем"
                }
            )
        else:
            logger.warning(f"[AgentWrapper] No active orchestrator for session {session_id}")
    
    def get_orchestrator(self, session_id: str) -> Optional[StepOrchestrator]:
        """
        Get active orchestrator for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            StepOrchestrator instance or None
        """
        return self._active_orchestrators.get(session_id)
    
    async def _handle_workspace_events(
        self,
        session_id: str,
        tool_name: str,
        result: str,
        tool_args: Dict[str, Any]
    ) -> None:
        """
        Handle workspace panel events based on tool execution results.
        
        Args:
            session_id: Session identifier
            tool_name: Name of the executed tool
            result: Tool execution result
            tool_args: Tool arguments
        """
        import re
        # Handle create_spreadsheet
        if tool_name == "create_spreadsheet":
            logger.info(f"[AgentWrapper] Processing create_spreadsheet, result length: {len(result)}, result preview: {result[:200]}")
            # Extract spreadsheet ID and URL from result
            # Result format: "Spreadsheet 'title' created successfully. ID: {id}. URL: {url}"
            spreadsheet_id_match = re.search(r'ID:\s*([a-zA-Z0-9_-]+)', result)
            url_match = re.search(r'URL:\s*(https?://[^\s]+)', result)
            title_match = re.search(r"Spreadsheet\s+'([^']+)'", result)
            
            logger.info(f"[AgentWrapper] Regex matches - ID: {bool(spreadsheet_id_match)}, URL: {bool(url_match)}, Title: {bool(title_match)}")
            
            if spreadsheet_id_match:
                spreadsheet_id = spreadsheet_id_match.group(1)
                
                # Check if we already sent event for this spreadsheet_id (prevent duplicates)
                event_key = f"{session_id}:create_spreadsheet:{spreadsheet_id}"
                current_time = time.time()
                
                
                if event_key in self._sent_workspace_events:
                    last_sent = self._sent_workspace_events[event_key]
                    # Only skip if sent within last 5 seconds (to allow retries after longer delays)
                    if current_time - last_sent < 5:
                        logger.info(f"[AgentWrapper] Skipping duplicate sheets_action event for spreadsheet {spreadsheet_id} (sent {current_time - last_sent:.2f}s ago)")
                        return
                
                url = url_match.group(1) if url_match else f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
                title = title_match.group(1) if title_match else tool_args.get("title", "Google Sheets")
                
                event_data = {
                    "action": "create",
                    "spreadsheet_id": spreadsheet_id,
                    "spreadsheet_url": url,
                    "title": title,
                    "range": None,
                    "description": f"Создана таблица '{title}'"
                }
                
                logger.info(f"[AgentWrapper] Sending sheets_action event: {event_data}")
                
                
                await self.ws_manager.send_event(
                    session_id,
                    "sheets_action",
                    event_data
                )
                # Mark as sent
                self._sent_workspace_events[event_key] = current_time
                
                
                logger.info(f"[AgentWrapper] Sent sheets_action event for created spreadsheet {spreadsheet_id}")
            else:
                logger.warning(f"[AgentWrapper] Failed to extract spreadsheet_id from result: {result[:500]}")
        
        # Handle create_document
        elif tool_name == "create_document":
            # Extract document ID and URL from result
            # Result format: "Document 'title' created successfully. ID: {id}. URL: {url}"
            doc_id_match = re.search(r'ID:\s*([a-zA-Z0-9_-]+)', result)
            url_match = re.search(r'URL:\s*(https?://[^\s]+)', result)
            title_match = re.search(r"Document\s+'([^']+)'", result)
            
            if doc_id_match:
                document_id = doc_id_match.group(1)
                url = url_match.group(1) if url_match else f"https://docs.google.com/document/d/{document_id}/edit"
                title = title_match.group(1) if title_match else tool_args.get("title", "Google Docs")
                
                await self.ws_manager.send_event(
                    session_id,
                    "docs_action",
                    {
                        "document_id": document_id,
                        "document_url": url,
                        "title": title
                    }
                )
                logger.info(f"[AgentWrapper] Sent docs_action event for document {document_id}")
        
        # Handle slides_create
        elif tool_name == "slides_create" or tool_name == "create_presentation":
            
            # Extract presentation ID and URL from result
            # Result format: "Presentation 'title' created successfully (ID: {id}) URL: {url}" or JSON
            try:
                # Try to parse as JSON first
                import json
                result_json = json.loads(result) if isinstance(result, str) else result
                if isinstance(result_json, dict) and "presentationId" in result_json:
                    presentation_id = result_json.get("presentationId")
                    url = result_json.get("url", f"https://docs.google.com/presentation/d/{presentation_id}/edit")
                    title = result_json.get("title", tool_args.get("title", "Google Slides"))
                else:
                    # Fallback to regex parsing
                    presentation_id_match = re.search(r'ID:\s*([a-zA-Z0-9_-]+)', result)
                    url_match = re.search(r'URL:\s*(https?://[^\s]+)', result)
                    title_match = re.search(r"Presentation\s+'([^']+)'", result)
                    
                    if presentation_id_match:
                        presentation_id = presentation_id_match.group(1)
                        url = url_match.group(1) if url_match else f"https://docs.google.com/presentation/d/{presentation_id}/edit"
                        title = title_match.group(1) if title_match else tool_args.get("title", "Google Slides")
                    else:
                        logger.warning(f"[AgentWrapper] Failed to extract presentation_id from result: {result[:500]}")
                        return
            except json.JSONDecodeError:
                # Not JSON, try regex
                presentation_id_match = re.search(r'ID:\s*([a-zA-Z0-9_-]+)', result)
                url_match = re.search(r'URL:\s*(https?://[^\s]+)', result)
                title_match = re.search(r"Presentation\s+'([^']+)'", result)
                
                if presentation_id_match:
                    presentation_id = presentation_id_match.group(1)
                    url = url_match.group(1) if url_match else f"https://docs.google.com/presentation/d/{presentation_id}/edit"
                    title = title_match.group(1) if title_match else tool_args.get("title", "Google Slides")
                else:
                    logger.warning(f"[AgentWrapper] Failed to extract presentation_id from result: {result[:500]}")
                    return
            
            
            await self.ws_manager.send_event(
                session_id,
                "slides_action",
                {
                    "action": "create",
                    "presentation_id": presentation_id,
                    "presentation_url": url,
                    "title": title,
                    "description": f"Создана презентация '{title}'"
                }
            )
            logger.info(f"[AgentWrapper] Sent slides_action event for presentation {presentation_id}")
            
        
        # Handle execute_python_code - show code in code viewer
        elif tool_name == "execute_python_code":
            code = tool_args.get("code", "")
            if code:
                # Extract filename from code if it's a script
                filename = "executed_code.py"
                if "def " in code or "import " in code:
                    filename = "script.py"
                
                await self.ws_manager.send_event(
                    session_id,
                    "code_display",
                    {
                        "filename": filename,
                        "language": "python",
                        "code": code
                    }
                )
                logger.info(f"[AgentWrapper] Sent code_display event for Python code")
        
        # Handle add_rows - append rows to spreadsheet
        elif tool_name == "add_rows":
            spreadsheet_id = tool_args.get("spreadsheet_id")
            sheet_name = tool_args.get("sheet_name", "Sheet1")
            values = tool_args.get("values", [])
            
            if spreadsheet_id:
                # Check if we already sent event for this spreadsheet_id (prevent duplicates)
                event_key = f"{session_id}:add_rows:{spreadsheet_id}"
                current_time = time.time()
                if event_key in self._sent_workspace_events:
                    last_sent = self._sent_workspace_events[event_key]
                    # Only skip if sent within last 5 seconds (to allow retries after longer delays)
                    if current_time - last_sent < 5:
                        logger.info(f"[AgentWrapper] Skipping duplicate sheets_action event for spreadsheet {spreadsheet_id} (sent {current_time - last_sent:.2f}s ago)")
                        return
                
                rows_count = len(values) if isinstance(values, list) else 0
                url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
                
                # Extract title from result if available
                title_match = re.search(r"sheet\s+'([^']+)'", result, re.IGNORECASE)
                title = title_match.group(1) if title_match else "Google Sheets"
                
                # Try to get spreadsheet title from previous context or use default
                # For now, use "Google Sheets" as default
                title = "Google Sheets"
                
                # Form description
                description = f"Добавлено {rows_count} строк(и) в лист '{sheet_name}'"
                
                event_data = {
                    "action": "append",
                    "spreadsheet_id": spreadsheet_id,
                    "spreadsheet_url": url,
                    "title": title,
                    "range": f"{sheet_name}!A:A",  # Approximate range for append
                    "description": description
                }
                
                await self.ws_manager.send_event(
                    session_id,
                    "sheets_action",
                    event_data
                )
                # Mark as sent
                self._sent_workspace_events[event_key] = current_time
                logger.info(f"[AgentWrapper] Sent sheets_action event for appended rows to spreadsheet {spreadsheet_id}")
        
        # Handle update_cells - update specific cell range
        elif tool_name == "update_cells":
            spreadsheet_id = tool_args.get("spreadsheet_id")
            range_str = tool_args.get("range", "")
            values = tool_args.get("values", [])
            
            if spreadsheet_id:
                # Check if we already sent event for this spreadsheet_id (prevent duplicates)
                event_key = f"{session_id}:update_cells:{spreadsheet_id}:{range_str}"
                current_time = time.time()
                if event_key in self._sent_workspace_events:
                    last_sent = self._sent_workspace_events[event_key]
                    # Only skip if sent within last 5 seconds (to allow retries after longer delays)
                    if current_time - last_sent < 5:
                        logger.info(f"[AgentWrapper] Skipping duplicate sheets_action event for spreadsheet {spreadsheet_id} (sent {current_time - last_sent:.2f}s ago)")
                        return
                
                rows_count = len(values) if isinstance(values, list) else 0
                url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
                
                # Extract title from result if available, otherwise use default
                title = "Google Sheets"
                
                # Form description
                description = f"Обновлено {rows_count} строк(и) в диапазоне '{range_str}'"
                
                event_data = {
                    "action": "update",
                    "spreadsheet_id": spreadsheet_id,
                    "spreadsheet_url": url,
                    "title": title,
                    "range": range_str,
                    "description": description
                }
                
                await self.ws_manager.send_event(
                    session_id,
                    "sheets_action",
                    event_data
                )
                # Mark as sent
                self._sent_workspace_events[event_key] = current_time
                logger.info(f"[AgentWrapper] Sent sheets_action event for updated cells in spreadsheet {spreadsheet_id}")
        
        # Handle get_sheet_data - optional read action (can be disabled if not needed)
        elif tool_name == "get_sheet_data":
            spreadsheet_id = tool_args.get("spreadsheet_id")
            range_str = tool_args.get("range", "")
            
            if spreadsheet_id:
                url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
                
                # Extract row count from result
                rows_match = re.search(r'(\d+)\s+row\(s\)', result, re.IGNORECASE)
                rows_count = rows_match.group(1) if rows_match else "?"
                
                title = "Google Sheets"
                description = f"Прочитано {rows_count} строк(и) из диапазона '{range_str}'"
                
                event_data = {
                    "action": "read",
                    "spreadsheet_id": spreadsheet_id,
                    "spreadsheet_url": url,
                    "title": title,
                    "range": range_str,
                    "description": description
                }
                
                await self.ws_manager.send_event(
                    session_id,
                    "sheets_action",
                    event_data
                )
                logger.info(f"[AgentWrapper] Sent sheets_action event for read operation on spreadsheet {spreadsheet_id}")
    
    async def update_plan(
        self,
        confirmation_id: str,
        updated_plan: Dict[str, Any],
        context: ConversationContext,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Update a pending plan before execution.
        
        Args:
            confirmation_id: Confirmation ID
            updated_plan: Updated plan with "plan" and "steps"
            context: Conversation context
            session_id: Session identifier
            
        Returns:
            Update result
        """
        # Get active orchestrator for this session
        orchestrator = self._active_orchestrators.get(session_id)
        if orchestrator:
            # Verify confirmation_id matches
            if orchestrator.get_confirmation_id() != confirmation_id:
                logger.warning(f"[AgentWrapper] Confirmation ID mismatch: expected {orchestrator.get_confirmation_id()}, got {confirmation_id}")
            
            # Update the plan in orchestrator
            orchestrator.update_pending_plan(updated_plan)
            return {
                "status": "updated",
                "message": "Plan updated successfully"
            }
        else:
            logger.warning(f"[AgentWrapper] No active orchestrator for session {session_id}")
            raise Exception("No active orchestrator found for this session")

