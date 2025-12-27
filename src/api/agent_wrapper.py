"""
Wrapper for agent execution that emits WebSocket events.
Captures intermediate steps and streams them to frontend.
"""

from typing import Dict, Any, Optional
import asyncio
import logging

from src.agents.main_agent import MainAgent
from src.agents.base_agent import StreamEvent
from src.core.context_manager import ConversationContext
from src.api.websocket_manager import get_websocket_manager
from src.utils.audit import get_audit_logger
from src.utils.config_loader import get_config

logger = logging.getLogger(__name__)


class AgentWrapper:
    """
    Wraps agent execution to emit WebSocket events for real-time updates.
    """
    
    def __init__(self):
        """Initialize agent wrapper."""
        # MainAgent will be created per request with model from context
        self._main_agent_cache: Dict[str, MainAgent] = {}
        self.ws_manager = get_websocket_manager()
        self.audit_logger = get_audit_logger()
    
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
        session_id: str
    ) -> Dict[str, Any]:
        """
        Process user message through agent and emit events.
        
        Args:
            user_message: User's message
            context: Conversation context
            session_id: Session identifier
            
        Returns:
            Final execution result
        """
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
            # Get MainAgent instance with model from context
            main_agent = self.get_main_agent(context.model_name)
            
            # Execute agent based on execution mode
            if context.execution_mode == "approval":
                result = await main_agent.execute_with_mode(
                    user_message,
                    context,
                    execution_mode="approval"
                )
                
                if result.get("type") == "plan_request":
                    # Send plan request event
                    await self.ws_manager.send_event(
                        session_id,
                        "plan_request",
                        {
                            "confirmation_id": result["confirmation_id"],
                            "plan": result["plan"]
                        }
                    )
                    return result
            else:
                # Execute immediately with streaming
                result = await self._execute_with_streaming(
                    user_message,
                    context,
                    session_id
                )
                
                # Stream the response (already done in _execute_with_streaming)
                # Just log the action
                self.audit_logger.log_agent_action(
                    "MainAgent",
                    "execute",
                    {"message": user_message, "result": "success"},
                    session_id=session_id
                )
                
                return result
            
        except Exception as e:
            # Extract detailed error message
            error_message = str(e)
            if not error_message or error_message.strip() == "":
                # Try to get message from exception attributes
                if hasattr(e, 'message'):
                    error_message = str(e.message)
                elif hasattr(e, 'args') and len(e.args) > 0:
                    error_message = str(e.args[0])
                else:
                    error_message = f"Произошла ошибка: {type(e).__name__}"
            
            # Send error event
            await self.ws_manager.send_event(
                session_id,
                "error",
                {
                    "message": error_message,
                    "type": type(e).__name__
                }
            )
            
            # Also send as system message for better visibility
            await self.ws_manager.send_event(
                session_id,
                "message",
                {
                    "role": "system",
                    "content": f"Ошибка: {error_message}"
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
            
            # Import exception types
            from src.utils.exceptions import ToolExecutionError, MCPError
            
            # Create user-friendly error message
            if isinstance(e, ToolExecutionError):
                friendly_message = f"Не удалось выполнить операцию: {error_message}"
            elif isinstance(e, MCPError):
                friendly_message = f"Ошибка подключения к сервису: {error_message}"
            else:
                friendly_message = f"Ошибка: {error_message}"
            
            raise Exception(friendly_message) from e
    
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
        
        # Track if we've sent message_start
        message_started = False
        accumulated_tokens = ""
        
        async def stream_event_callback(event_type: str, data: Dict[str, Any]):
            """Callback to handle streaming events and send to WebSocket."""
            nonlocal message_started, accumulated_tokens
            
            logger.debug(f"[AgentWrapper] Stream event: {event_type}, data keys: {list(data.keys())}")
            
            if event_type == StreamEvent.THINKING:
                # Send thinking/reasoning step
                # message contains the accumulated thinking text
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                        import json as json_lib
                        import time
                        f.write(json_lib.dumps({"location": "agent_wrapper.py:293", "message": "THINKING event received", "data": {"step": data.get("step"), "message_length": len(data.get("message", ""))}, "timestamp": time.time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "L"}) + "\n")
                except: pass
                # #endregion
                thinking_message = data.get("message", data.get("step", "Обрабатываю..."))
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                        import json as json_lib
                        import time
                        f.write(json_lib.dumps({"location": "agent_wrapper.py:297", "message": "sending thinking event to websocket", "data": {"session_id": session_id, "thinking_message_length": len(thinking_message)}, "timestamp": time.time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "M"}) + "\n")
                except: pass
                # #endregion
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
                await self.ws_manager.send_event(
                    session_id,
                    "error",
                    {
                        "message": data.get("error", "Unknown error")
                    }
                )
        
        # Execute with streaming
        logger.info(f"[AgentWrapper] Calling main_agent.execute_with_streaming")
        # Get MainAgent instance with model from context
        main_agent = self.get_main_agent(context.model_name)
        
        result = await main_agent.execute_with_streaming(
            user_message,
            context,
            event_callback=stream_event_callback
        )
        
        logger.info(f"[AgentWrapper] Streaming execution complete, response length: {len(result.get('response', ''))}")
        
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
        Execute an approved plan.
        
        Args:
            confirmation_id: Confirmation ID
            context: Conversation context
            session_id: Session identifier
            
        Returns:
            Execution result
        """
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
        
        result = await main_agent.execute_approved_plan(
            confirmation_id,
            context
        )
        
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
        Reject a plan.
        
        Args:
            confirmation_id: Confirmation ID
            context: Conversation context
            session_id: Session identifier
        """
        context.resolve_confirmation(confirmation_id, approved=False)
        
        await self.ws_manager.send_event(
            session_id,
            "message",
            {
                "role": "assistant",
                "content": "Plan rejected. How would you like to proceed?"
            }
        )

