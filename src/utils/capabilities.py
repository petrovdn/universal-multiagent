"""
Dynamic capabilities detection and prompt generation.
Determines available capabilities based on connected MCP servers and generates appropriate system prompts.
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import json
import logging

from src.utils.mcp_loader import get_mcp_manager
from src.utils.config_loader import get_config

logger = logging.getLogger(__name__)


# Mapping of MCP server names to human-readable category names
SERVER_CATEGORY_NAMES = {
    "gmail": "Email (Gmail)",
    "calendar": "Calendar",
    "sheets": "Spreadsheets",
    "google_workspace": "File Management",
}

# Tool name patterns to category mapping for better grouping
TOOL_CATEGORY_PATTERNS = {
    "email": ["email", "gmail", "send", "draft", "search_emails", "read_email"],
    "calendar": ["calendar", "event", "availability", "schedule"],
    "spreadsheets": ["spreadsheet", "sheet", "row", "cell", "spreadsheets"],
    "files": ["file", "document", "workspace", "folder", "drive", "list_files", "search_files"],
    "documents": ["document", "doc", "create_document", "read_document", "update_document"],
}


def categorize_tool(tool_name: str, tool_description: str) -> str:
    """
    Categorize a tool based on its name and description.
    
    Args:
        tool_name: Name of the tool
        tool_description: Description of the tool
        
    Returns:
        Category name
    """
    tool_lower = tool_name.lower()
    desc_lower = tool_description.lower()
    combined = f"{tool_lower} {desc_lower}"
    
    for category, patterns in TOOL_CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if pattern in combined:
                return category
    
    return "general"


async def get_available_capabilities() -> Dict[str, Any]:
    """
    Get available capabilities based on connected integrations and MCP servers.
    
    Returns:
        Dictionary with capabilities information:
        - enabled_servers: List of enabled server names
        - tools_by_category: Tools grouped by category
        - server_status: Status of each server
        - capabilities_description: Human-readable description of capabilities
    """
    mcp_manager = get_mcp_manager()
    config = get_config()
    
    # Check token existence
    token_paths = {
        "gmail": config.tokens_dir / "gmail_token.json",
        "calendar": config.tokens_dir / "google_calendar_token.json",
        "sheets": config.tokens_dir / "google_sheets_token.json",
        "google_workspace": config.tokens_dir / "google_workspace_token.json",
    }
    
    # Check workspace folder configuration
    workspace_folder_id = None
    workspace_folder_name = None
    workspace_config_path = config.config_dir / "workspace_config.json"
    if workspace_config_path.exists():
        try:
            workspace_config = json.loads(workspace_config_path.read_text())
            workspace_folder_id = workspace_config.get("folder_id")
            workspace_folder_name = workspace_config.get("folder_name")
        except Exception as e:
            logger.warning(f"Could not read workspace config: {e}")
    
    # Get health status of MCP servers
    try:
        health_status = await mcp_manager.health_check()
    except Exception as e:
        logger.warning(f"Could not get MCP health status: {e}")
        health_status = {}
    
    # Get all tools from all servers
    all_tools = {}
    try:
        all_tools = mcp_manager.get_all_tools()
    except Exception as e:
        logger.warning(f"Could not get all tools: {e}")
    
    # Determine enabled servers (have tokens and are enabled in config or have tools)
    enabled_servers = []
    server_status = {}
    
    for server_name in ["gmail", "calendar", "sheets", "google_workspace"]:
        token_exists = token_paths.get(server_name, Path("/dev/null")).exists()
        
        # Check if server is enabled in config
        config_enabled = False
        connection = mcp_manager.connections.get(server_name)
        if connection:
            config_enabled = connection.config.enabled
        
        health = health_status.get(server_name, {})
        connected = health.get("connected", False)
        tools_count = health.get("tools_count", 0)
        
        # Server is enabled if it has a token and (is enabled in config or has connected/loaded tools)
        is_enabled = token_exists and (config_enabled or connected or tools_count > 0)
        
        server_status[server_name] = {
            "enabled": is_enabled,
            "token_exists": token_exists,
            "connected": connected,
            "tools_count": tools_count,
        }
        
        if is_enabled:
            enabled_servers.append(server_name)
    
    # Group tools by category
    tools_by_category: Dict[str, List[Dict[str, Any]]] = {}
    
    for tool_name, tool_info in all_tools.items():
        if isinstance(tool_info, dict):
            description = tool_info.get("description", "")
            category = categorize_tool(tool_name, description)
            
            if category not in tools_by_category:
                tools_by_category[category] = []
            
            tools_by_category[category].append({
                "name": tool_name,
                "description": description,
            })
    
    # Generate human-readable capabilities description
    capabilities_description = _generate_capabilities_description(
        enabled_servers,
        tools_by_category,
        workspace_folder_id,
        workspace_folder_name
    )
    
    return {
        "enabled_servers": enabled_servers,
        "tools_by_category": tools_by_category,
        "server_status": server_status,
        "capabilities_description": capabilities_description,
        "workspace_folder_id": workspace_folder_id,
        "workspace_folder_name": workspace_folder_name,
    }


def _generate_capabilities_description(
    enabled_servers: List[str],
    tools_by_category: Dict[str, List[Dict[str, Any]]],
    workspace_folder_id: Optional[str],
    workspace_folder_name: Optional[str]
) -> str:
    """
    Generate human-readable description of available capabilities.
    
    Args:
        enabled_servers: List of enabled server names
        tools_by_category: Tools grouped by category
        workspace_folder_id: Optional workspace folder ID
        workspace_folder_name: Optional workspace folder name
        
    Returns:
        Human-readable description string
    """
    if not enabled_servers:
        return "Доступные интеграции не подключены. Подключите интеграции для использования системы."
    
    descriptions = []
    
    # Email capabilities
    if "gmail" in enabled_servers:
        email_tools = tools_by_category.get("email", [])
        if email_tools:
            descriptions.append("- Email operations: отправка писем, создание черновиков, поиск и чтение писем")
    
    # Calendar capabilities
    if "calendar" in enabled_servers:
        calendar_tools = tools_by_category.get("calendar", [])
        if calendar_tools:
            descriptions.append("- Calendar operations: создание событий, просмотр календаря, проверка доступности")
    
    # Spreadsheets capabilities
    if "sheets" in enabled_servers:
        sheet_tools = tools_by_category.get("spreadsheets", [])
        if sheet_tools:
            descriptions.append("- Spreadsheet operations: создание таблиц, добавление данных, чтение и обновление ячеек")
    
    # File management capabilities
    if "google_workspace" in enabled_servers:
        file_tools = tools_by_category.get("files", [])
        doc_tools = tools_by_category.get("documents", [])
        if file_tools or doc_tools:
            folder_info = ""
            if workspace_folder_id and workspace_folder_name:
                folder_info = f" в выбранной папке '{workspace_folder_name}'"
            descriptions.append(f"- File management{folder_info}: поиск файлов, создание документов, чтение и редактирование файлов")
    
    if not descriptions:
        return "Интеграции подключены, но инструменты пока не обнаружены."
    
    return "\n".join(descriptions)


def build_main_agent_prompt(capabilities: Dict[str, Any]) -> str:
    """
    Build system prompt for main agent based on available capabilities.
    
    Args:
        capabilities: Capabilities dictionary from get_available_capabilities()
        
    Returns:
        System prompt string
    """
    enabled_servers = capabilities.get("enabled_servers", [])
    capabilities_desc = capabilities.get("capabilities_description", "Нет доступных возможностей")
    
    # Base prompt
    prompt = """You are an expert AI assistant. Your role is to help users with their tasks using available integrations and tools.

