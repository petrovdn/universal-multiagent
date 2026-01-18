"""
MCP Tool Provider - wraps existing MCP/LangChain tools as ActionProvider.
Loads all MCP tools and classifies them as READ or WRITE capabilities.

Теперь использует динамическую генерацию tools из MCP серверов для гарантии синхронизации.
"""

import asyncio
from typing import Dict, List
from langchain_core.tools import BaseTool

from src.core.action_provider import (
    ActionProvider,
    ActionCapability,
    ProviderType,
    CapabilityCategory
)
from src.core.mcp_tool_factory import load_tools_from_mcp_servers
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class MCPToolProvider(ActionProvider):
    """
    Wraps existing MCP/LangChain tools as ActionProvider.
    Loads all tools from MCP tool modules and classifies them.
    """
    
    def __init__(self):
        """Initialize MCP tool provider and load all tools."""
        self.tools: Dict[str, BaseTool] = {}
        self._mcp_tools_loaded = False
        
        # #region agent log - начало инициализации
        import json as _debug_json_init; import time as _debug_time_init
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_init:
                _debug_f_init.write(_debug_json_init.dumps({"id":f"log_{int(_debug_time_init.time()*1000)}_mcp_provider_init_start","timestamp":int(_debug_time_init.time()*1000),"location":"mcp_provider.py:30","message":"MCPToolProvider __init__ started","data":{},"sessionId":"debug-session","runId":"run1","hypothesisId":"INIT"}) + '\n')
        except:
            pass
        # #endregion
        
        self._load_all_tools()
        
        # #region agent log - конец инициализации
        try:
            tool_names = list(self.tools.keys())
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_init:
                _debug_f_init.write(_debug_json_init.dumps({"id":f"log_{int(_debug_time_init.time()*1000)}_mcp_provider_init_end","timestamp":int(_debug_time_init.time()*1000),"location":"mcp_provider.py:35","message":"MCPToolProvider __init__ completed","data":{"tools_count":len(self.tools),"tool_names":tool_names,"has_list_emails":"list_emails" in tool_names,"has_search_emails":"search_emails" in tool_names,"has_get_calendar_events":"get_calendar_events" in tool_names,"mcp_tools_loaded":self._mcp_tools_loaded},"sessionId":"debug-session","runId":"run1","hypothesisId":"INIT"}) + '\n')
        except:
            pass
        # #endregion
        
        logger.info(f"[MCPToolProvider] Loaded {len(self.tools)} MCP tools")
    
    def _load_all_tools(self):
        """
        Load all MCP tools.
        
        Приоритет:
        1. Динамическая загрузка из MCP серверов (гарантирует синхронизацию)
        2. Fallback на ручные обёртки (для кастомной логики или если MCP недоступен)
        """
        tools = []
        
        # ШАГ 1: Попытка загрузить tools динамически из MCP серверов
        try:
            logger.info("[MCPToolProvider] Attempting to load tools from MCP servers...")
            
            # Проверяем, есть ли уже запущенный event loop
            try:
                loop = asyncio.get_running_loop()
                # Если loop уже запущен, создаём task в нём
                # Но в __init__ это обычно не так, поэтому используем другой подход
                logger.warning(
                    "[MCPToolProvider] Event loop already running, "
                    "MCP tools will be loaded lazily on first use. Using manual wrappers as fallback."
                )
                # #region agent log - event loop уже запущен
                try:
                    with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_loop:
                        _debug_f_loop.write(_debug_json_build.dumps({"id":f"log_{int(_debug_time_build.time()*1000)}_event_loop_running","timestamp":int(_debug_time_build.time()*1000),"location":"mcp_provider.py:53","message":"Event loop already running, skipping MCP load","data":{"will_use_manual_wrappers":True},"sessionId":"debug-session","runId":"run1","hypothesisId":"LOOP"}) + '\n')
                except:
                    pass
                # #endregion
                # Помечаем, что нужно загрузить позже
                self._mcp_tools_loaded = False
            except RuntimeError:
                # Нет запущенного loop - можем использовать asyncio.run()
                mcp_tools = asyncio.run(load_tools_from_mcp_servers())
                if mcp_tools:
                    tools.extend(mcp_tools)
                    # Логируем email tools для отладки
                    email_tools = [t for t in mcp_tools if "email" in t.name.lower() or "gmail" in t.name.lower()]
                    if email_tools:
                        for tool in email_tools:
                            desc_preview = tool.description[:150] if tool.description else "no description"
                            logger.info(
                                f"[MCPToolProvider] Loaded email tool from MCP: {tool.name} - "
                                f"description: {desc_preview}... (has Russian: {'Русские ключевые слова' in (tool.description or '')})"
                            )
                    logger.info(f"[MCPToolProvider] Loaded {len(mcp_tools)} tools from MCP servers (email tools: {len(email_tools)})")
                    self._mcp_tools_loaded = True
                else:
                    logger.warning("[MCPToolProvider] No tools loaded from MCP servers, using fallback")
                    self._mcp_tools_loaded = False
                    
        except Exception as e:
            logger.warning(
                f"[MCPToolProvider] Failed to load tools from MCP servers: {e}. "
                "Falling back to manual tool wrappers.",
                exc_info=True
            )
            self._mcp_tools_loaded = False
        
        # ШАГ 2: Fallback на ручные обёртки (для инструментов с кастомной логикой)
        # Загружаем только те, которые не были загружены из MCP
        loaded_tool_names = {tool.name for tool in tools}
        
        # #region agent log - перед загрузкой ручных обёрток
        import json as _debug_json_manual; import time as _debug_time_manual
        try:
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_manual:
                _debug_f_manual.write(_debug_json_manual.dumps({"id":f"log_{int(_debug_time_manual.time()*1000)}_manual_wrappers_start","timestamp":int(_debug_time_manual.time()*1000),"location":"mcp_provider.py:90","message":"Loading manual tool wrappers","data":{"mcp_tools_loaded":self._mcp_tools_loaded,"loaded_tool_names":list(loaded_tool_names),"loaded_count":len(loaded_tool_names)},"sessionId":"debug-session","runId":"run1","hypothesisId":"LOAD"}) + '\n')
        except:
            pass
        # #endregion
        
        try:
            # Code execution tools обычно не в MCP, загружаем вручную
            try:
                from src.mcp_tools.code_execution_tools import get_code_execution_tools
                code_tools = get_code_execution_tools()
                for tool in code_tools:
                    if tool.name not in loaded_tool_names:
                        tools.append(tool)
                        logger.debug(f"[MCPToolProvider] Added manual wrapper: {tool.name}")
            except ImportError:
                logger.debug("[MCPToolProvider] Code execution tools not available")
            
            # КРИТИЧНО: Если MCP tools не загрузились (event loop уже запущен или ошибка),
            # загружаем ручные обёртки для всех инструментов
            if not self._mcp_tools_loaded or len(loaded_tool_names) == 0:
                logger.warning(
                    "[MCPToolProvider] MCP tools not loaded, loading manual wrappers for all tools"
                )
                
                # Gmail tools
                try:
                    from src.mcp_tools.gmail_tools import get_gmail_tools
                    gmail_tools = get_gmail_tools()
                    for tool in gmail_tools:
                        if tool.name not in loaded_tool_names:
                            tools.append(tool)
                            logger.info(f"[MCPToolProvider] Added manual Gmail wrapper: {tool.name}")
                except ImportError as e:
                    logger.warning(f"[MCPToolProvider] Failed to load Gmail tools: {e}")
                
                # Calendar tools
                try:
                    from src.mcp_tools.calendar_tools import get_calendar_tools
                    calendar_tools = get_calendar_tools()
                    for tool in calendar_tools:
                        if tool.name not in loaded_tool_names:
                            tools.append(tool)
                            logger.info(f"[MCPToolProvider] Added manual Calendar wrapper: {tool.name}")
                except ImportError as e:
                    logger.warning(f"[MCPToolProvider] Failed to load Calendar tools: {e}")
                
                # Sheets tools
                try:
                    from src.mcp_tools.sheets_tools import get_sheets_tools
                    sheets_tools = get_sheets_tools()
                    for tool in sheets_tools:
                        if tool.name not in loaded_tool_names:
                            tools.append(tool)
                            logger.info(f"[MCPToolProvider] Added manual Sheets wrapper: {tool.name}")
                except ImportError as e:
                    logger.warning(f"[MCPToolProvider] Failed to load Sheets tools: {e}")
                
                # Docs tools
                try:
                    from src.mcp_tools.docs_tools import get_docs_tools
                    docs_tools = get_docs_tools()
                    for tool in docs_tools:
                        if tool.name not in loaded_tool_names:
                            tools.append(tool)
                            logger.info(f"[MCPToolProvider] Added manual Docs wrapper: {tool.name}")
                except ImportError as e:
                    logger.warning(f"[MCPToolProvider] Failed to load Docs tools: {e}")
                
                # Slides tools
                try:
                    from src.mcp_tools.slides_tools import get_slides_tools
                    slides_tools = get_slides_tools()
                    for tool in slides_tools:
                        if tool.name not in loaded_tool_names:
                            tools.append(tool)
                            logger.info(f"[MCPToolProvider] Added manual Slides wrapper: {tool.name}")
                except ImportError as e:
                    logger.warning(f"[MCPToolProvider] Failed to load Slides tools: {e}")
                
                # Workspace tools
                try:
                    from src.mcp_tools.workspace_tools import get_workspace_tools
                    workspace_tools = get_workspace_tools()
                    for tool in workspace_tools:
                        if tool.name not in loaded_tool_names:
                            tools.append(tool)
                            logger.info(f"[MCPToolProvider] Added manual Workspace wrapper: {tool.name}")
                except ImportError as e:
                    logger.warning(f"[MCPToolProvider] Failed to load Workspace tools: {e}")
            
        except Exception as e:
            logger.warning(f"[MCPToolProvider] Failed to load some manual wrappers: {e}", exc_info=True)
        
        # #region agent log - после загрузки ручных обёрток
        try:
            final_tool_names = [t.name for t in tools]
            with open('/Users/Dima/universal-multiagent/.cursor/debug.log', 'a') as _debug_f_manual:
                _debug_f_manual.write(_debug_json_manual.dumps({"id":f"log_{int(_debug_time_manual.time()*1000)}_manual_wrappers_end","timestamp":int(_debug_time_manual.time()*1000),"location":"mcp_provider.py:120","message":"Manual wrappers loaded","data":{"final_tool_count":len(tools),"final_tool_names":final_tool_names,"has_list_emails":any(t.name == "list_emails" for t in tools),"has_search_emails":any(t.name == "search_emails" for t in tools),"has_get_calendar_events":any(t.name == "get_calendar_events" for t in tools)},"sessionId":"debug-session","runId":"run1","hypothesisId":"LOAD"}) + '\n')
        except:
            pass
        # #endregion
        
        # Удаляем дубликаты (приоритет у MCP tools)
        seen_names = set()
        for tool in tools:
            if tool.name not in seen_names:
                seen_names.add(tool.name)
                self.tools[tool.name] = tool
            else:
                logger.warning(f"[MCPToolProvider] Duplicate tool name: {tool.name}, keeping first")
    
    def get_capabilities(self) -> List[ActionCapability]:
        """Return list of capabilities from all loaded MCP tools."""
        capabilities = []
        
        for name, tool in self.tools.items():
            try:
                # Get input schema
                input_schema = {}
                if tool.args_schema:
                    try:
                        input_schema = tool.args_schema.schema()
                    except Exception as e:
                        logger.debug(f"[MCPToolProvider] Failed to get schema for {name}: {e}")
                        input_schema = {}
                
                # Classify tool
                category = self._classify_tool(name)
                
                # Get service name
                service = self._get_service(name)
                
                tool_description = tool.description or f"Tool: {name}"
                capabilities.append(ActionCapability(
                    name=name,
                    description=tool_description,
                    category=category,
                    provider_type=ProviderType.MCP_TOOL,
                    input_schema=input_schema,
                    service=service,
                    tags=self._get_tags(name)
                ))
                
                # Логируем описания для email tools для отладки
                if "email" in name.lower() or "gmail" in name.lower() or "mail" in name.lower():
                    logger.info(
                        f"[MCPToolProvider] Email tool capability: {name} - "
                        f"description length: {len(tool_description)}, "
                        f"has Russian keywords: {'Русские ключевые слова' in tool_description}"
                    )
            except Exception as e:
                logger.error(f"[MCPToolProvider] Failed to create capability for {name}: {e}")
                continue
        
        logger.info(f"[MCPToolProvider] Created {len(capabilities)} capabilities")
        return capabilities
    
    async def execute(
        self,
        capability_name: str,
        arguments: Dict,
        context: Dict = None
    ):
        """Execute a capability through the underlying MCP tool."""
        tool = self.tools.get(capability_name)
        if not tool:
            raise ValueError(f"Unknown capability: {capability_name}")
        try:
            # Remove internal fields that Pydantic doesn't accept
            # These are added by unified_react_engine for tracking but MCP tools don't need them
            clean_arguments = {k: v for k, v in arguments.items() if not k.startswith('_')}
            
            # Fix ProjectLad argument naming inconsistency
            # LLM sometimes uses 'project_version_id' (like in other ProjectLad tools)
            # instead of 'version_id' (which is what GetResourceUtilizationInput expects)
            if capability_name == 'projectlad_get_resource_utilization':
                if 'project_version_id' in clean_arguments and 'version_id' not in clean_arguments:
                    clean_arguments['version_id'] = clean_arguments.pop('project_version_id')
            
            # Fix common LLM argument naming mistakes for docs tools
            # LLM sometimes uses 'text' instead of 'content', 'position' instead of 'index'
            if capability_name in ['append_to_document', 'insert_into_document', 'update_document']:
                if 'text' in clean_arguments and 'content' not in clean_arguments:
                    clean_arguments['content'] = clean_arguments.pop('text')
                if 'position' in clean_arguments and 'index' not in clean_arguments:
                    clean_arguments['index'] = clean_arguments.pop('position')
                # Convert escaped newlines to real newlines in content
                # LLM often outputs \\n\\n instead of actual newlines
                if 'content' in clean_arguments and isinstance(clean_arguments['content'], str):
                    clean_arguments['content'] = clean_arguments['content'].replace('\\n', '\n')
            
            # Fix boolean to float conversion for indent_first_line
            # LLM sometimes passes true instead of 36 (standard indent in points)
            if capability_name == 'format_document_paragraph':
                if 'indent_first_line' in clean_arguments:
                    val = clean_arguments['indent_first_line']
                    if val is True:
                        clean_arguments['indent_first_line'] = 36.0  # Standard first-line indent
                    elif val is False:
                        clean_arguments['indent_first_line'] = 0.0
            
            # Fix attendee_filter: LLM sometimes passes array instead of string
            # Convert ["marat", "churukhov"] to "marat и churukhov"
            if capability_name == 'get_calendar_events' and 'attendee_filter' in clean_arguments:
                attendee_filter = clean_arguments['attendee_filter']
                if isinstance(attendee_filter, list):
                    # Join array with " и " (AND operator) for Russian
                    clean_arguments['attendee_filter'] = ' и '.join(str(item) for item in attendee_filter)
                    logger.info(f"[MCPToolProvider] Converted attendee_filter from array to string: {clean_arguments['attendee_filter']}")
            
            result = await tool.ainvoke(clean_arguments)
            return result
        except Exception as e:
            logger.error(f"[MCPToolProvider] Execution failed for {capability_name}: {e}")
            raise
    
    @property
    def provider_type(self) -> ProviderType:
        """Return provider type."""
        return ProviderType.MCP_TOOL
    
    async def health_check(self) -> bool:
        """Check if MCP provider is healthy."""
        # MCP tools are considered healthy if they're loaded
        return len(self.tools) > 0
    
    def _classify_tool(self, name: str) -> CapabilityCategory:
        """
        Classify tool as READ or WRITE based on name patterns.
        
        Args:
            name: Tool name
            
        Returns:
            CapabilityCategory (READ or WRITE)
        """
        name_lower = name.lower()
        
        # Read patterns - tools that only read data
        read_patterns = [
            "get_", "search_", "list_", "read_", "find_", 
            "fetch_", "retrieve_", "query_", "lookup_",
            "get_", "read", "search", "list", "find"
        ]
        
        # Check if tool name starts with or contains read pattern
        for pattern in read_patterns:
            if name_lower.startswith(pattern) or f"_{pattern}" in name_lower:
                return CapabilityCategory.READ
        
        # Special cases - explicitly read-only tools
        read_only_tools = [
            "search_emails", "get_email", "get_labels",
            "get_sheet_data", "sheets_read_range",
            "get_events", "get_calendars",
            "search_files", "list_files", "workspace_search_files",
            "docs_read", "slides_get"
        ]
        
        if name in read_only_tools:
            return CapabilityCategory.READ
        
        # Default to WRITE for tools that modify state
        return CapabilityCategory.WRITE
    
    def _get_service(self, name: str) -> str:
        """
        Determine service name from tool name.
        
        Args:
            name: Tool name
            
        Returns:
            Service identifier (gmail, sheets, calendar, etc.)
        """
        name_lower = name.lower()
        
        # Service mapping based on tool name patterns
        if "gmail" in name_lower or "email" in name_lower:
            return "gmail"
        elif "sheet" in name_lower or "spreadsheet" in name_lower:
            return "sheets"
        elif "calendar" in name_lower or "event" in name_lower:
            return "calendar"
        elif "workspace" in name_lower or "file" in name_lower:
            return "workspace"
        elif "doc" in name_lower and "slide" not in name_lower:
            return "docs"
        elif "slide" in name_lower or "presentation" in name_lower:
            return "slides"
        elif "onec" in name_lower:
            return "onec"
        elif "projectlad" in name_lower:
            return "projectlad"
        elif "code" in name_lower or "python" in name_lower or "execute" in name_lower:
            return "code_execution"
        else:
            return "unknown"
    
    def _get_tags(self, name: str) -> List[str]:
        """
        Get tags for a tool based on its name and service.
        
        Args:
            name: Tool name
            
        Returns:
            List of tags
        """
        tags = []
        service = self._get_service(name)
        if service != "unknown":
            tags.append(service)
        
        category = self._classify_tool(name)
        tags.append(category.value)
        
        return tags

