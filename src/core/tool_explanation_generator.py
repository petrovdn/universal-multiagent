"""
ToolExplanationGenerator - Generates human-readable explanations for tool calls.

Cursor-style explanations that hide technical details and present actions
in natural language to users.
"""

from typing import Dict, Any, Optional


class ToolExplanationGenerator:
    """Generates human-readable explanations for tool calls."""
    
    def __init__(self):
        """Initialize the generator with action templates and service mappings."""
        # Action templates: prefix -> template
        self.action_templates: Dict[str, str] = {
            "list_": "Проверяю список в {service}",
            "get_": "Получаю данные из {service}",
            "create_": "Создаю {object_type} в {service}",
            "search_": "Ищу в {service}",
            "read_": "Читаю из {service}",
            "update_": "Обновляю в {service}",
            "delete_": "Удаляю из {service}",
            "send_": "Отправляю через {service}",
            "schedule_": "Планирую в {service}",
        }
        
        # Service name mappings: tool_name -> service name
        self.service_names: Dict[str, str] = {
            "list_emails": "Gmail",
            "search_emails": "Gmail",
            "read_email": "Gmail",
            "send_email": "Gmail",
            "draft_email": "Gmail",
            "get_sheet_data": "Google Sheets",
            "get_all_sheets_data": "Google Sheets",
            "create_spreadsheet": "Google Sheets",
            "update_cells": "Google Sheets",
            "get_calendar_events": "Google Calendar",
            "create_event": "Google Calendar",
            "schedule_group_meeting": "Google Calendar",
            "get_next_availability": "Google Calendar",
            "create_document": "Google Docs",
            "read_document": "Google Docs",
            "update_document": "Google Docs",
            "create_presentation": "Google Slides",
            "get_presentation": "Google Slides",
            "create_slide": "Google Slides",
        }
        
        # Object type mappings for create_ actions
        self.object_types: Dict[str, str] = {
            "create_document": "документ",
            "create_presentation": "презентацию",
            "create_spreadsheet": "таблицу",
            "create_event": "событие",
            "create_slide": "слайд",
        }
        
        # Custom explanations for specific tools
        self.custom_explanations: Dict[str, str] = {
            "list_emails": "Проверяю письма",
            "get_calendar_events": "Проверяю встречи в календаре",
        }
    
    def generate(self, tool_name: str, args: Dict[str, Any]) -> str:
        """
        Generate human-readable explanation for a tool call.
        
        Args:
            tool_name: Name of the tool (e.g., "list_emails")
            args: Tool arguments dictionary
            
        Returns:
            Human-readable explanation string
        """
        # Check for custom explanation first
        if tool_name in self.custom_explanations:
            explanation = self.custom_explanations[tool_name]
            # Enhance with key info from args
            return self._enhance_with_args(explanation, tool_name, args)
        
        # Determine action prefix
        action_prefix = None
        for prefix in self.action_templates.keys():
            if tool_name.startswith(prefix):
                action_prefix = prefix
                break
        
        # Get service name
        service = self.service_names.get(tool_name, "системе")
        
        # Generate base explanation
        if action_prefix:
            template = self.action_templates[action_prefix]
            
            # For create_ actions, get object type
            if action_prefix == "create_":
                object_type = self.object_types.get(tool_name, "объект")
                explanation = template.format(service=service, object_type=object_type)
            else:
                explanation = template.format(service=service)
        else:
            # Generic fallback
            explanation = f"Выполняю действие в {service}"
        
        # Enhance with key information from args
        return self._enhance_with_args(explanation, tool_name, args)
    
    def _enhance_with_args(self, explanation: str, tool_name: str, args: Dict[str, Any]) -> str:
        """
        Enhance explanation with relevant information from args.
        
        Args:
            explanation: Base explanation
            tool_name: Tool name
            args: Tool arguments
            
        Returns:
            Enhanced explanation
        """
        if not args:
            return explanation
        
        # Extract key info based on tool type
        enhancements = []
        
        # For email/search tools, mention query if present
        if "query" in args and args["query"]:
            query = str(args["query"])
            # Don't include technical query syntax
            if not query.startswith("is:") and not query.startswith("from:"):
                enhancements.append(f'по запросу "{query}"')
        
        # For document/presentation creation, mention title
        if "title" in args and args["title"]:
            title = str(args["title"])
            enhancements.append(f'"{title}"')
        
        # For calendar events, mention date if present
        if "time_min" in args or "time_max" in args:
            # Don't include raw timestamps, just indicate date filtering
            pass  # Could enhance later with date parsing
        
        # Combine enhancements
        if enhancements:
            return f"{explanation} {', '.join(enhancements)}"
        
        return explanation