## Language Requirements
- All your reasoning (thinking process) must be in Russian
- All your responses to users must be in Russian
- Use Russian for all internal reasoning and decision-making
- When you think through problems, use Russian language in your reasoning

## Your Available Capabilities

"""
    
    prompt += capabilities_desc + "\n\n"
    
    # Add tool usage guidance
    prompt += """## How to Handle Requests

You have access to various tools depending on which integrations are enabled. When a user makes a request:

1. **Analyze the request**: Determine what the user wants to accomplish
2. **Identify relevant tools**: Based on available capabilities, determine which tools can help
3. **Use appropriate tools**: Call the relevant tools to complete the task
4. **Provide clear feedback**: Report results clearly with details

## Key Principles

- Adapt your behavior based on available tools - if file management tools are available, use them for file operations
- If calendar tools are available, use them for scheduling tasks
- If email tools are available, use them for email operations
- If spreadsheet tools are available, use them for data management
- Always confirm important actions before executing them
- Provide clear, structured responses
- Remember context from previous turns
- Handle errors gracefully with suggestions

## Response Format

Structure your responses clearly:
1. **Understanding**: "Я понимаю, что вы хотите..."
2. **Plan** (if needed): "Вот что я сделаю: [steps]"
3. **Confirmation**: "Продолжить с [action]?"
4. **Execution**: Use appropriate tools
5. **Result**: "✅ [Action] completed: [details]"

