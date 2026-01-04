"""
Project Lad MCP Server.
Provides MCP tools for Project Lad operations via REST API.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import httpx

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logger = logging.getLogger(__name__)


class ProjectLadMCPServer:
    """MCP Server for Project Lad operations."""
    
    def __init__(self, config_path: Path):
        """
        Initialize Project Lad MCP Server.
        
        Args:
            config_path: Path to Project Lad configuration file
        """
        self.config_path = Path(config_path)
        self._config: Optional[Dict[str, Any]] = None
        self._auth_token: Optional[str] = None
        self.server = Server("projectlad-mcp")
        self._setup_tools()
    
    def _get_config(self) -> Dict[str, Any]:
        """Get or load Project Lad configuration."""
        if self._config is None:
            if not self.config_path.exists():
                raise ValueError(
                    f"Project Lad config not found at {self.config_path}. "
                    "Please configure Project Lad connection first."
                )
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            
            if not self._config:
                raise ValueError(
                    f"Failed to load Project Lad config from {self.config_path}."
                )
        
        return self._config
    
    async def _authenticate(self) -> str:
        """Authenticate and get access token."""
        if self._auth_token:
            return self._auth_token
        
        config = self._get_config()
        base_url = config.get('base_url', 'https://api.staging.po.ladcloud.ru')
        email = config.get('email')
        password = config.get('password')
        
        if not email or not password:
            raise ValueError("Email and password must be configured")
        
        url = f"{base_url}/v1/auth/login"
        payload = {
            "email": email,
            "password": password
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            
            if response.status_code != 200:
                error_text = response.text[:500]
                raise ValueError(
                    f"Authentication failed (status {response.status_code}): {error_text}"
                )
            
            data = response.json()
            
            # API возвращает токен в result.access_token
            result = data.get('result', {})
            if isinstance(result, dict):
                self._auth_token = (
                    result.get('access_token') or 
                    result.get('token') or 
                    result.get('accessToken')
                )
            
            # Если не нашли в result, пробуем напрямую
            if not self._auth_token:
                self._auth_token = (
                    data.get('token') or 
                    data.get('access_token') or 
                    data.get('accessToken') or
                    data.get('auth_token') or
                    data.get('apiKey')
                )
            
            if not self._auth_token:
                # Если токен не найден, выводим структуру ответа для отладки
                logger.warning(f"Token not found in response. Response keys: {list(data.keys())}")
                raise ValueError(
                    f"Token not found in authentication response. "
                    f"Response structure: {json.dumps(data, indent=2)[:500]}"
                )
            
            return self._auth_token
    
    async def _api_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make API request to Project Lad endpoint.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., "/v2/project/list")
            params: Query parameters
            json_data: JSON body for POST/PUT requests
        
        Returns:
            JSON response as dict
        """
        config = self._get_config()
        base_url = config.get('base_url', 'https://api.staging.po.ladcloud.ru')
        url = f"{base_url}{path}"
        
        token = await self._authenticate()
        # По Swagger используется apiKey в header Authorization
        # Пробуем разные форматы
        if token.startswith('Bearer '):
            auth_header = token
        elif token.startswith('ApiKey ') or token.startswith('apiKey '):
            auth_header = token
        else:
            # Пробуем сначала без Bearer (как apiKey), потом с Bearer
            auth_header = token
        
        headers = {
            "Authorization": auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = await client.post(url, headers=headers, params=params, json=json_data)
            elif method.upper() == "PUT":
                response = await client.put(url, headers=headers, params=params, json=json_data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            data = response.json()
            
            # API возвращает данные в формате {"result": ...}
            # Извлекаем result если он есть, иначе возвращаем весь ответ
            if isinstance(data, dict) and 'result' in data:
                return data
            return data
    
    async def _get_latest_version_id(self, project_id: str) -> str:
        """Get latest project version ID."""
        versions_data = await self._api_request(
            "GET", 
            f"/v2/project/{project_id}/version/list"
        )
        
        # Извлекаем версии из result
        versions = []
        if isinstance(versions_data, dict) and "result" in versions_data:
            versions = versions_data["result"]
        elif isinstance(versions_data, list):
            versions = versions_data
        elif isinstance(versions_data, dict) and "items" in versions_data:
            versions = versions_data.get("items", [])
        
        if versions and len(versions) > 0:
            # Ищем текущую версию (is_current=True) или берем первую
            for version in versions:
                if version.get("is_current"):
                    return version.get("id")
            return versions[0].get("id")
        
        raise ValueError("No project versions found")
    
    def _setup_tools(self):
        """Register MCP tools."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available Project Lad tools."""
            return [
                Tool(
                    name="projectlad_list_projects",
                    description="Get list of available projects",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "permission_filter": {
                                "type": "string",
                                "description": "Optional permission filter"
                            },
                            "with_groups": {
                                "type": "boolean",
                                "description": "Include project groups",
                                "default": False
                            }
                        }
                    }
                ),
                Tool(
                    name="projectlad_get_project",
                    description="Get project details by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "Project ID"
                            }
                        },
                        "required": ["project_id"]
                    }
                ),
                Tool(
                    name="projectlad_get_project_works",
                    description="Get list of works (items) for a project version",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "Project ID"
                            },
                            "project_version_id": {
                                "type": "string",
                                "description": "Project version ID (optional, uses latest if not provided)"
                            }
                        },
                        "required": ["project_id"]
                    }
                ),
                Tool(
                    name="projectlad_get_milestones",
                    description="Get milestones and their deadlines for a project",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "Project ID"
                            },
                            "project_version_id": {
                                "type": "string",
                                "description": "Project version ID (optional)"
                            }
                        },
                        "required": ["project_id"]
                    }
                ),
                Tool(
                    name="projectlad_get_indicators",
                    description="Get indicator values for a project with period filtering",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "Project ID"
                            },
                            "project_version_id": {
                                "type": "string",
                                "description": "Project version ID (optional)"
                            },
                            "from_date": {
                                "type": "string",
                                "description": "Start date (ISO 8601 format: YYYY-MM-DD)",
                                "format": "date"
                            },
                            "to_date": {
                                "type": "string",
                                "description": "End date (ISO 8601 format: YYYY-MM-DD)",
                                "format": "date"
                            },
                            "indicator_ids": {
                                "type": "array",
                                "description": "Optional list of specific indicator IDs to filter",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["project_id"]
                    }
                ),
                Tool(
                    name="projectlad_get_indicator_analytics",
                    description="Get indicator analytics with various data slices by period",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "Project ID"
                            },
                            "project_version_id": {
                                "type": "string",
                                "description": "Project version ID (optional)"
                            },
                            "from_date": {
                                "type": "string",
                                "description": "Start date (ISO 8601 format: YYYY-MM-DD)",
                                "format": "date"
                            },
                            "to_date": {
                                "type": "string",
                                "description": "End date (ISO 8601 format: YYYY-MM-DD)",
                                "format": "date"
                            }
                        },
                        "required": ["project_id", "from_date", "to_date"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                # ========== LIST PROJECTS ==========
                if name == "projectlad_list_projects":
                    params = {}
                    if arguments.get("permission_filter"):
                        params["permission_filter"] = arguments["permission_filter"]
                    if arguments.get("with_groups"):
                        params["withGroups"] = arguments["with_groups"]
                    
                    data = await self._api_request("GET", "/v2/project/list", params=params)
                    
                    # Извлекаем список проектов из result
                    projects = data.get('result', []) if isinstance(data, dict) else data
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "projects": projects,
                            "count": len(projects) if isinstance(projects, list) else 0
                        }, indent=2, ensure_ascii=False, default=str)
                    )]
                
                # ========== GET PROJECT ==========
                elif name == "projectlad_get_project":
                    project_id = arguments.get("project_id")
                    data = await self._api_request("GET", f"/v1/project/{project_id}")
                    
                    # Извлекаем проект из result
                    project = data.get('result', data) if isinstance(data, dict) else data
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps(project, indent=2, ensure_ascii=False, default=str)
                    )]
                
                # ========== GET PROJECT WORKS ==========
                elif name == "projectlad_get_project_works":
                    project_id = arguments.get("project_id")
                    project_version_id = arguments.get("project_version_id")
                    
                    if not project_version_id:
                        project_version_id = await self._get_latest_version_id(project_id)
                    
                    # Получаем элементы проекта (работы)
                    data = await self._api_request(
                        "POST",
                        "/v2/project/data/tree/list",
                        json_data={
                            "project_id": project_id,
                            "project_version_id": project_version_id
                        }
                    )
                    
                    # Извлекаем работы из result
                    works = data.get('result', data) if isinstance(data, dict) else data
                    if isinstance(works, dict) and 'items' in works:
                        works = works['items']
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "works": works if isinstance(works, list) else [works],
                            "count": len(works) if isinstance(works, list) else 1
                        }, indent=2, ensure_ascii=False, default=str)
                    )]
                
                # ========== GET MILESTONES ==========
                elif name == "projectlad_get_milestones":
                    project_id = arguments.get("project_id")
                    project_version_id = arguments.get("project_version_id")
                    
                    if not project_version_id:
                        project_version_id = await self._get_latest_version_id(project_id)
                    
                    # Получаем работы
                    works_data = await self._api_request(
                        "POST",
                        "/v2/project/data/tree/list",
                        json_data={
                            "project_id": project_id,
                            "project_version_id": project_version_id
                        }
                    )
                    
                    # Извлекаем работы из result
                    works = works_data.get('result', works_data) if isinstance(works_data, dict) else works_data
                    if isinstance(works, dict) and 'items' in works:
                        works = works['items']
                    if not isinstance(works, list):
                        works = [works] if works else []
                    
                    # Фильтруем вехи (предполагаем, что вехи имеют type='milestone' или is_milestone=true)
                    milestones = []
                    
                    def extract_milestones(items, parent_path=""):
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                                
                            item_type = str(item.get("type", "")).lower()
                            entity_type = str(item.get("entity_type", "")).lower()
                            is_milestone = item.get("is_milestone", False)
                            
                            # Проверяем, является ли элемент вехой
                            if ("milestone" in item_type or 
                                "milestone" in entity_type or 
                                is_milestone or
                                item.get("is_milestone")):
                                milestones.append({
                                    "id": item.get("id"),
                                    "name": item.get("name") or item.get("title"),
                                    "start_date": item.get("start_date") or item.get("startDate"),
                                    "end_date": item.get("end_date") or item.get("endDate"),
                                    "deadline": item.get("deadline") or item.get("end_date") or item.get("endDate"),
                                    "path": f"{parent_path}/{item.get('name', item.get('title', ''))}" if parent_path else (item.get("name") or item.get("title", ""))
                                })
                            
                            # Рекурсивно обрабатываем дочерние элементы
                            if "children" in item and isinstance(item["children"], list):
                                extract_milestones(
                                    item["children"], 
                                    f"{parent_path}/{item.get('name', item.get('title', ''))}" if parent_path else (item.get("name") or item.get("title", ""))
                                )
                    
                    extract_milestones(works)
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "project_id": project_id,
                            "project_version_id": project_version_id,
                            "milestones": milestones,
                            "count": len(milestones)
                        }, indent=2, ensure_ascii=False, default=str)
                    )]
                
                # ========== GET INDICATORS ==========
                elif name == "projectlad_get_indicators":
                    project_id = arguments.get("project_id")
                    project_version_id = arguments.get("project_version_id")
                    from_date = arguments.get("from_date")
                    to_date = arguments.get("to_date")
                    indicator_ids = arguments.get("indicator_ids")
                    
                    if not project_version_id:
                        project_version_id = await self._get_latest_version_id(project_id)
                    
                    # Получаем значения показателей
                    params = {}
                    if from_date:
                        params["from_date"] = from_date
                    if to_date:
                        params["to_date"] = to_date
                    
                    data = await self._api_request(
                        "GET",
                        f"/v1/project/{project_id}/version/{project_version_id}/item-indicator-value/list",
                        params=params
                    )
                    
                    # Извлекаем показатели из result
                    indicators = data.get('result', data) if isinstance(data, dict) else data
                    if isinstance(indicators, dict) and 'items' in indicators:
                        indicators = indicators['items']
                    if not isinstance(indicators, list):
                        indicators = [indicators] if indicators else []
                    
                    # Фильтруем по indicator_ids если указаны
                    if indicator_ids:
                        indicators = [
                            item for item in indicators
                            if item.get("indicator_id") in indicator_ids
                        ]
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "indicators": indicators,
                            "count": len(indicators)
                        }, indent=2, ensure_ascii=False, default=str)
                    )]
                
                # ========== GET INDICATOR ANALYTICS ==========
                elif name == "projectlad_get_indicator_analytics":
                    project_id = arguments.get("project_id")
                    project_version_id = arguments.get("project_version_id")
                    from_date = arguments.get("from_date")
                    to_date = arguments.get("to_date")
                    
                    if not project_version_id:
                        project_version_id = await self._get_latest_version_id(project_id)
                    
                    # Получаем аналитику по показателям
                    data = await self._api_request(
                        "GET",
                        f"/v1/project/version/{project_version_id}/indicator-analytics/list",
                        params={
                            "from_date": from_date,
                            "to_date": to_date
                        }
                    )
                    
                    # Извлекаем аналитику из result
                    analytics = data.get('result', data) if isinstance(data, dict) else data
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "analytics": analytics,
                            "period": {
                                "from_date": from_date,
                                "to_date": to_date
                            }
                        }, indent=2, ensure_ascii=False, default=str)
                    )]
                
                else:
                    raise ValueError(f"Unknown tool: {name}")
                    
            except httpx.HTTPStatusError as e:
                error_msg = f"HTTP error {e.response.status_code}: {e.response.text[:500]}"
                logger.error(f"API request failed: {error_msg}")
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": error_msg}, indent=2, ensure_ascii=False)
                )]
            except httpx.RequestError as e:
                error_msg = f"Request error: {str(e)}"
                logger.error(f"API request failed: {error_msg}")
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": error_msg}, indent=2, ensure_ascii=False)
                )]
            except Exception as e:
                error_msg = f"Tool execution failed: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": error_msg}, indent=2, ensure_ascii=False)
                )]
    
    async def run(self):
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point for the MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Project Lad MCP Server")
    parser.add_argument(
        "--config-path",
        type=str,
        default="config/projectlad_config.json",
        help="Path to Project Lad configuration file"
    )
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = ProjectLadMCPServer(Path(args.config_path))
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())

