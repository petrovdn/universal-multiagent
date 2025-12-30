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
        file_ids: Optional[List[str]] = None
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
        file_ids = file_ids or []# Wait for WebSocket connection BEFORE sending any events
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
            
            # Complex tasks use StepOrchestrator with planning
            # Mode depends on execution_mode setting
            logger.info(f"[AgentWrapper] Complex task detected, using StepOrchestrator")
            
            # CRITICAL: Stop and remove any existing orchestrator for this session
            # This prevents mixing context from previous requests
            if session_id in self._active_orchestrators:
                old_orchestrator = self._active_orchestrators[session_id]
                logger.info(f"[AgentWrapper] Stopping previous orchestrator for session {session_id}")
                old_orchestrator.stop()
                del self._active_orchestrators[session_id]
            
            if context.execution_mode == "approval":
                orchestrator_mode = "plan_and_confirm"
            else:
                orchestrator_mode = "plan_and_execute"
            
            # Create StepOrchestrator for this session
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
            self.audit_logger.log_agent_action(
                "StepOrchestrator",
                "execute",
                {"message": user_message, "mode": orchestrator_mode, "result": result.get("status", "unknown")},
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
            
            # Send error event
            await self.ws_manager.send_event(
                session_id,
                "error",
                {
                    "message": error_message,  # Send original, not escaped
                    "type": type(e).__name__
                }
            )
            
            # Also send as system message for better visibility (use .format() instead of f-string)
            await self.ws_manager.send_event(
                session_id,
                "message",
                {
                    "role": "system",
                    "content": "Ошибка: {error}".format(error=escaped_error_message)
                }
            )
            
            raise
    
    async def _execute_with_streaming(
        self,
        user_message: str,
        context: ConversationContext,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Execute agent with real-time streaming of tokens and events.
        
        Args:
            user_message: User's message
            context: Conversation context
            session_id: Session identifier
            
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
        logger.info(f"[AgentWrapper] Starting streaming execution, context.session_id: {session_id_val}")
        try:
            # Execute agent with real-time event streaming
            # Events are sent directly to WebSocket via callback in _execute_with_event_streaming
            result = await self._execute_with_event_streaming(
                user_message,
                context,
                session_id
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
            
            # Create user-friendly error message using .format() instead of f-string to avoid issues with escaped content
            if isinstance(e, ToolExecutionError):
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
        
        # Use direct streaming execution (no workflow)
        result = await self._execute_with_streaming(
            user_message,
            context,
            session_id
        )
        
        # Generate final result summary
        try:
            final_result = await self._generate_simple_task_result(
                user_message,
                result.get("response", ""),
                context
            )
            
            # Send final_result event
            await self.ws_manager.send_event(
                session_id,
                "final_result",
                {
                    "content": final_result,
                    "summary": True
                }
            )
        except Exception as e:
            logger.error(f"[AgentWrapper] Error generating final result for simple task: {e}")
            # Don't fail the whole task if result generation fails
        
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
- Прямой ответ на запрос пользователя
- Ключевая информация, которая была запрошена
- Если нужно, структурируй информацию для удобства чтения

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
        session_id: str
    ) -> Dict[str, Any]:
        """
        Execute agent with real-time event streaming.
        
        Uses astream_events to get real-time tokens, tool calls, and results
        from the LLM and sends them to the frontend via WebSocket.
        
        Args:
            user_message: User's message
            context: Conversation context
            session_id: Session identifier
            
        Returns:
            Execution result
        """
        logger.info(f"[AgentWrapper] Starting real-time streaming for session {session_id}")
        
        # Generate unique message ID for this streaming response
        message_id = f"stream_{session_id}_{asyncio.get_event_loop().time()}"
        
        # Store message_id so exception handler can access it
        self._current_streaming_message_id = message_id
        
        # Track if we've sent message_start
        message_started = False
        accumulated_tokens = ""
        
        async def stream_event_callback(event_type: str, data: Dict[str, Any]):
            """
Callback to handle streaming events and send to WebSocket."""
            nonlocal message_started, accumulated_tokens, message_id
            
            logger.debug(f"[AgentWrapper] Stream event: {event_type}, data keys: {list(data.keys())}")
            if event_type == StreamEvent.THINKING:
                # Send thinking/reasoning step
                # message contains the accumulated thinking text
                thinking_message = data.get("message", data.get("step", "Обрабатываю..."))
                await self.ws_manager.send_event(
                    session_id,
                    "thinking",
                    {
                        "step": data.get("step", "reasoning"),
                        "message": thinking_message  # This is the accumulated thinking text
                    }
                )
            
            elif event_type == StreamEvent.TOKEN:
                # Send streaming token
                token = data.get("token", "")
                accumulated_tokens = data.get("accumulated", accumulated_tokens + token)
                
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
                await self.ws_manager.send_event(
                    session_id,
                    "tool_call",
                    {
                        "tool_name": data.get("tool_name", "unknown"),
                        "arguments": data.get("arguments", {}),
                        "status": data.get("status", "calling")
                    }
                )
                # Also send as thinking step for visibility
                await self.ws_manager.send_event(
                    session_id,
                    "thinking",
                    {
                        "step": "tool_call",
                        "message": f"Вызываю: {data.get('tool_name', 'unknown')}"
                    }
                )
            
            elif event_type == StreamEvent.TOOL_RESULT:
                # Send tool result event with compact formatting
                result = data.get("result", "")
                # Make result more compact if it's too long
                if len(result) > 2000:
                    result = result[:2000] + "\n\n... (результат обрезан, показаны первые 2000 символов) ..."
                
                await self.ws_manager.send_event(
                    session_id,
                    "tool_result",
                    {
                        "tool_name": data.get("tool_name", "unknown"),
                        "result": result
                    }
                )
            
            elif event_type == StreamEvent.DONE:
                # Complete the streaming message
                response = data.get("response", accumulated_tokens)
                logger.info(f"[AgentWrapper] DONE event received, response length: {len(response)}, message_started: {message_started}")
                
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
                )# Always send message_complete after error to signal end of streaming
                # This ensures the frontend knows streaming is done even after error
                # If message was started, complete it. If not, still send message_complete with empty content
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