Be helpful, professional, and efficient."""
    
    return prompt


def build_step_executor_prompt(
    capabilities: Dict[str, Any],
    workspace_folder_info: Optional[str] = None
) -> str:
    """
    Build system prompt for step executor based on available capabilities.
    
    Args:
        capabilities: Capabilities dictionary from get_available_capabilities()
        workspace_folder_info: Optional workspace folder context information
        
    Returns:
        System prompt string
    """
    enabled_servers = capabilities.get("enabled_servers", [])
    tools_by_category = capabilities.get("tools_by_category", {})
    
    # Base prompt
    prompt = """Ты эксперт-ассистент по выполнению задач. Выполни текущий шаг плана эффективно и точно.

⚠️ ВАЖНО: ВСЕ ответы должны быть на РУССКОМ языке! ⚠️

ПРИНЦИПЫ ВЫПОЛНЕНИЯ:

"""
    
    # Add workspace folder priority if applicable
    if workspace_folder_info:
        prompt += f"""1. **ПРИОРИТЕТ РАБОЧЕЙ ПАПКИ GOOGLE DRIVE**:
   {workspace_folder_info}
   
   ⚠️ ВАЖНО: 
   - Папка УЖЕ задана в настройках, НЕ передавай folder_id как параметр!
   - Инструмент search_workspace_files автоматически использует эту папку
   - Просто передай query, mime_type (опционально) и max_results
   - Все операции с файлами относятся к этой папке автоматически
   - НЕ ищи в локальных директориях, если указана рабочая папка

"""
    else:
        prompt += """1. **ИСПОЛЬЗОВАНИЕ ДОСТУПНЫХ ИНСТРУМЕНТОВ**:
   - Анализируй доступные инструменты и используй подходящие для текущей задачи
   - Если доступны инструменты для работы с файлами - используй их для поиска и работы с файлами
   - Если доступны инструменты для работы с таблицами - используй их для операций с таблицами
   - Адаптируй своё поведение на основе доступных возможностей

