"""
Project Lad MCP tool wrappers for LangChain.
Provides validated interfaces to Project Lad operations.
"""

import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.utils.mcp_loader import get_mcp_manager
from src.utils.exceptions import ToolExecutionError, ValidationError
from src.utils.retry import retry_on_mcp_error


class ListProjectsInput(BaseModel):
    """Input schema for projectlad_list_projects tool."""
    
    permission_filter: Optional[str] = Field(default=None, description="Optional permission filter")
    with_groups: bool = Field(default=False, description="Include project groups")


class ListProjectsTool(BaseTool):
    """Tool for getting list of available projects from Project Lad."""
    
    name: str = "projectlad_list_projects"
    description: str = """
    Get list of available projects from Project Lad.
    
    Input:
    - permission_filter: Optional permission filter
    - with_groups: Include project groups (default: False)
    
    **CRITICAL**: This tool returns BOTH project_id AND version_id for each project!
    
    **Response structure**:
    Each project contains:
    - id: project_id (UUID format, e.g., "IzNRF5kByOLXRJ_0k2_Cc")
    - title: project name (e.g., "Atlas — веб-платформа")
    - version_id: current version ID (UUID format, e.g., "j9CgXe1pncf4eKpgRBg5r")
    - children: nested projects (if any)
    
    **IMPORTANT for nested projects like "Atlas"**:
    - If project is nested (inside "Портфель: Разработка продуктов"), look in children array
    - Each child project ALSO has id, title, and version_id fields
    
    **Example**: To find "Atlas" project:
    1. Call projectlad_list_projects
    2. Look in main projects or their children arrays
    3. Find project with title containing "Atlas"
    4. Extract BOTH id (project_id) and version_id from that project object
    5. Use these IDs for projectlad_get_resource_utilization
    
    Returns list of projects with their IDs, titles, version_ids, and metadata.
    """
    args_schema: type = ListProjectsInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        permission_filter: Optional[str] = None,
        with_groups: bool = False
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            args = {}
            if permission_filter:
                args["permission_filter"] = permission_filter
            if with_groups:
                args["with_groups"] = with_groups
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("projectlad_list_projects", args, server_name="projectlad")
            
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    pass
            
            # Handle MCP response format - list of TextContent objects
            if isinstance(result, list) and len(result) > 0:
                # If it's a list of MCP TextContent objects
                if hasattr(result[0], 'text'):
                    try:
                        result = json.loads(result[0].text)
                    except:
                        pass
                elif isinstance(result[0], dict) and 'text' in result[0]:
                    try:
                        result = json.loads(result[0]['text'])
                    except:
                        pass
            
            if isinstance(result, dict):
                projects = result.get("projects", result.get("result", []))
                if not projects:
                    return "No projects found."
                
                summary = f"Found {len(projects)} project(s):\n\n"
                
                def format_project(project, level=0):
                    """Format project with nested children, showing project_id AND version_id."""
                    indent = "  " * level
                    project_id = project.get("id", "N/A")
                    # API returns "current_version_id", not "version_id"
                    version_id = project.get("version_id") or project.get("current_version_id", "N/A")
                    title = project.get("title", project.get("name", "Untitled"))
                    
                    result = f"{indent}• {title}\n"
                    result += f"{indent}  project_id: {project_id}\n"
                    result += f"{indent}  version_id: {version_id}\n"
                    
                    # Process children if any
                    children = project.get("children", [])
                    if children:
                        result += f"{indent}  ──────────────────────────\n"
                        result += f"{indent}  ВЛОЖЕННЫЕ ПРОЕКТЫ (Children):\n"
                        result += f"{indent}  ──────────────────────────\n"
                        for child in children:
                            result += format_project(child, level + 1)
                    
                    return result
                
                for i, project in enumerate(projects[:10], 1):
                    summary += f"{i}. " + format_project(project)
                    summary += "\n"
                
                if len(projects) > 10:
                    summary += f"... and {len(projects) - 10} more projects."
                
                return summary
            
            return str(result)
            
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to list projects: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetProjectInput(BaseModel):
    """Input schema for projectlad_get_project tool."""
    
    project_id: str = Field(description="Project ID")


