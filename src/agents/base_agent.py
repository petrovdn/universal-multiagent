"""
Base agent architecture using LangGraph.
Provides common functionality for all agents in the system.
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated, AsyncGenerator, Callable
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, AIMessageChunk, ToolMessage
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import StateGraph, END
from langgraph.prebuilt.tool_node import ToolNode
from langgraph.checkpoint.memory import MemorySaver
import operator
import asyncio
from uuid import UUID

from src.utils.config_loader import get_config
from src.utils.exceptions import AgentError
from src.utils.logging_config import get_logger
from src.core.context_manager import ConversationContext
from src.agents.model_factory import create_llm, get_model_info


class StreamEvent:
    """Event types for streaming."""
    TOKEN = "token"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    DONE = "done"
    ERROR = "error"


class StreamingCallbackHandler(AsyncCallbackHandler):
    """Callback handler for streaming LLM tokens, thinking tokens, and tool calls."""
    
    def __init__(self, event_callback: Optional[Callable] = None, logger=None):
        self.event_callback = event_callback
        self.logger = logger
        self.accumulated_text = ""
        self.accumulated_thinking = ""
        # Cache tool names by run_id for TOOL_RESULT events
        self._tool_name_cache: Dict[str, str] = {}
    
    async def on_llm_new_token(self, token: Any, **kwargs) -> None:
        """Called when a new token is generated."""
        # Handle different token formats
        token_text = ""
        if isinstance(token, str):
            token_text = token
        elif isinstance(token, list):
            # Handle list of content blocks (Claude format)
            for block in token:
                if isinstance(block, dict) and block.get("type") == "text":
                    token_text += block.get("text", "")
                elif hasattr(block, "text"):
                    token_text += block.text
        elif hasattr(token, "text"):
            token_text = token.text
        else:
            token_text = str(token)
        
        if self.logger and token_text:
            self.logger.debug(f"[StreamingCallback] New token: {repr(token_text[:50])}")
        
        if token_text:
            self.accumulated_text += token_text
            if self.event_callback:
                await self.event_callback(StreamEvent.TOKEN, {
                    "token": token_text,
                    "accumulated": self.accumulated_text
                })
    
    async def on_chat_model_stream(
        self,
        chunk: Any,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs
    ) -> None:
        """Called when a new chunk is streamed from the chat model."""
        if self.logger:
            self.logger.debug(f"[StreamingCallback] on_chat_model_stream called, chunk type: {type(chunk)}")
        
        # Handle Claude thinking tokens and text tokens
        if hasattr(chunk, "content"):
            content = chunk.content
            
            if self.logger:
                self.logger.debug(f"[StreamingCallback] Content type: {type(content)}")
            
            # Handle list of content blocks (Claude format)
            if isinstance(content, list):
                for block in content:
                    # Check if it's a thinking block
                    if hasattr(block, "type"):
                        if block.type == "thinking":
                            thinking_text = getattr(block, "text", "")
                            if thinking_text:
                                if self.logger:
                                    self.logger.info(f"[StreamingCallback] Thinking token: {thinking_text[:100]}")
                                self.accumulated_thinking += thinking_text
                                if self.event_callback:
                                    await self.event_callback(StreamEvent.THINKING, {
                                        "step": "reasoning",
                                        "message": self.accumulated_thinking
                                    })
                        elif block.type == "text":
                            text = getattr(block, "text", "")
                            if text:
                                if self.logger:
                                    self.logger.debug(f"[StreamingCallback] Text token: {text[:50]}")
                                self.accumulated_text += text
                                if self.event_callback:
                                    await self.event_callback(StreamEvent.TOKEN, {
                                        "token": text,
                                        "accumulated": self.accumulated_text
                                    })
            # Handle string content
            elif isinstance(content, str):
                if self.logger:
                    self.logger.debug(f"[StreamingCallback] String token: {content[:50]}")
                self.accumulated_text += content
                if self.event_callback:
                    await self.event_callback(StreamEvent.TOKEN, {
                        "token": content,
                        "accumulated": self.accumulated_text
                    })
        # Also handle direct token strings (fallback)
        elif isinstance(chunk, str):
            if self.logger:
                self.logger.debug(f"[StreamingCallback] Direct string token: {chunk[:50]}")
            self.accumulated_text += chunk
            if self.event_callback:
                await self.event_callback(StreamEvent.TOKEN, {
                    "token": chunk,
                    "accumulated": self.accumulated_text
                })
    
    async def on_tool_start(
        self, 
        serialized: Dict[str, Any], 
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs
    ) -> None:
        """Called when a tool starts executing."""
        tool_name = serialized.get("name", "unknown")
        # Cache tool name for use in on_tool_end
        self._tool_name_cache[str(run_id)] = tool_name
        if self.logger:
            self.logger.info(f"[StreamingCallback] Tool start: {tool_name}")
        if self.event_callback:
            await self.event_callback(StreamEvent.TOOL_CALL, {
                "tool_name": tool_name,
                "arguments": input_str,
                "status": "starting",
                "run_id": str(run_id)
            })
    
    async def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs
    ) -> None:
        """Called when a tool finishes executing."""
        # #region agent log
        import json
        import time
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({
                    "location": "base_agent.py:on_tool_end:entry",
                    "message": "on_tool_end called",
                    "data": {
                        "run_id": str(run_id),
                        "output_length": len(str(output)) if output else 0,
                        "output_preview": str(output)[:200] if output else "",
                        "has_event_callback": self.event_callback is not None,
                        "tool_name_from_cache": self._tool_name_cache.get(str(run_id), "not_found")
                    },
                    "timestamp": int(time.time() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A"
                }) + "\n")
        except Exception as e:
            pass
        # #endregion
        
        if self.logger:
            self.logger.info(f"[StreamingCallback] Tool end: {output[:100] if output else 'empty'}")
        if self.event_callback:
            # Format output more compactly
            output_str = str(output)
            
            # For very long outputs, show summary
            if len(output_str) > 1000:
                # Try to extract key information
                lines = output_str.split('\n')
                if len(lines) > 20:
                    # Show first 10 lines and last 5 lines
                    summary = '\n'.join(lines[:10]) + '\n\n... (пропущено ' + str(len(lines) - 15) + ' строк) ...\n\n' + '\n'.join(lines[-5:])
                    display_output = summary[:2000] + "..." if len(summary) > 2000 else summary
                else:
                    display_output = output_str[:2000] + "..." if len(output_str) > 2000 else output_str
            else:
                display_output = output_str
            
            # Get tool name from cache
            tool_name = self._tool_name_cache.pop(str(run_id), "unknown")
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "location": "base_agent.py:on_tool_end:before_callback",
                        "message": "About to call event_callback with TOOL_RESULT",
                        "data": {
                            "run_id": str(run_id),
                            "tool_name": tool_name,
                            "display_output_length": len(display_output)
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A"
                    }) + "\n")
            except: pass
            # #endregion
            
            await self.event_callback(StreamEvent.TOOL_RESULT, {
                "result": display_output,
                "run_id": str(run_id),
                "tool_name": tool_name
            })
            
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({
                        "location": "base_agent.py:on_tool_end:after_callback",
                        "message": "event_callback called with TOOL_RESULT",
                        "data": {
                            "run_id": str(run_id),
                            "tool_name": tool_name
                        },
                        "timestamp": int(time.time() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "A"
                    }) + "\n")
            except: pass
            # #endregion
    
    def get_accumulated_text(self) -> str:
        """Get all accumulated text."""
        return self.accumulated_text
    
    def get_accumulated_thinking(self) -> str:
        """Get all accumulated thinking."""
        return self.accumulated_thinking


class AgentState(TypedDict):
    """State for LangGraph agent execution."""
    messages: Annotated[List[Any], operator.add]
    # Note: context and tools are not serializable by checkpointer
    # They are managed separately and not stored in checkpoint
    error: Optional[str]


class BaseAgent:
    """
    Base agent class using LangGraph.
    Provides common functionality for all specialized agents.
    """
    
    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: List[BaseTool],
        model_name: Optional[str] = None,
        llm: Optional[BaseChatModel] = None
    ):
        """
        Initialize base agent.
        
        Args:
            name: Agent name
            system_prompt: System prompt for the agent
            tools: List of tools available to the agent
            model_name: Model identifier (e.g., "claude-sonnet-4-5", "gpt-4o", "o1")
                       Uses default from config if None
            llm: Language model instance (creates from model_name if None)
        """
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.model_name = model_name
        self.llm = llm or self._create_llm()
        self.graph = self._build_graph()
        self.logger = get_logger(__name__)
    
    def _create_llm(self) -> BaseChatModel:
        """Create default LLM instance using model factory."""
        config = get_config()
        model_name = self.model_name or config.default_model
        
        # Get API keys from config
        api_keys = {
            "anthropic": config.anthropic_api_key,
            "openai": config.openai_api_key
        }
        
        return create_llm(model_name, api_keys)
    
    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph state graph for agent execution.
        
        Returns:
            Configured StateGraph
        """
        # LangChain's default prompt template format is "f-string".
        # Any literal braces in system prompts (e.g. "{...}") will be parsed as template variables.
        def _escape_langchain_fstring_template(text: str) -> str:
            return (text or "").replace("{", "{{").replace("}", "}}")

        escaped_system_prompt = _escape_langchain_fstring_template(self.system_prompt)

        # Create prompt template (use escaped system prompt)
        prompt = ChatPromptTemplate.from_messages([
            ("system", escaped_system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ])
        
        # Bind tools to LLM
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Create agent node with async support for streaming
        async def agent_node(state: AgentState):
            messages = state["messages"]
            response = prompt.invoke({"messages": messages})
            # Use ainvoke for async execution (callbacks are passed via config)
            response = await llm_with_tools.ainvoke(response.messages)
            return {"messages": [response]}
        
        # Create tool node
        tool_node = ToolNode(self.tools)
        
        # Build graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)
        
        # Add edges
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent",
            self._should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )
        workflow.add_edge("tools", "agent")
        
        # Compile graph
        # Temporarily disable checkpointer to avoid ConversationContext serialization issues
        # TODO: Implement custom serializer or use a different approach for state persistence
        # memory = MemorySaver()
        # compiled_graph = workflow.compile(checkpointer=memory)
        compiled_graph = workflow.compile()  # No checkpointer for now
        return compiled_graph
    
    def _should_continue(self, state: AgentState) -> str:
        """
        Determine if agent should continue or end.
        
        Args:
            state: Current agent state
            
        Returns:
            "continue" or "end"
        """
        messages = state["messages"]
        if not messages:
            return "end"
        
        last_message = messages[-1]
        
        # If last message has tool calls, continue
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "continue"
        
        # Check for tool_use (Anthropic format)
        if hasattr(last_message, "content") and isinstance(last_message.content, list):
            for item in last_message.content:
                if hasattr(item, "type") and item.type == "tool_use":
                    return "continue"
        
        return "end"
    
    async def execute(
        self,
        user_message: str,
        context: ConversationContext
    ) -> Dict[str, Any]:
        """
        Execute agent with user message.
        
        Args:
            user_message: User's message
            context: Conversation context
            
        Returns:
            Agent execution result
            
        Raises:
            AgentError: If execution fails
        """
        try:
            # Log entry point - use ERROR level to ensure we see it
            session_id_val = getattr(context, 'session_id', 'NOT SET')
            self.logger.error(f"[{self.name}] ===== STARTING EXECUTE =====")
            self.logger.error(f"[{self.name}] Context session_id: {session_id_val}")
            print(f"[DEBUG {self.name}] Starting execute method, session_id: {session_id_val}")
            
            # Prepare messages from context history
            # Convert context messages to LangChain message format
            langchain_messages = []
            
            # Get context messages - use context-aware method if available
            if hasattr(context, 'get_context_for_simple_task'):
                # Use method that returns appropriate depth for simple tasks (4 messages)
                recent_messages = context.get_context_for_simple_task()
                context_method = "get_context_for_simple_task"
            else:
                # Fallback to default method
                recent_messages = context.get_recent_messages(10)
                context_method = "get_recent_messages"
            
            # Add entity context if available (NEW)
            has_entity_context = False
            if hasattr(context, 'entity_memory') and context.entity_memory.has_recent_entities():
                entity_info = context.entity_memory.to_context_string()
                if entity_info:
                    langchain_messages.append(SystemMessage(
                        content=f"Контекст упомянутых объектов:\n{entity_info}"
                    ))
                    has_entity_context = True
            
            # Add open files context if available
            open_files_context = self._build_open_files_context(context)
            if open_files_context:
                # #region agent log
                import json
                import time
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"base_agent.py:execute:adding_open_files_context","message":"Adding open files context to messages","data":{"context_length":len(open_files_context)},"timestamp":int(time.time()*1000)})+'\n')
                except: pass
                # #endregion
                langchain_messages.append(SystemMessage(content=open_files_context))
            
            # Add recent messages from context
            for msg in recent_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    langchain_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    langchain_messages.append(AIMessage(content=content))
                elif role == "system":
                    langchain_messages.append(SystemMessage(content=content))
            
            # Add current user message if not already in context
            if not recent_messages or recent_messages[-1].get("content") != user_message:
                langchain_messages.append(HumanMessage(content=user_message))
            
            # Prepare initial state
            # Note: context and tools are not serializable by checkpointer
            # They are managed separately and not stored in checkpoint
            initial_state: AgentState = {
                "messages": langchain_messages,
                "error": None
            }
            
            # Execute graph
            # Note: Checkpointer is temporarily disabled to avoid ConversationContext serialization issues
            # Session management is handled separately via session_manager
            self.logger.error(f"[{self.name}] Executing graph (no checkpointer)")
            print(f"[DEBUG {self.name}] Executing graph without checkpointer")
            try:
                result = await self.graph.ainvoke(initial_state)
                self.logger.error(f"[{self.name}] ===== GRAPH EXECUTION SUCCESSFUL =====")
                print(f"[DEBUG {self.name}] Graph execution successful")
            except Exception as e:
                self.logger.error(f"[{self.name}] ===== GRAPH EXECUTION FAILED =====")
                self.logger.error(f"[{self.name}] Error: {e}")
                print(f"[DEBUG {self.name}] Graph execution failed: {e}")
                raise
            
            # Extract final message
            messages = result.get("messages", [])
            self.logger.error(f"[{self.name}] ===== EXTRACTING RESPONSE =====")
            self.logger.error(f"[{self.name}] Result messages count: {len(messages)}")
            self.logger.error(f"[{self.name}] Result keys: {list(result.keys())}")
            
            # Log all messages for debugging
            for i, msg in enumerate(messages):
                self.logger.error(f"[{self.name}] Message {i}: type={type(msg).__name__}, has_content={hasattr(msg, 'content')}")
                if hasattr(msg, "content"):
                    self.logger.error(f"[{self.name}] Message {i} content: {str(msg.content)[:100]}")
            
            final_message = messages[-1] if messages else None
            
            self.logger.error(f"[{self.name}] Final message is None: {final_message is None}")
            if final_message:
                self.logger.error(f"[{self.name}] Final message type: {type(final_message)}")
                self.logger.error(f"[{self.name}] Final message str: {str(final_message)[:200]}")
                if hasattr(final_message, "content"):
                    self.logger.error(f"[{self.name}] Final message content type: {type(final_message.content)}")
                    self.logger.error(f"[{self.name}] Final message content: {repr(final_message.content)[:300]}")
            
            # Extract content from final message
            response_text = "Задача выполнена, но ответ не был сформирован"
            if final_message:
                if hasattr(final_message, "content"):
                    # Handle both string and list content
                    content = final_message.content
                    self.logger.error(f"[{self.name}] Content extracted: type={type(content)}, value={repr(str(content)[:200])}")
                    if isinstance(content, list):
                        # Extract text from content blocks
                        text_parts = []
                        for block in content:
                            if hasattr(block, "text"):
                                text_parts.append(block.text)
                            elif isinstance(block, str):
                                text_parts.append(block)
                        response_text = " ".join(text_parts) if text_parts else str(content)
                        self.logger.error(f"[{self.name}] Extracted from list: {repr(response_text[:200])}")
                    else:
                        response_text = str(content)
                        self.logger.error(f"[{self.name}] Extracted from string: {repr(response_text[:200])}")
                elif isinstance(final_message, str):
                    response_text = final_message
                    self.logger.error(f"[{self.name}] Final message is string: {repr(response_text[:200])}")
                else:
                    response_text = str(final_message)
                    self.logger.error(f"[{self.name}] Final message converted to string: {repr(response_text[:200])}")
            
            self.logger.error(f"[{self.name}] ===== FINAL RESPONSE TEXT: {repr(response_text[:300])} =====")
            
            return {
                "agent": self.name,
                "response": response_text,
                "messages": messages
                # Note: context is not included in result to avoid serialization issues
            }
            
        except Exception as e:
            raise AgentError(
                f"Agent execution failed: {e}",
                agent_name=self.name
            ) from e
    
    def get_tools(self) -> List[BaseTool]:
        """Get list of available tools."""
        return self.tools
    
    def _build_open_files_context(self, context: ConversationContext) -> Optional[str]:
        """
        Build context string for currently open files in workspace panel.
        
        Args:
            context: Conversation context
            
        Returns:
            Context string or None if no open files
        """
        # #region agent log
        import json
        import time
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"base_agent.py:_build_open_files_context:entry","message":"Building open files context","data":{"context_has_get_open_files":hasattr(context,'get_open_files')},"timestamp":int(time.time()*1000)})+'\n')
        except: pass
        # #endregion
        
        open_files = context.get_open_files() if hasattr(context, 'get_open_files') else []
        
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"base_agent.py:_build_open_files_context:after_get","message":"Retrieved open_files from context","data":{"open_files_count":len(open_files) if open_files else 0,"open_files":open_files if open_files else []},"timestamp":int(time.time()*1000)})+'\n')
        except: pass
        # #endregion
        
        if not open_files:
            # #region agent log
            try:
                with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"base_agent.py:_build_open_files_context:no_files","message":"No open files found, returning None","data":{},"timestamp":int(time.time()*1000)})+'\n')
            except: pass
            # #endregion
            return None
        
        context_lines = ["## Открытые файлы в рабочей области:\n"]
        for i, file in enumerate(open_files, 1):
            file_type = file.get('type', 'unknown')
            title = file.get('title', 'Без названия')
            
            if file_type == 'sheets':
                spreadsheet_id = file.get('spreadsheet_id', 'N/A')
                url = file.get('url', '')
                context_lines.append(f"{i}. 📊 Таблица: {title}")
                context_lines.append(f"   ID: {spreadsheet_id}")
                if url:
                    context_lines.append(f"   URL: {url}")
            elif file_type == 'docs':
                document_id = file.get('document_id', 'N/A')
                url = file.get('url', '')
                context_lines.append(f"{i}. 📄 Документ: {title}")
                context_lines.append(f"   ID: {document_id}")
                if url:
                    context_lines.append(f"   URL: {url}")
            else:
                context_lines.append(f"{i}. {title} ({file_type})")
                if file.get('url'):
                    context_lines.append(f"   URL: {file.get('url')}")
        
        context_lines.append("\n🚫 КРИТИЧЕСКИ ВАЖНО:")
        context_lines.append("1. НИКОГДА не используй инструменты find_and_open_file, workspace_find_and_open_file или workspace_search_files для файлов из этого списка")
        context_lines.append("2. Если пользователь упоминает название файла из этого списка (например, 'Сказка', 'документ', 'таблица', 'этот файл'), используй ПРЯМО document_id/spreadsheet_id из списка выше")
        context_lines.append("3. НЕ создавай шаг 'Найти файл' в плане - файл УЖЕ открыт, просто используй его ID напрямую")
        context_lines.append("4. Если файл открыт, сразу переходи к выполнению действий с ним (read_document, read_sheet_data и т.д.)")
        context_lines.append("5. Шаг поиска файла должен отображаться ТОЛЬКО если файла НЕТ в этом списке открытых файлов")
        
        result_context = "\n".join(context_lines)
        
        # #region agent log
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"base_agent.py:_build_open_files_context:return","message":"Returning open files context","data":{"context_length":len(result_context),"context_preview":result_context[:200]},"timestamp":int(time.time()*1000)})+'\n')
        except: pass
        # #endregion
        
        return result_context

    async def execute_with_streaming(
        self,
        user_message: str,
        context: ConversationContext,
        event_callback: Optional[Callable[[str, Dict[str, Any]], Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute agent with streaming events using astream_events.
        Captures thinking tokens, regular tokens, and tool calls.
        
        Args:
            user_message: User's message
            context: Conversation context
            event_callback: Async callback for streaming events
            
        Returns:
            Agent execution result
        """
        try:
            session_id_val = getattr(context, 'session_id', 'NOT SET')
            self.logger.info(f"[{self.name}] Starting streaming execute, session_id: {session_id_val}")
            
            # Prepare messages from context history
            langchain_messages = []
            
            # Add open files context if available
            open_files_context = self._build_open_files_context(context)
            if open_files_context:
                # #region agent log
                import json
                import time
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"base_agent.py:execute_with_streaming:adding_open_files_context","message":"Adding open files context to messages","data":{"context_length":len(open_files_context)},"timestamp":int(time.time()*1000)})+'\n')
                except: pass
                # #endregion
                langchain_messages.append(SystemMessage(content=open_files_context))
            
            recent_messages = context.get_recent_messages(10)
            for msg in recent_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    langchain_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    langchain_messages.append(AIMessage(content=content))
                elif role == "system":
                    langchain_messages.append(SystemMessage(content=content))
            
            # Add current user message if not already in context
            if not recent_messages or recent_messages[-1].get("content") != user_message:
                langchain_messages.append(HumanMessage(content=user_message))
            
            # Prepare initial state
            initial_state: AgentState = {
                "messages": langchain_messages,
                "error": None
            }
            
            # Notify that we're starting
            if event_callback:
                await event_callback(StreamEvent.THINKING, {
                    "step": "starting",
                    "message": "Анализирую запрос..."
                })
            
            self.logger.info(f"[{self.name}] Starting graph execution with direct chunk processing")
            
            # Track accumulated text and thinking directly (no callback handler to avoid duplication)
            accumulated_text = ""
            accumulated_thinking = ""
            
            # Execute without callbacks - process chunks directly
            config = {"recursion_limit": 50}
            
            # Use astream to get streaming chunks
            all_messages = []
            chunk_count = 0
            
            self.logger.info(f"[{self.name}] Starting astream")
            self.logger.info(f"[{self.name}] Initial state messages count: {len(initial_state.get('messages', []))}")
            
            async for chunk in self.graph.astream(initial_state, config=config, stream_mode="messages"):
                chunk_count += 1
                
                # Handle different chunk formats
                if isinstance(chunk, tuple):
                    # (MessageChunk, metadata) format in messages mode
                    msg_chunk = chunk[0]
                    metadata = chunk[1] if len(chunk) > 1 else {}
                    # Only process AIMessage chunks - skip ToolMessage, HumanMessage, etc.
                    if not isinstance(msg_chunk, (AIMessage, AIMessageChunk)):
                        msg_type = type(msg_chunk).__name__
                        self.logger.debug(f"[{self.name}] Skipping non-AI message chunk: {msg_type}")
                        continue
                    
                    # Extract text from the message chunk
                    if hasattr(msg_chunk, "content"):
                        content = msg_chunk.content
                        if isinstance(content, list):
                            for block in content:
                                # Get block type - handle both dict and object formats
                                block_type = block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
                                if block_type == "thinking":
                                    # For thinking blocks, text is in 'thinking' key, not 'text'!
                                    thinking_text = block.get("thinking", "") if isinstance(block, dict) else getattr(block, "thinking", "")
                                    if thinking_text:
                                        self.logger.info(f"[{self.name}] THINKING block: {thinking_text[:100]}...")
                                        accumulated_thinking += thinking_text
                                        if event_callback:
                                            await event_callback(StreamEvent.THINKING, {
                                                "step": "reasoning",
                                                "message": accumulated_thinking
                                            })
                                elif block_type == "text":
                                    # For text blocks, text is in 'text' key
                                    text_content = block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
                                    if text_content:
                                        accumulated_text += text_content
                                        if event_callback:
                                            await event_callback(StreamEvent.TOKEN, {
                                                "token": text_content,
                                                "accumulated": accumulated_text
                                            })
                                elif block_type == "tool_use" or block_type == "input_json_delta":
                                    # Skip tool_use and input_json_delta blocks - these are not user-facing content
                                    # tool_use is for tool calls, input_json_delta is for streaming JSON input
                                    self.logger.debug(f"[{self.name}] Skipping {block_type} block (tool call data)")
                                else:
                                    # Log unknown block types for debugging
                                    self.logger.debug(f"[{self.name}] Unknown block type: {block_type}, block: {block}")
                        elif isinstance(content, str) and content:
                            accumulated_text += content
                            if event_callback:
                                await event_callback(StreamEvent.TOKEN, {
                                    "token": content,
                                    "accumulated": accumulated_text
                                })
                    
                    # Collect final message
                    all_messages.append(msg_chunk)
                    
                elif isinstance(chunk, dict):
                    if "messages" in chunk:
                        all_messages = chunk.get("messages", [])
            
            self.logger.info(f"[{self.name}] Finished streaming, total chunks: {chunk_count}, messages count: {len(all_messages)}")
            self.logger.info(f"[{self.name}] Streaming completed, text length: {len(accumulated_text)}, thinking length: {len(accumulated_thinking)}")
            
            # If no text accumulated via callback, extract from messages
            if not accumulated_text and all_messages:
                self.logger.warning(f"[{self.name}] No text accumulated via callback, extracting from messages")
                final_message = all_messages[-1] if all_messages else None
                if final_message and hasattr(final_message, "content"):
                    content = final_message.content
                    if isinstance(content, str):
                        accumulated_text = content
                    elif isinstance(content, list):
                        text_parts = []
                        thinking_parts = []
                        for item in content:
                            # Handle thinking blocks - note: text is in 'thinking' key!
                            if hasattr(item, "type") and item.type == "thinking":
                                thinking_text = getattr(item, "thinking", "") or getattr(item, "text", "")
                                if thinking_text:
                                    thinking_parts.append(thinking_text)
                            # Handle text blocks
                            elif hasattr(item, "text"):
                                text_parts.append(item.text)
                            elif isinstance(item, dict):
                                if item.get("type") == "thinking":
                                    # Thinking content is in 'thinking' key, not 'text'!
                                    thinking_parts.append(item.get("thinking", ""))
                                elif item.get("type") == "text":
                                    text_parts.append(item.get("text", ""))
                        accumulated_text = " ".join(text_parts)
                        if thinking_parts and not accumulated_thinking:
                            accumulated_thinking = " ".join(thinking_parts)
                            if event_callback:
                                await event_callback(StreamEvent.THINKING, {
                                    "step": "reasoning",
                                    "message": accumulated_thinking
                                })
            
            # If still no text, try to get from any message
            if not accumulated_text:
                self.logger.warning(f"[{self.name}] Still no text, checking all messages (count: {len(all_messages)})")
                for i, msg in enumerate(reversed(all_messages)):
                    self.logger.info(f"[{self.name}] Checking message {i}: type={type(msg).__name__}")
                    if hasattr(msg, "content"):
                        content = msg.content
                        self.logger.info(f"[{self.name}] Message content type: {type(content)}")
                        if isinstance(content, str) and content.strip():
                            accumulated_text = content
                            self.logger.info(f"[{self.name}] Found text in string content: {repr(content[:100])}")
                            break
                        elif isinstance(content, list):
                            self.logger.info(f"[{self.name}] Content is list, length: {len(content)}")
                            for j, item in enumerate(content):
                                self.logger.info(f"[{self.name}] Item {j}: type={type(item).__name__}, has_text={hasattr(item, 'text')}")
                                if hasattr(item, "text") and item.text and item.text.strip():
                                    accumulated_text = item.text
                                    self.logger.info(f"[{self.name}] Found text in item: {repr(accumulated_text[:100])}")
                                    break
                                elif isinstance(item, dict):
                                    item_text = item.get("text", "")
                                    if item_text and item_text.strip():
                                        accumulated_text = item_text
                                        self.logger.info(f"[{self.name}] Found text in dict item: {repr(accumulated_text[:100])}")
                                        break
                            if accumulated_text:
                                break
                    # Also try to convert message to string
                    elif not accumulated_text:
                        try:
                            msg_str = str(msg)
                            if msg_str and msg_str.strip() and len(msg_str) > 10:
                                accumulated_text = msg_str
                                self.logger.info(f"[{self.name}] Found text by converting message to string: {repr(accumulated_text[:100])}")
                                break
                        except:
                            pass
            
            # If we still don't have text but have messages, try one more time to extract
            if not accumulated_text and all_messages:
                self.logger.warning(f"[{self.name}] Final attempt to extract text from messages")
                # Get the last AI message
                for msg in reversed(all_messages):
                    if hasattr(msg, "content"):
                        content = msg.content
                        # Try to extract text from content
                        if isinstance(content, str):
                            if content.strip():
                                accumulated_text = content
                                break
                        elif isinstance(content, list):
                            # Extract all text blocks
                            text_blocks = []
                            for item in content:
                                if hasattr(item, "type"):
                                    if item.type == "text" and hasattr(item, "text"):
                                        text_blocks.append(item.text)
                                elif isinstance(item, dict) and item.get("type") == "text":
                                    text_blocks.append(item.get("text", ""))
                            if text_blocks:
                                accumulated_text = " ".join(text_blocks)
                                break
            
            response_text = accumulated_text if accumulated_text else "Извините, не удалось получить ответ от модели."
            
            self.logger.info(f"[{self.name}] Final response length: {len(response_text)}")
            self.logger.info(f"[{self.name}] Final response: {repr(response_text[:200])}")
            
            # If we have a response but no tokens were streamed, send it as a complete message
            if response_text and response_text != "Извините, не удалось получить ответ от модели." and not accumulated_text:
                self.logger.info(f"[{self.name}] Response found but not streamed, sending as complete message")
                if event_callback:
                    # Send as token chunks to simulate streaming
                    words = response_text.split()
                    for i, word in enumerate(words):
                        chunk = word + (" " if i < len(words) - 1 else "")
                        await event_callback(StreamEvent.TOKEN, {
                            "token": chunk,
                            "accumulated": " ".join(words[:i+1])
                        })
            
            # Always notify completion, even if response is empty
            if event_callback:
                self.logger.info(f"[{self.name}] Sending DONE event with response")
                await event_callback(StreamEvent.DONE, {
                    "response": response_text
                })
            else:
                self.logger.warning(f"[{self.name}] No event_callback, cannot send DONE event")
            
            return {
                "agent": self.name,
                "response": response_text,
                "messages": all_messages
            }
            
        except Exception as e:
            self.logger.error(f"[{self.name}] Streaming execution failed: {e}")
            import traceback
            self.logger.error(f"[{self.name}] Traceback: {traceback.format_exc()}")
            if event_callback:
                # Send error event first
                await event_callback(StreamEvent.ERROR, {
                    "error": str(e)
                })
                # Try to send any accumulated response before failing
                # Send DONE event with accumulated text if any, so agent_wrapper can send message_complete
                try:
                    await event_callback(StreamEvent.DONE, {
                        "response": accumulated_text if accumulated_text else ""
                    })
                except:
                    pass
            raise AgentError(
                f"Agent streaming execution failed: {e}",
                agent_name=self.name
            ) from e