"""
    
    # Add tool categories information
    tool_categories_info = []
    if "files" in tools_by_category or "documents" in tools_by_category:
        tool_categories_info.append("- Для работы с файлами используй инструменты поиска, чтения и создания файлов")
    if "spreadsheets" in tools_by_category:
        tool_categories_info.append("- Для работы с таблицами используй инструменты работы с таблицами")
    if "email" in tools_by_category:
        tool_categories_info.append("- Для работы с письмами используй инструменты email")
    if "calendar" in tools_by_category:
        tool_categories_info.append("- Для работы с календарём используй инструменты календаря")
    
    if tool_categories_info:
        prompt += "   " + "\n   ".join(tool_categories_info) + "\n\n"
    
    # Continue with standard execution principles
    prompt += """2. **ФОРМАТ РЕЗУЛЬТАТА ШАГА**:
   
   ⚠️ КРИТИЧЕСКИ ВАЖНО: Результат шага должен отвечать на название шага, а не описывать процесс!
   
   **Правильные примеры:**
   - Шаг "Найти файл test2" → Результат: "Найден файл Тест2 (Google Sheets, ID: xxx)" ИЛИ "Файл не найден, остановка выполнения"
   - Шаг "Прочитать содержимое файла" → Результат: "Содержимое файла: [текст содержимого]"
   - Шаг "Записать три новые строки" → Результат: "Записаны три строки: [список строк]"
   
   **Неправильные примеры (НЕ ДЕЛАЙ ТАК):**
   - "Буду искать файл..." (это процесс, не результат)
   - "Попытка 1: Поиск по точному совпадению..." (это процесс, не результат)
   - "Вызываю инструмент search_files..." (это процесс, не результат)
   
   **Правило:** Результат = ответ на вопрос "Что было достигнуто в этом шаге?"

3. **ВЫПОЛНЕНИЕ ДЕЙСТВИЙ С ИНСТРУМЕНТАМИ**:
   
   ⚠️ КРИТИЧЕСКИ ВАЖНО: Ты ДОЛЖЕН реально вызывать инструменты, а не описывать процесс!
   
   **Правильный вызов инструмента поиска:**
   - search_workspace_files(query="Рабочая таблица", max_results=100)
   - НЕ передавай folder_id - папка уже задана в настройках!
   
   **Неправильные примеры (НЕ ДЕЛАЙ ТАК):**
   - search_workspace_files(query="...", folder_id="...") - folder_id не нужен!
   - <search_files>...</search_files> - это XML, не работает!
   - "Ищу файл..." - это описание, не вызов инструмента!
   
   - Делай разумное количество попыток (2-3 максимум) с разными параметрами
   - Если после попыток действие не выполнено - останови выполнение с маркером "🛑 ТРЕБУЕТСЯ ПОМОЩЬ ПОЛЬЗОВАТЕЛЯ"
   - НЕ пиши о попытках без реальных вызовов инструментов

4. **ВЫБОР ИНСТРУМЕНТОВ**:
   
   - Определи тип найденного файла (таблица Google, текстовый документ, etc.)
   - Используй соответствующий инструмент для работы с этим типом файла:
     * Таблица Google → используй MCP таблиц Google (инструменты sheets_*)
     * Документ Google → используй MCP документов Google (инструменты workspace_*)
     * Текстовый файл → используй соответствующие инструменты чтения/записи
   - Если доступны специализированные инструменты - используй их вместо универсальных

5. **ОСТАНОВКА ПРИ НЕУДАЧЕ**:
   
   - Если шаг критически важен и не может быть выполнен после 2-3 попыток
   - Останови выполнение с маркером "🛑 ТРЕБУЕТСЯ ПОМОЩЬ ПОЛЬЗОВАТЕЛЯ"
   - НЕ пытайся продолжить без необходимых данных

