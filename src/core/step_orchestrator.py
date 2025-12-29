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

logger = get_logger(__name__)


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
        
        # Create LLM with extended thinking support
        self.llm = self._create_llm_with_thinking()
        
        # State for plan confirmation
        self._confirmation_event: Optional[asyncio.Event] = None
        self._confirmation_result: Optional[bool] = None
        self._plan_steps: List[str] = []
        self._plan_text: str = ""
        self._confirmation_id: Optional[str] = None
        self._stop_requested: bool = False
        
        logger.info(f"[StepOrchestrator] Initialized for session {session_id} with model {model_name or 'default'}")
    
    def stop(self):
        """Request stop of execution."""
        self._stop_requested = True
        logger.info(f"[StepOrchestrator] Stop requested for session {self.session_id}")
    
    def _create_llm_with_thinking(self) -> BaseChatModel:
        """Create LLM instance with extended thinking enabled."""
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
                    await asyncio.wait_for(
                        self._confirmation_event.wait(),
                        timeout=confirmation_timeout
                    )
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
                # Check if stop was requested
                if self._stop_requested:
                    logger.info(f"[StepOrchestrator] Stop requested, stopping execution at step {step_index}")
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
                    # Send step_start event
                    await self.ws_manager.send_event(
                        self.session_id,
                        "step_start",
                        {
                            "step": step_index,
                            "title": step_title
                        }
                    )
                    
                    # Execute step with streaming
                    step_result = await self._execute_step(
                        step_index,
                        step_title,
                        user_request,
                        plan_text,
                        plan_steps,
                        step_results,
                        context,
                        file_ids
                    )
                    
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
                    
                except Exception as e:
                    logger.error(f"[StepOrchestrator] Error executing step {step_index}: {e}")
                    await self.ws_manager.send_event(
                        self.session_id,
                        "error",
                        {
                            "message": f"Error in step {step_index}: {str(e)}"
                        }
                    )
                    raise
            
            # Step 4: Send workflow_complete event
            await self.ws_manager.send_event(
                self.session_id,
                "workflow_complete",
                {}
            )
            
            logger.info(f"[StepOrchestrator] Workflow completed successfully")
            
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
            """Create HumanMessage with text and optional file attachments."""
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
                    # Append PDF text to the text content
                    content_parts[0]["text"] += f"\n\n[Содержимое файла {file.get('filename', 'document.pdf')}]:\n{file['text']}"
            
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
        
        # #region agent log
        log_data = json.dumps({"location": "step_orchestrator.py:_generate_plan", "message": "_generate_plan called", "data": {"user_request": user_request, "user_request_length": len(user_request), "user_request_preview": user_request[:200], "files_count": len(files_data)}, "timestamp": time.time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "DUPLICATE"}).encode('utf-8')
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'ab') as f:
            f.write(log_data + b'\n')
        # #endregion
        """
        Generate detailed execution plan using Claude.
        
        Args:
            user_request: User's request
            context: Conversation context
            
        Returns:
            Dict with "plan" (text) and "steps" (list of step titles)
        """
        # #region agent log
        log_data = json.dumps({"location": "step_orchestrator.py:_generate_plan", "message": "ENTRY: _generate_plan called", "data": {"user_request": user_request[:100], "user_request_length": len(user_request)}, "timestamp": time.time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}).encode('utf-8')
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'ab') as f:
            f.write(log_data + b'\n')
        # #endregion
        
        # Use dynamic planning prompt
        system_prompt = build_planning_prompt()

        # Prepare messages with file attachments if any
        # Include uploaded files info FIRST, then user request
        plan_request_text = uploaded_files_info + f"\n\nСоздай детальный план выполнения для этого запроса:\n\n{user_request}"
        user_message = create_message_with_files(plan_request_text, files_data)
        
        messages = [
            SystemMessage(content=system_prompt),
            user_message
        ]
        
        # #region agent log
        log_data = json.dumps({"location": "step_orchestrator.py:_generate_plan", "message": "BEFORE recent_messages: user_request added directly", "data": {"messages_count": len(messages), "last_message_preview": str(messages[-1].content)[:100]}, "timestamp": time.time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}).encode('utf-8')
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'ab') as f:
            f.write(log_data + b'\n')
        # #endregion
        
        # Add recent context messages if available, but skip the last user message if it matches current user_request
        recent_messages = context.get_recent_messages(5)
        
        # #region agent log
        recent_msgs_preview = [{"role": m.get("role"), "content": m.get("content", "")[:200], "content_length": len(m.get("content", ""))} for m in recent_messages]
        log_data = json.dumps({"location": "step_orchestrator.py:_generate_plan", "message": "recent_messages retrieved", "data": {"recent_messages_count": len(recent_messages), "recent_messages": recent_msgs_preview, "user_request": user_request, "user_request_length": len(user_request)}, "timestamp": time.time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "DUPLICATE"}).encode('utf-8')
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'ab') as f:
            f.write(log_data + b'\n')
        # #endregion
        
        # Only add assistant messages from recent context for planning
        # Do NOT add previous user messages - they can cause confusion and message concatenation
        for msg in recent_messages:
            role = msg.get("role")
            content = msg.get("content", "")
            # #region agent log
            log_data = json.dumps({"location": "step_orchestrator.py:_generate_plan", "message": "Processing message from recent_messages", "data": {"role": role, "content": content[:200], "content_length": len(content), "user_request": user_request, "user_request_length": len(user_request)}, "timestamp": time.time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "DUPLICATE"}).encode('utf-8')
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'ab') as f:
                f.write(log_data + b'\n')
            # #endregion
            # Skip all user messages - we only want the current user_request in the prompt
            # This prevents message concatenation issues
            if role == "user":
                # #region agent log
                log_data = json.dumps({"location": "step_orchestrator.py:_generate_plan", "message": "SKIPPED user message from recent_messages (only current user_request is used)", "data": {"content_preview": content[:100]}, "timestamp": time.time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "DUPLICATE"}).encode('utf-8')
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'ab') as f:
                    f.write(log_data + b'\n')
                # #endregion
                continue
            elif role == "assistant":
                # Add assistant messages for context
                messages.append(AIMessage(content=content))
                # #region agent log
                log_data = json.dumps({"location": "step_orchestrator.py:_generate_plan", "message": "ADDED assistant message from recent_messages", "data": {"content_preview": content[:200], "content_length": len(content)}, "timestamp": time.time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "DUPLICATE"}).encode('utf-8')
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'ab') as f:
                    f.write(log_data + b'\n')
                # #endregion
        
        # #region agent log
        user_msgs_in_final = [str(m.content)[:100] for m in messages if isinstance(m, HumanMessage)]
        log_data = json.dumps({"location": "step_orchestrator.py:_generate_plan", "message": "FINAL messages prepared", "data": {"total_messages_count": len(messages), "user_messages_count": len(user_msgs_in_final), "user_messages_preview": user_msgs_in_final}, "timestamp": time.time() * 1000, "sessionId": "debug-session", "runId": "run1", "hypothesisId": "A"}).encode('utf-8')
        with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'ab') as f:
            f.write(log_data + b'\n')
        # #endregion
        
        try:
            # Stream LLM response with thinking
            accumulated_thinking = ""
            accumulated_response = ""
            
            async for chunk in self.llm.astream(messages):
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
            return {
                "plan": plan_text,
                "steps": steps
            }
            
        except Exception as e:
            logger.error(f"[StepOrchestrator] Error generating plan: {e}")
            # Fallback plan
            return {
                "plan": f"Execute: {user_request}",
                "steps": [f"Step 1: {user_request}"]
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
            """Create HumanMessage with text and optional file attachments."""
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
                    # Append PDF text to the text content
                    content_parts[0]["text"] += f"\n\n[Содержимое файла {file.get('filename', 'document.pdf')}]:\n{file['text']}"
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
        step_context += f"""Оригинальный запрос: {user_request}

Общий план: {plan_text}
"""
        
        step_context += """
Выполненные шаги:
"""
        for i, result in enumerate(previous_results, start=1):
            step_context += f"  {i}. {result['title']}: {result['result']}\n"
        
        step_context += f"""
Текущий шаг ({step_index} из {len(all_steps)}): {step_title}

Выполни этот шаг. Предоставь четкий, конкретный ответ."""

        # Build dynamic system prompt based on available capabilities
        system_prompt = build_step_executor_prompt(capabilities, workspace_folder_info)
        
        # Prepare messages with file attachments if any (files_data already loaded above)
        step_message = create_message_with_files(step_context, files_data)
        messages = [
            SystemMessage(content=system_prompt),
            step_message
        ]
        
        # Stream the response with thinking
        accumulated_thinking = ""
        accumulated_response = ""
        
        try:
            # Stream the response with thinking support
            # LangChain ChatAnthropic with thinking enabled streams thinking and text separately
            async for chunk in self.llm.astream(messages):
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
                                    accumulated_thinking += thinking_text
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
            
            logger.info(f"[StepOrchestrator] Step {step_index} completed, response length: {len(accumulated_response)}")
            return accumulated_response
            
        except Exception as e:
            logger.error(f"[StepOrchestrator] Error streaming step {step_index}: {e}")
            error_msg = f"Error executing step: {str(e)}"
            await self.ws_manager.send_event(
                self.session_id,
                "error",
                {"message": error_msg}
            )
            raise
    
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
        """Get the confirmation ID for the current plan."""
        return self._confirmation_id