class GetProjectTool(BaseTool):
    """Tool for getting project details from Project Lad."""
    
    name: str = "projectlad_get_project"
    description: str = """
    Get project details by ID from Project Lad.
    
    Input:
    - project_id: Project ID
    
    Returns project details including title, description, and metadata.
    """
    args_schema: type = GetProjectInput
    
    @retry_on_mcp_error()
    async def _arun(self, project_id: str) -> str:
        """Execute the tool asynchronously."""
        try:
            if not project_id:
                raise ValidationError("project_id is required")
            
            args = {"project_id": project_id}
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("projectlad_get_project", args, server_name="projectlad")
            
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    pass
            
            if isinstance(result, dict):
                project = result.get("project", result.get("result", result))
                if not project:
                    return f"Project with ID {project_id} not found."
                
                title = project.get("title", project.get("name", "Untitled"))
                summary = f"Project: {title}\n"
                summary += f"ID: {project.get('id', 'N/A')}\n"
                
                if project.get("description"):
                    summary += f"Description: {project.get('description')}\n"
                
                return summary
            
            return str(result)
            
        except ValidationError as e:
            raise ToolExecutionError(
                f"Validation failed: {e.message}",
                tool_name=self.name,
                tool_args={"project_id": project_id}
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get project: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetProjectWorksInput(BaseModel):
    """Input schema for projectlad_get_project_works tool."""
    
    project_id: str = Field(description="Project ID")
    project_version_id: Optional[str] = Field(default=None, description="Project version ID (optional, uses latest if not provided)")


class GetProjectWorksTool(BaseTool):
    """Tool for getting list of works (items) for a project version."""
    
    name: str = "projectlad_get_project_works"
    description: str = """
    Get list of works (items) for a project version from Project Lad.
    
    Input:
    - project_id: Project ID
    - project_version_id: Project version ID (optional, uses latest if not provided)
    
    Returns list of works with their names, types, and relationships.
    """
    args_schema: type = GetProjectWorksInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        project_id: str,
        project_version_id: Optional[str] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            if not project_id:
                raise ValidationError("project_id is required")
            
            args = {"project_id": project_id}
            if project_version_id:
                args["project_version_id"] = project_version_id
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("projectlad_get_project_works", args, server_name="projectlad")
            
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    pass
            
            if isinstance(result, dict):
                works = result.get("works", result.get("items", result.get("result", [])))
                if not works:
                    return f"No works found for project {project_id}."
                
                summary = f"Found {len(works)} work(s) for project:\n\n"
                for i, work in enumerate(works[:30], 1):
                    name = work.get("name", work.get("title", "Untitled"))
                    work_type = work.get("type", "N/A")
                    summary += f"{i}. {name} (Type: {work_type})\n"
                
                if len(works) > 30:
                    summary += f"\n... and {len(works) - 30} more works."
                
                return summary
            
            return str(result)
            
        except ValidationError as e:
            raise ToolExecutionError(
                f"Validation failed: {e.message}",
                tool_name=self.name,
                tool_args={"project_id": project_id}
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get project works: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetMilestonesInput(BaseModel):
    """Input schema for projectlad_get_milestones tool."""
    
    project_id: str = Field(description="Project ID")
    project_version_id: Optional[str] = Field(default=None, description="Project version ID (optional)")


class GetMilestonesTool(BaseTool):
    """Tool for getting milestones and their deadlines for a project."""
    
    name: str = "projectlad_get_milestones"
    description: str = """
    Get milestones and their deadlines for a project from Project Lad.
    
    Input:
    - project_id: Project ID
    - project_version_id: Project version ID (optional)
    
    Returns list of milestones with their deadlines and status.
    """
    args_schema: type = GetMilestonesInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        project_id: str,
        project_version_id: Optional[str] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            if not project_id:
                raise ValidationError("project_id is required")
            
            args = {"project_id": project_id}
            if project_version_id:
                args["project_version_id"] = project_version_id
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("projectlad_get_milestones", args, server_name="projectlad")
            
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    pass
            
            if isinstance(result, dict):
                milestones = result.get("milestones", result.get("result", []))
                if not milestones:
                    return f"No milestones found for project {project_id}."
                
                summary = f"Found {len(milestones)} milestone(s) for project:\n\n"
                for i, milestone in enumerate(milestones, 1):
                    name = milestone.get("name", milestone.get("title", "Untitled"))
                    deadline = milestone.get("deadline", milestone.get("end_date", "N/A"))
                    summary += f"{i}. {name} - Deadline: {deadline}\n"
                
                return summary
            
            return str(result)
            
        except ValidationError as e:
            raise ToolExecutionError(
                f"Validation failed: {e.message}",
                tool_name=self.name,
                tool_args={"project_id": project_id}
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get milestones: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetIndicatorsInput(BaseModel):
    """Input schema for projectlad_get_indicators tool."""
    
    project_id: str = Field(description="Project ID")
    project_version_id: Optional[str] = Field(default=None, description="Project version ID (optional)")
    from_date: Optional[str] = Field(default=None, description="Start date (ISO 8601 format: YYYY-MM-DD)")
    to_date: Optional[str] = Field(default=None, description="End date (ISO 8601 format: YYYY-MM-DD)")
    indicator_ids: Optional[List[str]] = Field(default=None, description="Optional list of specific indicator IDs to filter")


class GetIndicatorsTool(BaseTool):
    """Tool for getting indicator values for a project with period filtering."""
    
    name: str = "projectlad_get_indicators"
    description: str = """
    Get indicator values for a project with period filtering from Project Lad.
    
    Input:
    - project_id: Project ID
    - project_version_id: Project version ID (optional)
    - from_date: Start date (ISO 8601 format: YYYY-MM-DD)
    - to_date: End date (ISO 8601 format: YYYY-MM-DD)
    - indicator_ids: Optional list of specific indicator IDs to filter
    
    Returns indicator values for the specified period.
    """
    args_schema: type = GetIndicatorsInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        project_id: str,
        project_version_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        indicator_ids: Optional[List[str]] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            if not project_id:
                raise ValidationError("project_id is required")
            
            # Validate dates if provided
            if from_date:
                try:
                    datetime.fromisoformat(f"{from_date}T00:00:00")
                except ValueError as e:
                    raise ValidationError(f"Invalid from_date format: {e}. Use YYYY-MM-DD format.")
            
            if to_date:
                try:
                    datetime.fromisoformat(f"{to_date}T23:59:59")
                except ValueError as e:
                    raise ValidationError(f"Invalid to_date format: {e}. Use YYYY-MM-DD format.")
            
            args = {"project_id": project_id}
            if project_version_id:
                args["project_version_id"] = project_version_id
            if from_date:
                args["from_date"] = from_date
            if to_date:
                args["to_date"] = to_date
            if indicator_ids:
                args["indicator_ids"] = indicator_ids
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("projectlad_get_indicators", args, server_name="projectlad")
            
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    pass
            
            if isinstance(result, dict):
                indicators = result.get("indicators", result.get("result", []))
                if not indicators:
                    period = f" from {from_date} to {to_date}" if from_date and to_date else ""
                    return f"No indicators found for project {project_id}{period}."
                
                summary = f"Found {len(indicators)} indicator value(s) for project:\n\n"
                for i, indicator in enumerate(indicators[:20], 1):
                    indicator_name = indicator.get("indicator_name", indicator.get("name", "N/A"))
                    value = indicator.get("value", "N/A")
                    date = indicator.get("date", indicator.get("period", "N/A"))
                    summary += f"{i}. {indicator_name}: {value} (Date: {date})\n"
                
                if len(indicators) > 20:
                    summary += f"\n... and {len(indicators) - 20} more indicator values."
                
                return summary
            
            return str(result)
            
        except ValidationError as e:
            raise ToolExecutionError(
                f"Validation failed: {e.message}",
                tool_name=self.name,
                tool_args={"project_id": project_id}
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get indicators: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetIndicatorAnalyticsInput(BaseModel):
    """Input schema for projectlad_get_indicator_analytics tool."""
    
    project_id: str = Field(description="Project ID")
    from_date: str = Field(description="Start date (ISO 8601 format: YYYY-MM-DD)")
    to_date: str = Field(description="End date (ISO 8601 format: YYYY-MM-DD)")
    project_version_id: Optional[str] = Field(default=None, description="Project version ID (optional)")


class GetIndicatorAnalyticsTool(BaseTool):
    """Tool for getting indicator analytics with various data slices by period."""
    
    name: str = "projectlad_get_indicator_analytics"
    description: str = """
    Get indicator analytics with various data slices by period from Project Lad.
    
    **NOTE**: This tool is for project indicators (metrics, KPIs), NOT for resource/employee workload.
    For employee hours/workload, use projectlad_get_resource_utilization instead.
    
    Input:
    - project_id: Project ID
    - from_date: Start date (ISO 8601 format: YYYY-MM-DD)
    - to_date: End date (ISO 8601 format: YYYY-MM-DD)
    - project_version_id: Project version ID (optional)
    
    Returns indicator analytics with various data slices by period.
    """
    args_schema: type = GetIndicatorAnalyticsInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        project_id: str,
        from_date: str,
        to_date: str,
        project_version_id: Optional[str] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            if not project_id:
                raise ValidationError("project_id is required")
            if not from_date:
                raise ValidationError("from_date is required")
            if not to_date:
                raise ValidationError("to_date is required")
            
            # Validate dates
            try:
                datetime.fromisoformat(f"{from_date}T00:00:00")
                datetime.fromisoformat(f"{to_date}T23:59:59")
            except ValueError as e:
                raise ValidationError(f"Invalid date format: {e}. Use YYYY-MM-DD format.")
            
            args = {
                "project_id": project_id,
                "from_date": from_date,
                "to_date": to_date
            }
            if project_version_id:
                args["project_version_id"] = project_version_id
            
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("projectlad_get_indicator_analytics", args, server_name="projectlad")
            
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    pass
            
            if isinstance(result, dict):
                analytics = result.get("analytics", result.get("result", result))
                if not analytics:
                    return f"No analytics found for project {project_id} for period {from_date} to {to_date}."
                
                summary = f"Indicator analytics for project {project_id} ({from_date} to {to_date}):\n\n"
                summary += json.dumps(analytics, indent=2, default=str)
                
                return summary
            
            return str(result)
            
        except ValidationError as e:
            raise ToolExecutionError(
                f"Validation failed: {e.message}",
                tool_name=self.name,
                tool_args={"project_id": project_id, "from_date": from_date, "to_date": to_date}
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get indicator analytics: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetResourceUtilizationInput(BaseModel):
    """Input schema for projectlad_get_resource_utilization tool."""
    
    project_id: str = Field(description="Project ID")
    version_id: str = Field(description="Project version ID")


class GetResourceUtilizationTool(BaseTool):
    """Tool for getting resource utilization (загрузка ресурсов) from Project Lad."""
    
    name: str = "projectlad_get_resource_utilization"
    description: str = """
    **PRIMARY TOOL** for getting resource/employee workload data (загрузка ресурсов/сотрудников) from Project Lad.
    
    **IMPORTANT**: This is the ONLY tool that returns actual employee hours and workload data.
    Do NOT use projectlad_get_indicators or projectlad_get_indicator_analytics for this - they return different data.
    
    **Use this tool when user asks about:**
    - Resource workload / загрузка ресурсов
    - Employee hours / часы сотрудников  
    - Staff allocation / распределение персонала
    - Team capacity / загрузка команды
    - How many hours employees work on project / сколько часов работают сотрудники
    
    **WORKFLOW**: You MUST have both project_id and version_id before calling this tool:
    1. If you only have project name (e.g., "Atlas"), first call projectlad_list_projects to get project_id and version_id
    2. Then call this tool with both IDs
    
    **Input (BOTH REQUIRED)**:
    - project_id: Project ID (UUID format, NOT project name)
    - version_id: Project version ID (UUID format)
    
    Returns detailed information about resource allocation by month, including:
    - Resource name (ФИО сотрудника)
    - Month (Месяц)
    - Hours (Часы загрузки)
    
    Returns aggregated resource utilization by month in human-readable format.
    """
    args_schema: type = GetResourceUtilizationInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        project_id: str,
        version_id: str
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            if not project_id:
                raise ValidationError("project_id is required")
            if not version_id:
                raise ValidationError("version_id is required")
            
            mcp_manager = get_mcp_manager()
            
            # Получаем данные загрузки ресурсов
            utilization_args = {
                "project_id": project_id,
                "version_id": version_id
            }
            
            utilization_result = await mcp_manager.call_tool(
                "projectlad_get_resource_utilization",
                utilization_args,
                server_name="projectlad"
            )
            
            # Получаем имена ресурсов через analytics
            analytics_args = {
                "project_id": project_id,
                "version_id": version_id,
                "from_date": "2025-01-01",
                "to_date": "2025-12-31"
            }
            
            analytics_result = await mcp_manager.call_tool(
                "projectlad_get_indicator_analytics",
                analytics_args,
                server_name="projectlad"
            )
            
            # Парсим результаты
            if isinstance(utilization_result, str):
                import json
                utilization_result = json.loads(utilization_result)
            
            if isinstance(analytics_result, str):
                import json
                analytics_result = json.loads(analytics_result)
            
            # MCP server возвращает список напрямую, а не обернутый в {"result": [...]}
            # Если результат - это список TextContent объектов от MCP, берем первый элемент
            if isinstance(utilization_result, list) and len(utilization_result) > 0:
                # Если это MCP response с TextContent
                if hasattr(utilization_result[0], 'text'):
                    import json
                    utilization_data = json.loads(utilization_result[0].text)
                elif isinstance(utilization_result[0], dict) and 'text' in utilization_result[0]:
                    import json
                    utilization_data = json.loads(utilization_result[0]['text'])
                else:
                    # Это уже распарсенный список данных
                    utilization_data = utilization_result
            elif isinstance(utilization_result, dict):
                # Старый формат: {"result": [...]}
                utilization_data = utilization_result.get("result", {})
            else:
                utilization_data = utilization_result
            
            # Если utilization_data - это обёртка {"message": "", "result": {...}}, берем result
            if isinstance(utilization_data, dict) and "result" in utilization_data and "message" in utilization_data:
                utilization_data = utilization_data["result"]
            
            # То же для analytics_result
            if isinstance(analytics_result, list) and len(analytics_result) > 0:
                if hasattr(analytics_result[0], 'text'):
                    import json
                    analytics_data = json.loads(analytics_result[0].text)
                elif isinstance(analytics_result[0], dict) and 'text' in analytics_result[0]:
                    import json
                    analytics_data = json.loads(analytics_result[0]['text'])
                else:
                    analytics_data = analytics_result
            elif isinstance(analytics_result, dict):
                analytics_data = analytics_result.get("result", [])
            else:
                analytics_data = analytics_result
            
            # Если analytics_data - это обёртка {"message": "", "result": {...}}, берем result
            if isinstance(analytics_data, dict) and "result" in analytics_data and "message" in analytics_data:
                analytics_data = analytics_data["result"]
            
            # Если analytics_data - это обёртка {"analytics": [...]}, берем список
            if isinstance(analytics_data, dict) and "analytics" in analytics_data:
                analytics_data = analytics_data["analytics"]
            
            # Создаем маппинг resource_id -> имя
            resource_names = {}
            
            if isinstance(analytics_data, list):
                for item in analytics_data:
                    indicator_title = item.get("indicator_title", "")
                    
                    if "ресурс" in indicator_title.lower():
                        resource_id = item.get("analytics_element_id")
                        name = item.get("analytic_title")
                        if resource_id and name:
                            resource_names[resource_id] = name
            
            # Агрегируем данные по ресурсам и месяцам
            from datetime import datetime
            from collections import defaultdict
            
            resource_month_hours = defaultdict(lambda: defaultdict(int))
            
            # Обрабатываем данные - они могут быть в двух форматах:
            # Формат 1: {work_id: [{resource_id, start_date, end_date, value}, ...], ...}
            # Формат 2: [{work_id, resource_id, start_date, end_date, value}, ...]
            
            assignments_list = []
            if isinstance(utilization_data, dict):
                # Формат 1: словарь с work_id -> список assignments
                for work_id, assignments in utilization_data.items():
                    if isinstance(assignments, list):
                        assignments_list.extend(assignments)
            elif isinstance(utilization_data, list):
                # Формат 2: плоский список assignments
                assignments_list = utilization_data
            
            # Обрабатываем каждый assignment
            for assignment in assignments_list:
                if not isinstance(assignment, dict):
                    continue
                
                resource_id = assignment.get("resource_id")
                start_date_str = assignment.get("start_date")
                end_date_str = assignment.get("end_date")
                hours_per_day = assignment.get("value", 0)
                
                if not all([resource_id, start_date_str, end_date_str]):
                    continue
                
                # Парсим даты
                try:
                    start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    continue
                
                # Получаем имя ресурса
                resource_name = resource_names.get(resource_id, resource_id)
                
                # Итерируем по дням и агрегируем по месяцам
                from datetime import timedelta
                current_date = start_date
                while current_date < end_date:
                    month_key = current_date.strftime("%Y-%m")  # "2025-06"
                    resource_month_hours[resource_name][month_key] += hours_per_day
                    
                    # Переход к следующему дню
                    current_date = current_date + timedelta(days=1)
            
            # Форматируем результат
            if not resource_month_hours:
                return f"No resource utilization data found for project {project_id}"
            
            summary = f"Resource utilization for project (version {version_id}):\n\n"
            summary += f"Found {len(resource_month_hours)} resource(s):\n\n"
            
            # Словарь для перевода месяцев
            month_names = {
                "01": "Январь", "02": "Февраль", "03": "Март",
                "04": "Апрель", "05": "Май", "06": "Июнь",
                "07": "Июль", "08": "Август", "09": "Сентябрь",
                "10": "Октябрь", "11": "Ноябрь", "12": "Декабрь"
            }
            
            for resource_name in sorted(resource_month_hours.keys()):
                months_data = resource_month_hours[resource_name]
                total_hours = sum(months_data.values())
                
                summary += f"• {resource_name}: {total_hours} ч.\n"
                
                for month_key in sorted(months_data.keys()):
                    year, month = month_key.split("-")
                    month_name = month_names.get(month, month)
                    hours = months_data[month_key]
                    summary += f"  - {month_name} {year}: {hours} ч.\n"
                
                summary += "\n"
            
            return summary
            
        except ValidationError as e:
            raise ToolExecutionError(
                f"Validation failed: {e.message}",
                tool_name=self.name,
                tool_args={"project_id": project_id, "version_id": version_id}
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get resource utilization: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


def get_projectlad_tools() -> List[BaseTool]:
    """
    Get all Project Lad tools.
    
    Returns:
        List of Project Lad tool instances
    """
    return [
        ListProjectsTool(),
        GetProjectTool(),
        GetProjectWorksTool(),
        GetMilestonesTool(),
        GetIndicatorsTool(),
        GetIndicatorAnalyticsTool(),
        GetResourceUtilizationTool(),  # NEW: Resource utilization
    ]