6. **ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ**:
   
   Если тебе нужна помощь пользователя для принятия решения (например, выбор из нескольких вариантов), используй формат:
   
   🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ
   
   Вопрос: [четкий вопрос к пользователю]
   
   Варианты:
   1. [Описание варианта 1]
   2. [Описание варианта 2]
   ...
   
   Или используй JSON формат для более структурированных данных:
   {
     "🔍 ЗАПРОС ПОМОЩИ ПОЛЬЗОВАТЕЛЯ": {
       "question": "...",
       "options": [
         {"id": "1", "label": "...", "description": "...", "data": {...}},
         ...
       ]
     }
   }
   
   **КРИТИЧЕСКИ ВАЖНО**: 
   - Если инструмент вернул JSON с запросом помощи (например, при поиске файлов найдено несколько вариантов), 
     ты ДОЛЖЕН передать этот JSON БЕЗ ИЗМЕНЕНИЙ в своем ответе, а НЕ выбирать вариант самостоятельно.
   - Если инструмент вернул текст вида "Найдено N файл(ов)... Требуется выбор пользователя:" с JSON - 
     передай ВЕСЬ этот текст с JSON в своем ответе БЕЗ ИЗМЕНЕНИЙ.
   - НЕ интерпретируй результат поиска как обычный текст - если инструмент вернул JSON с запросом помощи, 
     это означает, что требуется выбор пользователя, а не твое решение.
   - НЕ выбирай файл сам - всегда запрашивай выбор пользователя, если найдено несколько файлов.
   
   Примеры использования:
   - При поиске файлов: если найдено несколько файлов с похожими именами
   - При отправке писем: если найдено несколько адресов получателя
   - При любых ситуациях, где требуется выбор из нескольких вариантов
   
   После получения ответа пользователя - продолжай выполнение с выбранным вариантом, используя данные из выбранной опции.

Все ответы на русском языке."""
    
    return prompt


def build_planning_prompt() -> str:
    """
    Build system prompt for planning phase.
    This prompt is more generic and doesn't need specific capabilities.
    
    Returns:
        System prompt string for planning
    """
    return """Ты эксперт по планированию задач. Твоя задача - создать детальный пошаговый план выполнения запроса пользователя.

⚠️ ВАЖНО: ВСЕ ответы должны быть на РУССКОМ языке! ⚠️

КОНТЕКСТ РАБОТЫ С ФАЙЛАМИ:
- Если пользователь говорит о поиске, чтении или записи файлов, он имеет в виду прикрепленную папку Google Drive
- Поиск файлов должен быть нестрогим (например, "тест2" может соответствовать "Тест2", "test2", "TEST2")
- Шаги должны быть общими: "Найти файл тест2", а не "Попытка 1: искать как X, попытка 2: искать как Y"
- При планировании не указывай конкретные попытки поиска - просто опиши общую задачу поиска

МЕТОДОЛОГИЯ ПЛАНИРОВАНИЯ:

1. **Определи оптимальное количество шагов**:
   - Если задачу логично выполнить за 1 шаг - создай 1 шаг
   - Если задачу нужно разбить на несколько этапов - создай несколько шагов
   - Количество шагов зависит от сложности задачи (может быть 1, 2, 3, 5 или больше)
   
   Примеры:
   
   Простая задача (1 шаг):
   * "Создай файл README.md" → Шаг 1: "Создать файл README.md с базовым содержимым"
   
   Сложная задача (несколько шагов):
   * "Найди файл test2 и напиши поздравления" → 
     - Шаг 1: "Найти файл test2 используя поиск"
     - Шаг 2: "Извлечь политику написания из файла"
     - Шаг 3: "Создать поздравления по найденной политике"

2. **Каждый шаг должен быть**:
   - Понятным и конкретным (ясно, что нужно сделать)
   - Логически обоснованным (есть причина для отдельного шага)
   - Выполнимым (можно реально выполнить)

3. **Будь проактивным**:
   - НЕ создавай шаги типа "Попросить пользователя предоставить файл"
   - Вместо этого: "Найти файл используя доступные инструменты поиска"
   - Планируй автономное выполнение

4. **Логическая последовательность**:
   - Ранние шаги собирают информацию
   - Средние шаги обрабатывают/анализируют
   - Финальные шаги создают результат

Формат ответа (ТОЛЬКО валидный JSON, без markdown):
{
    "plan": "Краткое описание подхода (1-2 предложения)",
    "steps": [
        "Шаг 1: Описание действия",
        "Шаг 2: Описание действия"
    ]
}

Помни: количество шагов определяется логикой задачи, не искусственными требованиями."""

