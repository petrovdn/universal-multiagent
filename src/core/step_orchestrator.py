"""
Step Orchestrator for multi-step execution with planning and confirmation.
Implements plan_and_confirm and plan_and_execute modes with streaming.
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
import asyncio
import json
import re
import time
from uuid import uuid4

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

from src.core.context_manager import ConversationContext
from src.api.websocket_manager import WebSocketManager
from src.agents.model_factory import create_llm
from src.utils.logging_config import get_logger
from src.utils.capabilities import get_available_capabilities, build_step_executor_prompt, build_planning_prompt
from src.mcp_tools.workspace_tools import get_workspace_tools
from src.mcp_tools.sheets_tools import get_sheets_tools
from src.mcp_tools.gmail_tools import get_gmail_tools
from src.mcp_tools.calendar_tools import get_calendar_tools

logger = get_logger(__name__)


def _escape_braces_for_fstring(text: str) -> str:
    """
    Escape curly braces in text to safely use in f-strings.
    Doubles all { and } characters so they are treated as literals.
    
    Args:
        text: Text that may contain curly braces
        
    Returns:
        Text with escaped braces
    """
    return text.replace("{", "{{").replace("}", "}}")


class StepOrchestrator:
    """
    Orchestrator for multi-step execution with planning and optional confirmation.
    
    Modes:
    - plan_and_confirm: Generate plan, wait for approval, then execute steps
    - plan_and_execute: Generate plan and execute immediately
    """
    
    def __init__(
        self,
        ws_manager: WebSocketManager,
        session_id: str,
        model_name: Optional[str] = None
    ):
        """
        Initialize StepOrchestrator.
        
        Args:
            ws_manager: WebSocket manager for sending events
            session_id: Session identifier
            model_name: Model name for LLM (optional, uses default from config if None)
        """
        self.ws_manager = ws_manager
        self.session_id = session_id
        self.model_name = model_name
        
        # Load tools for step execution
        self.tools = self._load_tools()
        
        # Create LLM with extended thinking support
        self.llm = self._create_llm_with_thinking()
        
        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # State for plan confirmation
        self._confirmation_event: Optional[asyncio.Event] = None
        self._confirmation_result: Optional[bool] = None
        self._plan_steps: List[str] = []
        self._plan_text: str = ""
        self._confirmation_id: Optional[str] = None
        
        # State for user assistance requests
        self._user_assistance_event: Optional[asyncio.Event] = None
        self._user_assistance_result: Optional[Dict[str, Any]] = None
        self._user_assistance_id: Optional[str] = None
        self._user_assistance_context: Optional[Dict[str, Any]] = None
        self._user_assistance_options: Optional[List[Dict[str, Any]]] = None
        
        self._stop_requested: bool = False
        self._streaming_task: Optional[asyncio.Task] = None
        
        logger.info(f"[StepOrchestrator] Initialized for session {session_id} with model {model_name or 'default'}")
    
    def stop(self):
        """
        Request stop of execution.
        """
        self._stop_requested = True
        if self._streaming_task and not self._streaming_task.done():
            self._streaming_task.cancel()
            logger.info(f"[StepOrchestrator] Cancelled streaming task for session {self.session_id}")
        logger.info(f"[StepOrchestrator] Stop requested for session {self.session_id}")
    
    def _load_tools(self) -> List:
        """
        Load all available tools for step execution.
        
        Returns:
            List of LangChain tools
        """
        tools = []
        try:
            # Load workspace tools (file search, etc.)
            workspace_tools = get_workspace_tools()
            tools.extend(workspace_tools)
            
            # Load sheets tools
            sheets_tools = get_sheets_tools()
            tools.extend(sheets_tools)
            
            # Load gmail tools
            gmail_tools = get_gmail_tools()
            tools.extend(gmail_tools)
            
            # Load calendar tools
            calendar_tools = get_calendar_tools()
            tools.extend(calendar_tools)
            
            # Remove duplicates by name
            seen_names = set()
            unique_tools = []
            for tool in tools:
                if tool.name not in seen_names:
                    seen_names.add(tool.name)
                    unique_tools.append(tool)
            
            logger.info(f"[StepOrchestrator] Loaded {len(unique_tools)} tools for step execution")
            return unique_tools
        except Exception as e:
            logger.error(f"[StepOrchestrator] Failed to load tools: {e}")
            return []
    
    def _create_llm_with_thinking(self) -> BaseChatModel:
        """
