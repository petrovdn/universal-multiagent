"""
Step Orchestrator for multi-step execution with planning and confirmation.
Implements plan_and_confirm and plan_and_execute modes with streaming.
"""

from typing import Dict, Any, List, Optional, AsyncGenerator
import asyncio
import json
import re
from uuid import uuid4

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.language_models.chat_models import BaseChatModel

from src.core.context_manager import ConversationContext
from src.api.websocket_manager import WebSocketManager
from src.agents.model_factory import create_llm
from src.utils.logging_config import get_logger

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
        
        logger.info(f"[StepOrchestrator] Initialized for session {session_id} with model {model_name or 'default'}")
    
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
        context: ConversationContext
    ) -> Dict[str, Any]:
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
            plan_result = await self._generate_plan(user_request, context)
            
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
                        context
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
        context: ConversationContext
    ) -> Dict[str, Any]:
        """
        Generate detailed execution plan using Claude.
        
        Args:
            user_request: User's request
            context: Conversation context
            
        Returns:
            Dict with "plan" (text) and "steps" (list of step titles)
        """
        system_prompt = """You are an expert planning assistant. Your task is to create a detailed, step-by-step execution plan for the user's request.

Requirements:
1. Break down the request into clear, actionable steps
2. Each step should be specific and executable
3. Steps should be ordered logically
4. Provide a clear plan description and numbered step titles

Format your response as JSON:
{
    "plan": "Detailed plan description explaining the overall approach",
    "steps": ["Step 1 title", "Step 2 title", "Step 3 title", ...]
}

Return ONLY valid JSON, no additional text."""

        # Prepare messages
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Create a detailed execution plan for this request:\n\n{user_request}")
        ]
        
        # Add recent context messages if available
        recent_messages = context.get_recent_messages(5)
        for msg in recent_messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        
        try:
            # Call LLM to generate plan
            response = await self.llm.ainvoke(messages)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON response
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
            
            logger.info(f"[StepOrchestrator] Generated plan with {len(steps)} steps")
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
        context: ConversationContext
    ) -> str:
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
        # Build context for this step
        step_context = f"""
Original Request: {user_request}

Overall Plan: {plan_text}

Previous Steps Completed:
"""
        for i, result in enumerate(previous_results, start=1):
            step_context += f"  {i}. {result['title']}: {result['result']}\n"
        
        step_context += f"""
Current Step ({step_index} of {len(all_steps)}): {step_title}

Execute this step. Provide a clear, actionable response."""

        system_prompt = """You are an expert execution assistant. Execute the current step of the plan efficiently and accurately.

Requirements:
- Be specific and actionable
- Reference previous steps when relevant
- Complete the step thoroughly
- Provide clear results

All responses should be in Russian."""
        
        # Prepare messages
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=step_context)
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