Create LLM instance with extended thinking enabled."""
        from src.utils.config_loader import get_config
        from langchain_anthropic import ChatAnthropic
        
        config_model_name = self.model_name or "claude-sonnet-4-5"  # Default to Claude Sonnet 4.5 for thinking
        config = get_config()
        
        try:
            # Check if model supports extended thinking
            from src.agents.model_factory import MODELS, get_available_models
            available_models = get_available_models()
            
            if config_model_name in available_models:
                model_config = available_models[config_model_name]
                if model_config.get("supports_reasoning") and model_config.get("reasoning_type") == "extended_thinking":
                    # Create LLM with extended thinking (budget_tokens will be set per-invocation)
                    llm = ChatAnthropic(
                        model=model_config["model_id"],
                        api_key=config.anthropic_api_key,
                        streaming=True,
                        temperature=1,  # Required for extended thinking
                        thinking={
                            "type": "enabled",
                            "budget_tokens": 5000  # Use 5000 for steps
                        }
                    )
                    return llm
            
            # Fallback: use create_llm for models without thinking support
            return create_llm(config_model_name)
        except Exception as e:
            logger.error(f"[StepOrchestrator] Failed to create LLM: {e}")
            # Fallback to default model
            try:
                return create_llm(config.default_model)
            except Exception as e2:
                logger.error(f"[StepOrchestrator] Failed to create fallback LLM: {e2}")
                raise
    
    async def execute(
        self,
        user_request: str,
        mode: str,
        context: ConversationContext,
        file_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        file_ids = file_ids or []
        """
        Execute multi-step workflow.
        
        Args:
            user_request: User's request
            mode: "plan_and_confirm" or "plan_and_execute"
            context: Conversation context
            
        Returns:
            Execution result with final status
        """
        try:
            # Step 1: Generate plan
            logger.info(f"[StepOrchestrator] Generating plan for request: {user_request[:100]}")
            plan_result = await self._generate_plan(user_request, context, file_ids)
            
            # Check if stop was requested during plan generation
            if self._stop_requested:
                logger.info(f"[StepOrchestrator] Stop requested during plan generation")
                await self.ws_manager.send_event(
                    self.session_id,
                    "workflow_stopped",
                    {
                        "reason": "Остановлено пользователем",
                        "step": 0,
                        "remaining_steps": 0
                    }
                )
                return {
                    "status": "stopped",
                    "message": "Генерация остановлена пользователем"
                }
            
            plan_text = plan_result["plan"]
            plan_steps = plan_result["steps"]
            
            self._plan_text = plan_text
            self._plan_steps = plan_steps
            self._confirmation_id = str(uuid4())
            
            # Send plan_generated event
            await self.ws_manager.send_event(
                self.session_id,
                "plan_generated",
                {
                    "plan": plan_text,
                    "steps": plan_steps,
                    "confirmation_id": self._confirmation_id
                }
            )
            
            # Check if stop was requested after plan generation
            if self._stop_requested:
                logger.info(f"[StepOrchestrator] Stop requested after plan generation")
                await self.ws_manager.send_event(
                    self.session_id,
                    "workflow_stopped",
                    {
                        "reason": "Остановлено пользователем",
                        "step": 0,
                        "remaining_steps": len(plan_steps)
                    }
                )
                return {
                    "status": "stopped",
                    "message": "Генерация остановлена пользователем",
                    "plan": plan_text,
                    "steps": plan_steps
                }
            
            # Step 2: Handle confirmation based on mode
            if mode == "plan_and_confirm":
                # Send awaiting_confirmation event
                await self.ws_manager.send_event(
                    self.session_id,
                    "awaiting_confirmation",
                    {}
                )
                
                # Store confirmation in context
                context.add_pending_confirmation(self._confirmation_id, {
                    "plan": plan_text,
                    "steps": plan_steps,
                    "mode": mode
                })
                
                # Wait for confirmation (will be triggered by confirm_plan() or reject_plan())
                self._confirmation_event = asyncio.Event()
                confirmation_timeout = 300  # 5 minutes timeout
                try:
                    # Wait for confirmation with periodic stop checks
                    while not self._confirmation_event.is_set():
                        if self._stop_requested:
                            logger.info(f"[StepOrchestrator] Stop requested during confirmation wait")
                            await self.ws_manager.send_event(
                                self.session_id,
                                "workflow_stopped",
                                {
                                    "reason": "Остановлено пользователем",
                                    "step": 0,
                                    "remaining_steps": len(plan_steps)
                                }
                            )
                            # Reset confirmation state
                            self._confirmation_event = None
                            self._confirmation_result = None
                            return {
                                "status": "stopped",
                                "message": "Генерация остановлена пользователем"
                            }
                        
                        try:
                            await asyncio.wait_for(
                                self._confirmation_event.wait(),
                                timeout=0.5  # Check every 0.5 seconds
                            )
                            break
                        except asyncio.TimeoutError:
                            # Continue checking _stop_requested
                            continue
                except asyncio.TimeoutError:
                    logger.warning(f"[StepOrchestrator] Confirmation timeout for session {self.session_id}")
                    await self.ws_manager.send_event(
                        self.session_id,
                        "error",
                        {"message": "Confirmation timeout. Plan execution cancelled."}
                    )
                    # Reset confirmation state
                    self._confirmation_event = None
                    self._confirmation_result = None
                    
                    return {
                        "status": "timeout",
                        "message": "Confirmation timeout"
                    }
                
                # Check if stop was requested after confirmation
                if self._stop_requested:
                    logger.info(f"[StepOrchestrator] Stop requested after confirmation")
                    await self.ws_manager.send_event(
                        self.session_id,
                        "workflow_stopped",
                        {
                            "reason": "Остановлено пользователем",
                            "step": 0,
                            "remaining_steps": len(plan_steps)
                        }
                    )
                    # Reset confirmation state
                    self._confirmation_event = None
                    self._confirmation_result = None
                    return {
                        "status": "stopped",
                        "message": "Генерация остановлена пользователем"
                    }
                
                if not self._confirmation_result:
                    # Plan was rejected
                    await self.ws_manager.send_event(
                        self.session_id,
                        "error",
                        {"message": "Plan rejected by user"}
                    )
                    # Reset confirmation state
                    self._confirmation_event = None
                    self._confirmation_result = None
                    
                    return {
                        "status": "rejected",
                        "message": "Plan rejected"
                    }
            
            # Step 3: Execute steps sequentially
            logger.info(f"[StepOrchestrator] Executing {len(plan_steps)} steps")
            step_results = []
            
            for step_index, step_title in enumerate(plan_steps, start=1):
                # Check if stop was requested before starting step
                if self._stop_requested:
                    logger.info(f"[StepOrchestrator] Stop requested, stopping execution before step {step_index}")
                    await self.ws_manager.send_event(
                        self.session_id,
                        "workflow_stopped",
                        {
                            "reason": "Остановлено пользователем",
                            "step": step_index - 1,
                            "remaining_steps": len(plan_steps) - step_index + 1
                        }
                    )
                    break
                
                try:
                    # Check again before sending step_start event
                    if self._stop_requested:
                        logger.info(f"[StepOrchestrator] Stop requested before step {step_index} start event")
                        await self.ws_manager.send_event(
                            self.session_id,
                            "workflow_stopped",
                            {
                                "reason": "Остановлено пользователем",
                                "step": step_index - 1,
                                "remaining_steps": len(plan_steps) - step_index + 1
                            }
                        )
                        break
                    
                    # Send step_start event
                    await self.ws_manager.send_event(
                        self.session_id,
                        "step_start",
                        {
                            "step": step_index,
                            "title": step_title
                        }
                    )# Execute step with streaming
                    step_result = await self._execute_step(
                        step_index,
                        step_title,
                        user_request,
                        plan_text,
                        plan_steps,
                        step_results,
                        context,
                        file_ids
                    )# Add step result
                    step_results.append({
                        "step": step_index,
                        "title": step_title,
                        "result": step_result
                    })
                    
                    # Send step_complete event
                    await self.ws_manager.send_event(
                        self.session_id,
                        "step_complete",
                        {
                            "step": step_index
                        }
                    )
                    
                    # Check if stop was requested after sending step_complete
                    if self._stop_requested:
                        logger.info(f"[StepOrchestrator] Stop requested after step {step_index} completion")
                        await self.ws_manager.send_event(
                            self.session_id,
                            "workflow_stopped",
                            {
                                "reason": "Остановлено пользователем",
                                "step": step_index,
                                "remaining_steps": len(plan_steps) - step_index
                            }
                        )
                        break
                    
                    # Check if step requires user help (critical error)
                    if "🛑 ТРЕБУЕТСЯ ПОМОЩЬ ПОЛЬЗОВАТЕЛЯ" in step_result:
                        logger.warning(f"[StepOrchestrator] Step {step_index} requires user help, stopping execution")
                        await self.ws_manager.send_event(
                            self.session_id,
                            "workflow_paused",
                            {
                                "reason": "Шаг требует помощи пользователя",
                                "step": step_index,
                                "remaining_steps": len(plan_steps) - step_index
                            }
                        )
                        # Stop executing remaining steps
                        break
                    
                    # Check if stop was requested after step execution (before adding result)
                    if self._stop_requested:
                        logger.info(f"[StepOrchestrator] Stop requested after step {step_index} execution")
                        await self.ws_manager.send_event(
                            self.session_id,
                            "workflow_stopped",
                            {
                                "reason": "Остановлено пользователем",
                                "step": step_index,
                                "remaining_steps": len(plan_steps) - step_index
                            }
                        )
                        break
                    
                except Exception as e:
                    # Проверить, является ли это исключением остановки
                    from src.utils.exceptions import AgentError
                    if isinstance(e, AgentError) and "остановлено" in str(e).lower():
                        logger.info(f"[StepOrchestrator] Stop exception caught for step {step_index}")
                        await self.ws_manager.send_event(
                            self.session_id,
                            "workflow_stopped",
                            {
                                "reason": "Остановлено пользователем",
                                "step": step_index,
                                "remaining_steps": len(plan_steps) - step_index
                            }
                        )
                        break
                    # Если это не исключение остановки, пробросить дальше
                    logger.error(f"[StepOrchestrator] Error executing step {step_index}: {e}")
                    await self.ws_manager.send_event(
                        self.session_id,
                        "error",
                        {
                            "message": f"Error in step {step_index}: {str(e)}"
                        }
                    )
                    raise# Step 4: Check if stop was requested before sending workflow_complete
            if self._stop_requested:
                logger.info(f"[StepOrchestrator] Stop requested, workflow not completed")
                # Reset confirmation state
                self._confirmation_event = None
                self._confirmation_result = None
                return {
                    "status": "stopped",
                    "message": "Генерация остановлена пользователем",
                    "steps": step_results,
                    "plan": plan_text,
                    "confirmation_id": self._confirmation_id
                }
            
            # Send workflow_complete event only if not stopped
            await self.ws_manager.send_event(
                self.session_id,
                "workflow_complete",
                {}
            )
            
            logger.info(f"[StepOrchestrator] Workflow completed successfully")
            
            # Generate and stream final result (events are sent from _generate_final_result)
            try:
                await self._generate_final_result(
                    user_request,
                    plan_text,
                    step_results,
                    context
                )
                
                logger.info(f"[StepOrchestrator] Final result generated and streamed")
            except Exception as e:
                logger.error(f"[StepOrchestrator] Error generating final result: {e}")
                # Don't fail the whole workflow if result generation fails
                # Just log the error and continue
            
            # Reset confirmation state
            self._confirmation_event = None
            self._confirmation_result = None
            
            return {
                "status": "completed",
                "steps": step_results,
                "plan": plan_text,
                "confirmation_id": self._confirmation_id
            }
            
        except Exception as e:
            logger.error(f"[StepOrchestrator] Error in execute: {e}", exc_info=True)
            await self.ws_manager.send_event(
                self.session_id,
                "error",
                {"message": str(e)}
            )
            # Reset confirmation state on error
            self._confirmation_event = None
            self._confirmation_result = None
            raise
    
    async def _generate_plan(
        self,
        user_request: str,
        context: ConversationContext,
        file_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        file_ids = file_ids or []
        
        # Helper function to create HumanMessage with file attachments
        def create_message_with_files(text: str, files: List[Dict[str, Any]]) -> HumanMessage:
            """
Create HumanMessage with text and optional file attachments."""
            content_parts = [{"type": "text", "text": text}]
            
            # Add image files as image_url blocks
            for file in files:
                if file.get("type", "").startswith("image/") and "data" in file:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{file.get('media_type', file.get('type', 'image/png'))};base64,{file['data']}"
                        }
                    })
                elif "text" in file:  # PDF text content
                    # Append PDF text to the text content (escape braces in file text)
                    filename = _escape_braces_for_fstring(str(file.get('filename', 'document.pdf')))
                    file_text = _escape_braces_for_fstring(str(file['text']))
                    # Use string concatenation instead of f-string to avoid issues
                    content_parts[0]["text"] += "\n\n[Содержимое файла " + filename + "]:\n" + file_text
            
            # If we have multiple content parts or complex content, use list format
            if len(content_parts) > 1 or any(part.get("type") != "text" for part in content_parts):
                return HumanMessage(content=content_parts)
            else:
                # Simple text message
                return HumanMessage(content=text)
        
        # Get file data from context
        files_data = []
        for file_id in file_ids:
            file_data = context.get_file(file_id)
            if file_data:
                files_data.append(file_data)
        
        # Build uploaded files information text (PRIORITY #1)
        uploaded_files_info = ""
        if files_data:
            uploaded_files_info = "\n\n📎 ЗАГРУЖЕННЫЕ ФАЙЛЫ (ПРИОРИТЕТ #1):\n"
            uploaded_files_info += "⚠️ ВАЖНО: Текст этих файлов УЖЕ включен в это сообщение ниже!\n"
            uploaded_files_info += "⚠️ НЕ ищи эти файлы в Google Диск - используй текст напрямую из сообщения!\n\n"
            for i, file in enumerate(files_data, 1):
                filename = file.get('filename', 'unknown')
                file_type = file.get('type', '')
                if file_type.startswith('image/'):
                    uploaded_files_info += f"{i}. Изображение: {filename} (включено в сообщение)\n"
                elif file_type == 'application/pdf' and 'text' in file:
                    uploaded_files_info += f"{i}. PDF файл: {filename}\n   ⚠️ ТЕКСТ ФАЙЛА УЖЕ ВКЛЮЧЕН В СООБЩЕНИЕ НИЖЕ! Используй его напрямую, НЕ ищи файл в Google Диск!\n"
                else:
                    uploaded_files_info += f"{i}. Файл: {filename} (тип: {file_type})\n"
            uploaded_files_info += "\n⚠️ СНАЧАЛА используй информацию из загруженных файлов (текст уже в сообщении), ПОТОМ уже ищи дополнительные файлы в Google Диск!\n"
        
        """
        Generate detailed execution plan using Claude.
        
        Args:
            user_request: User's request
            context: Conversation context
            
        Returns:
            Dict with "plan" (text) and "steps" (list of step titles)
        """
        # #region agent log
        import time
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"step_orchestrator.py:_generate_plan","message":"Plan generation started","data":{"user_request":user_request[:200],"file_ids":file_ids},"timestamp":int(time.time()*1000)})+'\n')
        except: pass
        # #endregion
        
        # Use dynamic planning prompt
        system_prompt = build_planning_prompt()

        # Prepare messages with file attachments if any
        # Include uploaded files info FIRST, then user request
        # Escape user_request to avoid f-string syntax errors if it contains braces
        escaped_user_request = _escape_braces_for_fstring(user_request)
        plan_request_text = uploaded_files_info + f"\n\nСоздай детальный план выполнения для этого запроса:\n\n{escaped_user_request}"
        user_message = create_message_with_files(plan_request_text, files_data)
        
        messages = [
            SystemMessage(content=system_prompt),
            user_message
        ]
        # Add recent context messages if available, but skip the last user message if it matches current user_request
        recent_messages = context.get_recent_messages(5)
        
        # Only add assistant messages from recent context for planning
        # Do NOT add previous user messages - they can cause confusion and message concatenation
        # IMPORTANT: When using extended thinking, assistant messages from previous requests
        # may not have thinking blocks, which causes API errors. Skip them.
        added_context_messages = []
        # Check if LLM uses extended thinking
        uses_extended_thinking = False
        try:
            from src.agents.model_factory import get_available_models
            available_models = get_available_models()
            config_model_name = self.model_name or "claude-sonnet-4-5"
            if config_model_name in available_models:
                model_config = available_models[config_model_name]
                if model_config.get("supports_reasoning") and model_config.get("reasoning_type") == "extended_thinking":
                    uses_extended_thinking = True
        except:
            pass
        
        for msg in recent_messages:
            role = msg.get("role")
            content = msg.get("content", "")
            # Skip all user messages - we only want the current user_request in the prompt
            # This prevents message concatenation issues
            if role == "user":
                continue
            elif role == "assistant":
                # When using extended thinking, skip assistant messages from previous requests
                # because they may not have thinking blocks, causing API errors
                if uses_extended_thinking:
                    # Skip assistant messages from previous requests to avoid thinking block errors
                    continue
                # Add assistant messages for context (only when not using extended thinking)
                messages.append(AIMessage(content=content))
        try:
            # Check if stop was requested before starting streaming
            if self._stop_requested:
                logger.info(f"[StepOrchestrator] Stop requested before plan generation")
                return {
                    "plan": "Execution plan (stopped)",
                    "steps": ["Execute request"]
                }
            
            # Stream LLM response with thinking
            accumulated_thinking = ""
            accumulated_response = ""
            
            # Создать задачу для стриминга, чтобы можно было её отменить
            async def stream_plan():
                nonlocal accumulated_thinking, accumulated_response
                async for chunk in self.llm.astream(messages):
                    if self._stop_requested:
                        break
                    
                    if hasattr(chunk, 'content'):
                        content = chunk.content
                        
                        # Handle list of content blocks (Claude format with thinking)
                        if isinstance(content, list):
                            for block in content:
                                block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                                
                                if block_type == "thinking":
                                    # Extract thinking text
                                    thinking_text = block.get("thinking", "") if isinstance(block, dict) else getattr(block, "thinking", "")
                                    if thinking_text:
                                        accumulated_thinking += thinking_text
                                        # Stream thinking chunk to UI
                                        await self.ws_manager.send_event(
                                            self.session_id,
                                            "plan_thinking_chunk",
                                            {"content": thinking_text}
                                        )
                                
                                elif block_type == "text":
                                    # Extract response text
                                    text_content = block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
                                    if text_content:
                                        accumulated_response += text_content
                        
                        # Handle simple string content
                        elif isinstance(content, str):
                            accumulated_response += content
            
            # Запустить задачу и сохранить ссылку
            self._streaming_task = asyncio.create_task(stream_plan())
            
            try:
                await self._streaming_task
            except asyncio.CancelledError:
                logger.info(f"[StepOrchestrator] Plan streaming cancelled")
                if self._stop_requested:
                    return {
                        "plan": "Execution plan (stopped)",
                        "steps": ["Execute request"]
                    }
                raise
            finally:
                self._streaming_task = None
            
            # Check if stop was requested after streaming
            if self._stop_requested:
                logger.info(f"[StepOrchestrator] Stop requested after plan generation, returning partial plan")
                # Return partial plan if we have something
                if accumulated_response:
                    try:
                        json_match = re.search(r'\{[\s\S]*\}', accumulated_response)
                        if json_match:
                            json_str = json_match.group(0)
                            plan_data = json.loads(json_str)
                            plan_text = plan_data.get("plan", "Execution plan (partial)")
                            steps = plan_data.get("steps", [])
                        else:
                            plan_text = accumulated_response[:500] if accumulated_response else "Execution plan (partial)"
                            steps = ["Execute request"]
                    except:
                        plan_text = accumulated_response[:500] if accumulated_response else "Execution plan (partial)"
                        steps = ["Execute request"]
                else:
                    plan_text = "Execution plan (stopped)"
                    steps = ["Execute request"]
                
                return {
                    "plan": plan_text,
                    "steps": steps
                }
            
            # Parse JSON response
            response_text = accumulated_response
            
            # Try to extract JSON from response (handle cases where LLM adds markdown code blocks)
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response_text
            
            plan_data = json.loads(json_str)
            
            plan_text = plan_data.get("plan", "Execution plan")
            steps = plan_data.get("steps", [])
            
            if not steps:
                # Fallback: create a simple single-step plan
                steps = ["Execute request"]
            
            logger.info(f"[StepOrchestrator] Generated plan with {len(steps)} steps (thinking: {len(accumulated_thinking)} chars)")
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"step_orchestrator.py:_generate_plan","message":"Plan generated successfully","data":{"steps_count":len(steps),"plan_preview":plan_text[:200],"steps":steps},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            
            return {
                "plan": plan_text,
                "steps": steps
            }
            
        except Exception as e:
            logger.error(f"[StepOrchestrator] Error generating plan: {e}")
            # Fallback plan
            # Escape user_request to avoid f-string syntax errors
            escaped_user_request = _escape_braces_for_fstring(user_request)
            return {
                "plan": f"Execute: {escaped_user_request}",
                "steps": [f"Step 1: {escaped_user_request}"]
            }
    
    async def _execute_step(
        self,
        step_index: int,
        step_title: str,
        user_request: str,
        plan_text: str,
        all_steps: List[str],
        previous_results: List[Dict[str, Any]],
        context: ConversationContext,
        file_ids: Optional[List[str]] = None
    ) -> str:
        file_ids = file_ids or []
        
        # Helper function to create HumanMessage with file attachments
        def create_message_with_files(text: str, files: List[Dict[str, Any]]) -> HumanMessage:
            """
Create HumanMessage with text and optional file attachments."""
            content_parts = [{"type": "text", "text": text}]
            text_was_modified = False
            
            # Add image files as image_url blocks
            for file in files:
                if file.get("type", "").startswith("image/") and "data" in file:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{file.get('media_type', file.get('type', 'image/png'))};base64,{file['data']}"
                        }
                    })
                elif "text" in file:  # PDF text content
                    # Append PDF text to the text content (escape braces in file text)
                    filename = _escape_braces_for_fstring(str(file.get('filename', 'document.pdf')))
                    file_text = _escape_braces_for_fstring(str(file['text']))
                    # Use string concatenation instead of f-string to avoid issues
                    content_parts[0]["text"] += "\n\n[Содержимое файла " + filename + "]:\n" + file_text
                    text_was_modified = True
            
            # Always use content_parts if text was modified (PDF added) or if we have images
            if text_was_modified or len(content_parts) > 1 or any(part.get("type") != "text" for part in content_parts):
                return HumanMessage(content=content_parts)
            else:
                # Simple text message (no files)
                return HumanMessage(content=text)
        
        """
        Execute a single step with streaming thinking and response.
        
        Args:
            step_index: Step number (1-based)
            step_title: Title of the step
            user_request: Original user request
            plan_text: Overall plan description
            all_steps: All step titles
            previous_results: Results from previous steps
            context: Conversation context
            
        Returns:
            Step execution result
        """
        # Get available capabilities for dynamic prompt generation
        try:
            capabilities = await get_available_capabilities()
        except Exception as e:
            logger.warning(f"[StepOrchestrator] Could not get capabilities: {e}, using defaults")
            capabilities = {"enabled_servers": [], "tools_by_category": {}}
        
        # Get file data from context
        files_data = []
        for file_id in file_ids:
            file_data = context.get_file(file_id)
            if file_data:
                files_data.append(file_data)
        
        # Build uploaded files information text (PRIORITY #1)
        uploaded_files_info = ""
        if files_data:
            uploaded_files_info = "📎 ЗАГРУЖЕННЫЕ ФАЙЛЫ (ПРИОРИТЕТ #1):\n"
            uploaded_files_info += "⚠️ ВАЖНО: Текст этих файлов УЖЕ включен в это сообщение ниже!\n"
            uploaded_files_info += "⚠️ НЕ ищи эти файлы в Google Диск - используй текст напрямую из сообщения!\n\n"
            for i, file in enumerate(files_data, 1):
                filename = file.get('filename', 'unknown')
                file_type = file.get('type', '')
                if file_type.startswith('image/'):
                    uploaded_files_info += f"{i}. Изображение: {filename} (включено в сообщение)\n"
                elif file_type == 'application/pdf' and 'text' in file:
                    uploaded_files_info += f"{i}. PDF файл: {filename}\n   ⚠️ ТЕКСТ ФАЙЛА УЖЕ ВКЛЮЧЕН В СООБЩЕНИЕ НИЖЕ! Используй его напрямую, НЕ ищи файл в Google Диск!\n"
                else:
                    uploaded_files_info += f"{i}. Файл: {filename} (тип: {file_type})\n"
            uploaded_files_info += "\n⚠️ СНАЧАЛА используй информацию из загруженных файлов (текст уже в сообщении), ПОТОМ уже ищи дополнительные файлы в Google Диск!\n\n"
        
        # Read workspace folder configuration for context (PRIORITY #2)
        workspace_folder_info = None
        try:
            from src.utils.config_loader import get_config
            config = get_config()
            workspace_config_path = config.config_dir / "workspace_config.json"
            
            if workspace_config_path.exists():
                workspace_config = json.loads(workspace_config_path.read_text())
                folder_id = workspace_config.get("folder_id")
                folder_name = workspace_config.get("folder_name")
                if folder_id:
                    workspace_folder_info = f"""📁 GOOGLE ДИСК ПАПКА (ПРИОРИТЕТ #2):
⚠️ После анализа загруженных файлов, используй эту папку Google Диск:
  Название: {folder_name}
  ID: {folder_id}
  
  Используй соответствующие инструменты для работы с выбранной папкой, указывая folder_id={folder_id}
"""
        except Exception as e:
            logger.warning(f"[StepOrchestrator] Could not read workspace config: {e}")
        
        # Build context for this step
        # PRIORITY ORDER: 1) Uploaded files, 2) Google Drive folder, 3) Original request and plan
        step_context = ""
        if uploaded_files_info:
            step_context += uploaded_files_info + "\n"
        if workspace_folder_info:
            step_context += workspace_folder_info + "\n"
        # Escape user_request and plan_text to avoid f-string syntax errors
        escaped_user_request = _escape_braces_for_fstring(user_request)
        escaped_plan_text = _escape_braces_for_fstring(plan_text)# Use string concatenation instead of f-string to avoid issues
        step_context += "Оригинальный запрос: " + escaped_user_request + "\n\n"
        step_context += "Общий план: " + escaped_plan_text + "\n"
        
        step_context += """
Выполненные шаги:
"""
        for i, result in enumerate(previous_results, start=1):
            # Escape braces in result content to avoid f-string syntax errors
            result_title = _escape_braces_for_fstring(str(result['title']))
            result_content = _escape_braces_for_fstring(str(result['result']))
            # Use string concatenation instead of f-string to avoid issues
            step_context += "  " + str(i) + ". " + result_title + ": " + result_content + "\n"
        
        # Escape step_title to avoid f-string syntax errors
        escaped_step_title = _escape_braces_for_fstring(str(step_title))
        # Use string concatenation instead of f-string to avoid issues
        step_context += "\nТекущий шаг (" + str(step_index) + " из " + str(len(all_steps)) + "): " + escaped_step_title + "\n\n"
        step_context += "Выполни этот шаг. Предоставь четкий, конкретный ответ."

        # Build dynamic system prompt based on available capabilities
        system_prompt = build_step_executor_prompt(capabilities, workspace_folder_info)
        
        # Prepare messages with file attachments if any (files_data already loaded above)
        step_message = create_message_with_files(step_context, files_data)
        messages = [
            SystemMessage(content=system_prompt),
            step_message
        ]
        # Check if stop was requested before starting streaming
        if self._stop_requested:
            logger.info(f"[StepOrchestrator] Stop requested before step {step_index} execution")
            # Выбросить исключение, чтобы прервать выполнение цикла шагов
            from src.utils.exceptions import AgentError
            raise AgentError("Выполнение остановлено пользователем")
        
        # Stream the response with thinking
        accumulated_thinking = ""
        accumulated_response = ""
        
        try:
            # Создать задачу для стриминга, чтобы можно было её отменить
            async def stream_step():
                nonlocal accumulated_thinking, accumulated_response
                # Stream the response with thinking support
                # LangChain ChatAnthropic with thinking enabled streams thinking and text separately
                # Use llm_with_tools to enable tool calling
                # Collect all chunks to handle tool calls
                all_chunks = []
                async for chunk in self.llm_with_tools.astream(messages):
                    if self._stop_requested:
                        break
                    all_chunks.append(chunk)
                    
                    # Process chunk - chunks are AIMessageChunk objects
                    if hasattr(chunk, 'content'):
                        content = chunk.content
                        
                        # Handle list of content blocks (Claude format with thinking)
                        if isinstance(content, list):
                            for block in content:
                                # Handle both dict and object formats
                                block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                                
                                if block_type == "thinking":
                                    # For thinking blocks, text is in 'thinking' key, not 'text'!
                                    thinking_text = block.get("thinking", "") if isinstance(block, dict) else getattr(block, "thinking", "")
                                    if thinking_text:
                                        # #region agent log
                                        import time
                                        try:
                                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"step_orchestrator.py:_execute_step:thinking_chunk","message":"Thinking chunk received","data":{"thinking_length":len(thinking_text),"accumulated_length_before":len(accumulated_thinking),"step":step_index},"timestamp":int(time.time()*1000)})+'\n')
                                        except: pass
                                        # #endregion
                                        accumulated_thinking += thinking_text
                                        # #region agent log
                                        try:
                                            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"J","location":"step_orchestrator.py:_execute_step:thinking_chunk_after","message":"Thinking chunk added","data":{"accumulated_length_after":len(accumulated_thinking)},"timestamp":int(time.time()*1000)})+'\n')
                                        except: pass
                                        # #endregion
                                        # Send thinking chunk
                                        await self.ws_manager.send_event(
                                            self.session_id,
                                            "thinking_chunk",
                                            {"content": thinking_text}
                                        )
                                elif block_type == "text":
                                    # For text blocks, text is in 'text' key
                                    text_content = block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
                                    if text_content:
                                        accumulated_response += text_content
                                        # Send response chunk
                                        await self.ws_manager.send_event(
                                            self.session_id,
                                            "response_chunk",
                                            {"content": text_content}
                                        )
                        # Handle string content (fallback)
                        elif isinstance(content, str) and content:
                            accumulated_response += content
                            await self.ws_manager.send_event(
                                self.session_id,
                                "response_chunk",
                                {"content": content}
                            )
                    # Fallback: if chunk doesn't have content attribute, try to extract text
                    elif hasattr(chunk, 'text'):
                        text = chunk.text
                        if text:
                            accumulated_response += text
                            await self.ws_manager.send_event(
                                self.session_id,
                                "response_chunk",
                                {"content": text}
                            )
                    else:
                        # Last resort: convert to string
                        chunk_str = str(chunk)
                        if chunk_str and chunk_str not in ['', 'None']:
                            accumulated_response += chunk_str
                            await self.ws_manager.send_event(
                                self.session_id,
                                "response_chunk",
                                {"content": chunk_str}
                            )
            
            # Запустить задачу и сохранить ссылку
            self._streaming_task = asyncio.create_task(stream_step())
            
            try:
                await self._streaming_task
            except asyncio.CancelledError:
                logger.info(f"[StepOrchestrator] Step {step_index} streaming cancelled")
                if self._stop_requested:
                    # Выбросить исключение, чтобы прервать выполнение цикла шагов
                    from src.utils.exceptions import AgentError
                    raise AgentError("Выполнение остановлено пользователем")
                raise
            finally:
                self._streaming_task = None
            
            # Check if stop was requested after streaming
            if self._stop_requested:
                logger.info(f"[StepOrchestrator] Stop requested after step {step_index} streaming")
                # Выбросить исключение, чтобы прервать выполнение цикла шагов
                from src.utils.exceptions import AgentError
                raise AgentError("Выполнение остановлено пользователем")
            
            logger.info(f"[StepOrchestrator] Step {step_index} completed, response length: {len(accumulated_response)}")
            
            # After streaming, check if we need to execute tools
            # Get full response to check for tool calls
            try:
                full_response = await self.llm_with_tools.ainvoke(messages)
                
                if hasattr(full_response, 'tool_calls') and full_response.tool_calls:
                    # Execute tool calls
                    from langchain_core.messages import ToolMessage
                    tool_messages = []
                    for tool_call in full_response.tool_calls:
                        tool_name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
                        tool_args = tool_call.get("args") if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
                        tool_id = tool_call.get("id") if isinstance(tool_call, dict) else getattr(tool_call, "id", None)
                        
                        if tool_name:
                            # Find and execute tool
                            tool = next((t for t in self.tools if t.name == tool_name), None)
                            if tool:
                                try:
                                    result = await tool.ainvoke(tool_args)
                                    tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_id or tool_name))
                                    accumulated_response += f"\n\nРезультат инструмента {tool_name}: {result}\n"
                                except Exception as e:
                                    logger.error(f"[StepOrchestrator] Tool {tool_name} execution failed: {e}")
                                    tool_messages.append(ToolMessage(content=f"Ошибка: {str(e)}", tool_call_id=tool_id or tool_name))
                    
                    # If we have tool results, call LLM again with tool results
                    if tool_messages:
                        messages_with_tools = messages + [full_response] + tool_messages
                        final_response = await self.llm_with_tools.ainvoke(messages_with_tools)
                        if hasattr(final_response, 'content'):
                            final_text = final_response.content
                            if final_text and final_text not in accumulated_response:
                                accumulated_response += final_text
            except Exception as e:
                logger.error(f"[StepOrchestrator] Error checking/executing tool calls: {e}")
            
            # Check if response contains user assistance request
            assistance_request = self._parse_assistance_request(accumulated_response)
            
            if assistance_request:
                # Pause execution and request user assistance
                await self._request_user_assistance(assistance_request, step_index, context)
                # Wait for user response
                await self._wait_for_user_assistance()
                # Get selected option and continue
                if self._user_assistance_result:
                    selected_option = self._user_assistance_result
                    # Add selected option context to response for continuation
                    accumulated_response += f"\n\nВыбранный вариант пользователем: {selected_option.get('label', '')}\n"
                    if 'data' in selected_option:
                        accumulated_response += f"Данные выбора: {json.dumps(selected_option['data'], ensure_ascii=False)}\n"
            
            return accumulated_response
            
        except Exception as e:
            logger.error(f"[StepOrchestrator] Error streaming step {step_index}: {e}")
            # Escape braces in error message to avoid f-string syntax errors
            error_str = str(e)
            escaped_error_str = _escape_braces_for_fstring(error_str)
            # Use .format() instead of f-string to avoid issues with escaped content
            error_msg = "Error executing step: {error}".format(error=escaped_error_str)
            await self.ws_manager.send_event(
                self.session_id,
                "error",
                {"message": "Error executing step: {error}".format(error=error_str)}  # Use original for event, not escaped
            )
            raise
    
    async def _generate_final_result(
        self,
        user_request: str,
        plan_text: str,
        step_results: List[Dict[str, Any]],
        context: ConversationContext
    ) -> None:
        """
        Generate and stream final result summary after all steps are completed.
        Results are sent via WebSocket events (final_result_start, final_result_chunk, final_result_complete).
        
        Args:
            user_request: Original user request
            plan_text: Overall plan description
            step_results: Results from all executed steps
            context: Conversation context
        """
        # Build summary of all steps - format as context data without step numbering
        # This prevents the model from copying "Шаг N:" format into the final answer
        steps_summary = ""
        for step_result in step_results:
            step_content = step_result.get("result", "")
            # Extract slice outside f-string to avoid syntax errors
            step_content_preview = step_content[:1000] if len(step_content) > 1000 else step_content
            # Escape braces in content BEFORE checking length to avoid f-string syntax errors
            escaped_step_content = _escape_braces_for_fstring(str(step_content_preview))
            # Build lines using string concatenation (NOT f-string) to avoid issues with trailing braces and ellipsis
            # Don't include "Шаг N:" or "Результат:" - just the content
            if len(step_content) > 1000:
                # Use string concatenation to safely add ellipsis without f-string parsing issues
                result_line = escaped_step_content + "...\n\n"
            else:
                result_line = escaped_step_content + "\n\n"
            steps_summary += result_line# Create prompt for final result generation
        system_prompt = """Ты эксперт по созданию финальных ответов пользователям. Создай прямой и информативный ответ на исходный запрос пользователя.

⚠️ ВАЖНО: ВСЕ ответы должны быть на РУССКОМ языке! ⚠️

Твоя задача:
1. Проанализировать исходный запрос пользователя
2. Использовать предоставленные данные как контекст для формирования ответа
3. Создать понятный финальный ответ, который напрямую отвечает на запрос пользователя
4. НЕ упоминай шаги выполнения, попытки, инструменты или процесс работы
5. НЕ создавай отчет о выполнении - создай именно ответ на запрос

Формат ответа:
- Используй Markdown для форматирования (жирный текст **текст**, списки, эмодзи и т.д.)
- Прямой ответ на запрос пользователя
- Ключевая информация, которая была запрошена
- Если нужно, структурируй информацию для удобства чтения (используй списки, заголовки, выделение)

Будь конкретным, информативным и отвечай именно на то, что спросил пользователь."""

        # Escape all content to avoid f-string syntax errors
        escaped_user_request = _escape_braces_for_fstring(user_request)
        escaped_plan_text = _escape_braces_for_fstring(plan_text)
        escaped_steps_summary = _escape_braces_for_fstring(steps_summary)
        # Use .format() instead of f-string to avoid issues with escaped content containing {...}
        user_prompt = """Исходный запрос пользователя: {user_request}

Данные, полученные в результате выполнения запроса:
{steps_summary}

Создай финальный ответ пользователю, который напрямую отвечает на его запрос. Используй предоставленные данные для формирования ответа. НЕ упоминай процесс выполнения, шаги или технические детали - просто ответь на запрос.""".format(
            user_request=escaped_user_request,
            steps_summary=escaped_steps_summary
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            # Send final_result_start event
            await self.ws_manager.send_event(
                self.session_id,
                "final_result_start",
                {}
            )
            
            # Stream final result using LLM
            accumulated_result = ""
            async for chunk in self.llm.astream(messages):
                if self._stop_requested:
                    break
                
                # Extract text content from chunk
                if hasattr(chunk, 'content'):
                    content = chunk.content
                    
                    # Handle list of content blocks (Claude format)
                    if isinstance(content, list):
                        for block in content:
                            block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                            
                            if block_type == "text":
                                # Extract text from text blocks
                                text_content = block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
                                if text_content:
                                    accumulated_result += text_content
                                    # Send chunk
                                    await self.ws_manager.send_event(
                                        self.session_id,
                                        "final_result_chunk",
                                        {"content": accumulated_result}
                                    )
                    # Handle string content (fallback)
                    elif isinstance(content, str) and content:
                        accumulated_result += content
                        await self.ws_manager.send_event(
                            self.session_id,
                            "final_result_chunk",
                            {"content": accumulated_result}
                        )
                # Fallback: if chunk has text attribute
                elif hasattr(chunk, 'text'):
                    text = chunk.text
                    if text:
                        accumulated_result += text
                        await self.ws_manager.send_event(
                            self.session_id,
                            "final_result_chunk",
                            {"content": accumulated_result}
                        )
            
            final_result = accumulated_result.strip()
            logger.info(f"[StepOrchestrator] Generated and streamed final result, length: {len(final_result)}")
            
            # Send final_result_complete event
            await self.ws_manager.send_event(
                self.session_id,
                "final_result_complete",
                {"content": final_result}
            )
            
        except Exception as e:
            logger.error(f"[StepOrchestrator] Error generating final result: {e}")
            # Fallback: create simple final answer from step results
            # Combine all step results into a single answer without step numbering
            combined_results = []
            for r in step_results:
                r_result = r.get('result', '')
                if r_result and r_result.strip():
                    # Take first 300 chars of each result to avoid too long fallback
                    r_result_preview = r_result[:300] if len(r_result) > 300 else r_result
                    escaped_r_result = _escape_braces_for_fstring(str(r_result_preview))
                    combined_results.append(escaped_r_result)
            
            # Join results with newlines, add ellipsis if truncated
            results_text = "\n\n".join(combined_results)
            if any(len(r.get('result', '')) > 300 for r in step_results):
                results_text += "\n\n..."
            
            # Send fallback result
            fallback_result = results_text if results_text.strip() else "Запрос выполнен."
            await self.ws_manager.send_event(
                self.session_id,
                "final_result_start",
                {}
            )
            await self.ws_manager.send_event(
                self.session_id,
                "final_result_complete",
                {"content": fallback_result}
            )
    
    def confirm_plan(self) -> None:
        """
        Confirm the pending plan for execution.
        Should be called when user approves the plan.
        """
        logger.info(f"[StepOrchestrator] Plan confirmed for session {self.session_id}")
        self._confirmation_result = True
        if self._confirmation_event:
            self._confirmation_event.set()
    
    def reject_plan(self) -> None:
        """
        Reject the pending plan.
        Should be called when user rejects the plan.
        """
        logger.info(f"[StepOrchestrator] Plan rejected for session {self.session_id}")
        self._confirmation_result = False
        if self._confirmation_event:
            self._confirmation_event.set()
    
    def get_confirmation_id(self) -> Optional[str]:
        """
Get the confirmation ID for the current plan."""
        return self._confirmation_id
    
    def update_pending_plan(self, updated_plan: Dict[str, Any]) -> None:
        """
        Update the pending plan before execution.
        
        Args:
            updated_plan: Dictionary with "plan" (text) and "steps" (list of step titles)
        """
        logger.info(f"[StepOrchestrator] Updating pending plan for session {self.session_id}")
        self._plan_text = updated_plan.get("plan", self._plan_text)
        self._plan_steps = updated_plan.get("steps", self._plan_steps)
        
        # Send updated plan event to frontend
        asyncio.create_task(
            self.ws_manager.send_event(
                self.session_id,
                "plan_updated",
                {
                    "plan": self._plan_text,
                    "steps": self._plan_steps,
                    "confirmation_id": self._confirmation_id
                }
            )
        )
    
    def resolve_user_assistance(self, assistance_id: str, user_response: str) -> None:
        """
        Resolve a user assistance request with user's response.
        Parses the response and finds the selected option.
        
        Args:
            assistance_id: Assistance request ID
            user_response: User's response text (can be number, ordinal, label, etc.)
        """
        # #region agent log
        import time
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C,D","location":"step_orchestrator.py:resolve_user_assistance:entry","message":"resolve_user_assistance called","data":{"assistance_id":assistance_id,"user_response":user_response,"current_assistance_id":self._user_assistance_id,"has_options":self._user_assistance_options is not None,"options_count":len(self._user_assistance_options) if self._user_assistance_options else 0},"timestamp":int(time.time()*1000)})+'\n')
        except: pass
        # #endregion
        
        if self._user_assistance_id != assistance_id:
            logger.warning(f"[StepOrchestrator] Assistance ID mismatch: expected {self._user_assistance_id}, got {assistance_id}")
            return
        
        if not self._user_assistance_options:
            logger.warning(f"[StepOrchestrator] No options available for assistance request {assistance_id}")
            return
        
        # Parse user response to find selected option
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"step_orchestrator.py:resolve_user_assistance:before_parse","message":"Before _parse_user_selection","data":{"user_response":user_response,"options":self._user_assistance_options},"timestamp":int(time.time()*1000)})+'\n')
        except: pass
        # #endregion
        
        selected_option = self._parse_user_selection(user_response, self._user_assistance_options)
        
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"step_orchestrator.py:resolve_user_assistance:after_parse","message":"After _parse_user_selection","data":{"selected_option":selected_option},"timestamp":int(time.time()*1000)})+'\n')
        except: pass
        # #endregion
        
        if not selected_option:
            logger.warning(f"[StepOrchestrator] Could not parse user selection from response: {user_response}")
            # Try to use first option as fallback
            selected_option = self._user_assistance_options[0] if self._user_assistance_options else None
        
        if selected_option:
            logger.info(f"[StepOrchestrator] User assistance resolved for session {self.session_id}, selected option: {selected_option.get('id', 'unknown')}")
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"step_orchestrator.py:resolve_user_assistance:before_set_result","message":"Before setting result and event","data":{"selected_option_id":selected_option.get('id'),"has_event":self._user_assistance_event is not None},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            
            self._user_assistance_result = selected_option
            if self._user_assistance_event:
                self._user_assistance_event.set()
                
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"step_orchestrator.py:resolve_user_assistance:after_set_result","message":"After setting result and event","data":{},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
        else:
            logger.error(f"[StepOrchestrator] No option selected for assistance request {assistance_id}")
    
    def get_user_assistance_id(self) -> Optional[str]:
        """
        Get the current user assistance request ID.
        
        Returns:
            Assistance ID or None if no pending request
        """
        return self._user_assistance_id
    
    def _parse_assistance_request(self, step_result: str) -> Optional[Dict[str, Any]]:
        """
        Parse user assistance request from LLM response.
        Supports both JSON and text formats.
        
        Args:
            step_result: Step execution result text
            
        Returns:
            Parsed assistance request dict or None if not found
        """
        if "🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ" not in step_result:
            return None
        
        try:
            # Try to extract JSON block first - improved regex to match nested JSON
            # Pattern: { "🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ": { ... } }
            # Find ALL JSON blocks with the marker
            json_blocks = []
            marker_pos = step_result.find('🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ')
            while marker_pos != -1:
                # Find the opening brace before the marker
                start_pos = step_result.rfind('{', 0, marker_pos)
                if start_pos != -1:
                    # Find the matching closing brace
                    brace_count = 0
                    end_pos = start_pos
                    for i in range(start_pos, len(step_result)):
                        if step_result[i] == '{':
                            brace_count += 1
                        elif step_result[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i + 1
                                break
                    
                    if end_pos > start_pos:
                        json_blocks.append((start_pos, end_pos))
                
                # Find next marker
                marker_pos = step_result.find('🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ', marker_pos + 1)
            
            # Use the FIRST (and should be only) JSON block
            if json_blocks:
                start_pos, end_pos = json_blocks[0]
                json_str = step_result[start_pos:end_pos]
                
                # Clean up the JSON - remove emoji from key if needed
                json_str = json_str.replace('"🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ"', '"user_assistance_request"')
                json_str = json_str.replace("'🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ'", '"user_assistance_request"')
                
                try:
                    data = json.loads(json_str)
                    assistance_data = data.get("user_assistance_request") or data.get("🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ")
                    if assistance_data and isinstance(assistance_data, dict):
                        # Ensure options is a list and deduplicate by id
                        options_list = assistance_data.get("options", [])
                        if isinstance(options_list, list):
                            # Deduplicate options by id
                            seen_ids = set()
                            unique_options = []
                            for opt in options_list:
                                opt_id = str(opt.get("id", ""))
                                if opt_id and opt_id not in seen_ids:
                                    seen_ids.add(opt_id)
                                    unique_options.append(opt)
                            
                            return {
                                "question": assistance_data.get("question", ""),
                                "options": unique_options,
                                "context": assistance_data.get("context", {})
                            }
                except json.JSONDecodeError as e:
                    logger.debug(f"[StepOrchestrator] Failed to parse JSON: {e}")
            
            # Fallback to regex if brace matching failed
            json_match = re.search(r'\{\s*["\']🔍\s*ЗАПРОС\s*ПОМОЩИ\s*ПОЛЬЗОВАТЕЛЯ["\']\s*:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})\s*\}', step_result, re.DOTALL | re.IGNORECASE)
            if not json_match:
                # Try simpler pattern
                json_match = re.search(r'\{\s*["\']?🔍\s*ЗАПРОС\s*ПОМОЩИ\s*ПОЛЬЗОВАТЕЛЯ["\']?\s*:\s*(\{.*?\})\s*\}', step_result, re.DOTALL | re.IGNORECASE)
            
            if json_match:
                # Try to extract the full JSON object
                # Find the complete JSON block from { to matching }
                start_pos = step_result.find('{', step_result.find('🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ'))
                if start_pos != -1:
                    brace_count = 0
                    end_pos = start_pos
                    for i in range(start_pos, len(step_result)):
                        if step_result[i] == '{':
                            brace_count += 1
                        elif step_result[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = i + 1
                                break
                    
                    if end_pos > start_pos:
                        json_str = step_result[start_pos:end_pos]
                        # Clean up the JSON - remove emoji from key if needed
                        json_str = json_str.replace('"🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ"', '"user_assistance_request"')
                        json_str = json_str.replace("'🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ'", '"user_assistance_request"')
                        try:
                            data = json.loads(json_str)
                            assistance_data = data.get("user_assistance_request") or data.get("🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ")
                            if assistance_data and isinstance(assistance_data, dict):
                                # Ensure options is a list and deduplicate by id
                                options_list = assistance_data.get("options", [])
                                # #region agent log
                                try:
                                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"K","location":"step_orchestrator.py:_parse_assistance_request:before_dedup","message":"Before deduplication","data":{"options_count":len(options_list) if isinstance(options_list, list) else 0,"options_preview":[{"id":opt.get("id"),"label":opt.get("label","")[:50]} for opt in (options_list[:5] if isinstance(options_list, list) else [])]},"timestamp":int(time.time()*1000)})+'\n')
                                except: pass
                                # #endregion
                                if isinstance(options_list, list):
                                    # Deduplicate options by id
                                    seen_ids = set()
                                    unique_options = []
                                    for opt in options_list:
                                        opt_id = str(opt.get("id", ""))
                                        if opt_id and opt_id not in seen_ids:
                                            seen_ids.add(opt_id)
                                            unique_options.append(opt)
                                    
                                    # #region agent log
                                    try:
                                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"K","location":"step_orchestrator.py:_parse_assistance_request:after_dedup","message":"After deduplication","data":{"unique_options_count":len(unique_options),"unique_ids":list(seen_ids),"option_labels_preview":[opt.get("label","")[:80] for opt in unique_options[:5]]},"timestamp":int(time.time()*1000)})+'\n')
                                    except: pass
                                    # #endregion
                                    
                                    return {
                                        "question": assistance_data.get("question", ""),
                                        "options": unique_options,
                                        "context": assistance_data.get("context", {})
                                    }
                        except json.JSONDecodeError as e:
                            logger.debug(f"[StepOrchestrator] Failed to parse JSON: {e}")
        except (AttributeError, Exception) as e:
            logger.debug(f"[StepOrchestrator] Failed to parse JSON assistance request: {e}")
        
        # Fallback: parse text format
        try:
            # Extract question
            question_match = re.search(r'Вопрос:\s*(.+?)(?:\n|Варианты:)', step_result, re.IGNORECASE | re.DOTALL)
            question = question_match.group(1).strip() if question_match else "Требуется выбор варианта"
            
            # Extract options (numbered list)
            options = []
            option_pattern = r'(\d+)\.\s*(.+?)(?=\n\d+\.|\nУкажите|$)'
            option_matches = re.finditer(option_pattern, step_result, re.MULTILINE | re.DOTALL)
            
            for match in option_matches:
                option_id = match.group(1)
                option_label = match.group(2).strip()
                options.append({
                    "id": option_id,
                    "label": option_label,
                    "description": "",
                    "data": {}
                })
            
            if options:
                return {
                    "question": question,
                    "options": options,
                    "context": {}
                }
        except Exception as e:
            logger.debug(f"[StepOrchestrator] Failed to parse text assistance request: {e}")
        
        return None
    
    async def _request_user_assistance(
        self,
        assistance_request: Dict[str, Any],
        step_index: int,
        context: ConversationContext
    ) -> None:
        """
        Request user assistance by pausing execution and sending event.
        
        Args:
            assistance_request: Parsed assistance request with question and options
            step_index: Current step index
            context: Conversation context
        """
        self._user_assistance_id = str(uuid4())
        self._user_assistance_event = asyncio.Event()
        self._user_assistance_result = None
        self._user_assistance_context = {
            "step": step_index,
            **assistance_request.get("context", {})
        }
        self._user_assistance_options = assistance_request.get("options", [])
        
        # Send user assistance request event
        await self.ws_manager.send_event(
            self.session_id,
            "user_assistance_request",
            {
                "assistance_id": self._user_assistance_id,
                "question": assistance_request.get("question", "Требуется выбор варианта"),
                "options": self._user_assistance_options,
                "context": self._user_assistance_context
            }
        )
        
        logger.info(f"[StepOrchestrator] User assistance requested for session {self.session_id}, step {step_index}")
    
    async def _wait_for_user_assistance(self) -> None:
        """
        Wait for user to provide assistance response.
        Similar to confirmation wait logic.
        """
        # #region agent log
        import time
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"G","location":"step_orchestrator.py:_wait_for_user_assistance:entry","message":"_wait_for_user_assistance called","data":{"has_event":self._user_assistance_event is not None,"event_is_set":self._user_assistance_event.is_set() if self._user_assistance_event else None},"timestamp":int(time.time()*1000)})+'\n')
        except: pass
        # #endregion
        
        if not self._user_assistance_event:
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"G","location":"step_orchestrator.py:_wait_for_user_assistance:no_event","message":"No event, returning early","data":{},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            return
        
        confirmation_timeout = 300  # 5 minutes timeout
        start_time = time.time()
        
        try:
            while not self._user_assistance_event.is_set():
                elapsed = time.time() - start_time
                
                # #region agent log
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"G","location":"step_orchestrator.py:_wait_for_user_assistance:waiting","message":"Waiting for user assistance","data":{"elapsed":elapsed,"stop_requested":self._stop_requested,"event_is_set":self._user_assistance_event.is_set()},"timestamp":int(time.time()*1000)})+'\n')
                except: pass
                # #endregion
                
                if self._stop_requested:
                    logger.info(f"[StepOrchestrator] Stop requested during user assistance wait")
                    break
                
                if elapsed > confirmation_timeout:
                    logger.warning(f"[StepOrchestrator] User assistance timeout for session {self.session_id}")
                    await self.ws_manager.send_event(
                        self.session_id,
                        "error",
                        {"message": "User assistance timeout. Execution cancelled."}
                    )
                    # Reset assistance state
                    self._user_assistance_event = None
                    self._user_assistance_result = None
                    self._user_assistance_id = None
                    return
                
                try:
                    await asyncio.wait_for(
                        self._user_assistance_event.wait(),
                        timeout=0.5  # Check every 0.5 seconds
                    )
                    # #region agent log
                    try:
                        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"G","location":"step_orchestrator.py:_wait_for_user_assistance:event_set","message":"Event was set, breaking loop","data":{},"timestamp":int(time.time()*1000)})+'\n')
                    except: pass
                    # #endregion
                    break
                except asyncio.TimeoutError:
                    # Continue checking _stop_requested
                    continue
        except Exception as e:
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"G","location":"step_orchestrator.py:_wait_for_user_assistance:exception","message":"Exception in _wait_for_user_assistance","data":{"error":str(e),"error_type":type(e).__name__},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            logger.error(f"[StepOrchestrator] Error waiting for user assistance: {e}")
            raise
    
    @staticmethod
    def _parse_user_selection(user_response: str, options: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Parse user's selection from their response.
        Supports multiple formats: numbers, ordinal words, option labels, option IDs.
        
        Args:
            user_response: User's response text
            options: List of available options
            
        Returns:
            Selected option dict or None if not found
        """
        if not user_response or not options:
            return None
        
        user_response = user_response.strip().lower()
        
        # Try to find by number (1, 2, 3, etc.)
        number_match = re.search(r'^(\d+)', user_response)
        if number_match:
            try:
                index = int(number_match.group(1)) - 1  # Convert to 0-based index
                if 0 <= index < len(options):
                    return options[index]
            except (ValueError, IndexError):
                pass
        
        # Try to find by ordinal words (первый, второй, etc.)
        ordinal_map = {
            "первый": 0, "первая": 0, "первое": 0, "first": 0,
            "второй": 1, "вторая": 1, "второе": 1, "second": 1,
            "третий": 2, "третья": 2, "третье": 2, "third": 2,
            "четвертый": 3, "четвертая": 3, "четвертое": 3, "fourth": 3,
            "пятый": 4, "пятая": 4, "пятое": 4, "fifth": 4,
        }
        for ordinal, index in ordinal_map.items():
            if ordinal in user_response and index < len(options):
                return options[index]
        
        # Try to find by option ID
        for option in options:
            option_id = str(option.get("id", "")).lower()
            if option_id == user_response:
                return option
        
        # Try to find by label (partial match)
        user_response_lower = user_response.lower()
        for option in options:
            label = str(option.get("label", "")).lower()
            if user_response_lower in label or label in user_response_lower:
                return option
        
        # Try to find by data fields (e.g., file_name, file_id)
        for option in options:
            data = option.get("data", {})
            for key, value in data.items():
                if isinstance(value, str) and user_response_lower in value.lower():
                    return option
        
        return None

