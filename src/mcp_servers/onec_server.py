"""
1C:Бухгалтерия OData MCP Server.
Provides MCP tools for reading data from 1C:Бухгалтерия Фреш via OData.
"""

import asyncio
import json
import sys
import base64
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import logging
import httpx
from collections import defaultdict

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from src.utils.config_loader import get_onec_config, OneCConfig

logger = logging.getLogger(__name__)


class OneCMCPServer:
    """MCP Server for 1C:Бухгалтерия OData operations."""
    
    def __init__(self, config_path: Path):
        """
        Initialize 1C MCP Server.
        
        Args:
            config_path: Path to 1C configuration file
        """
        self.config_path = Path(config_path)
        self._config: Optional[OneCConfig] = None
        self.server = Server("onec-mcp")
        self._setup_tools()
    
    def _get_config(self) -> OneCConfig:
        """Get or load 1C configuration."""
        if self._config is None:
            if self.config_path.exists():
                self._config = get_onec_config()
            else:
                raise ValueError(
                    f"1C config not found at {self.config_path}. "
                    "Please configure 1C OData connection first via /api/integrations/onec/config"
                )
            
            if not self._config:
                raise ValueError(
                    f"Failed to load 1C config from {self.config_path}. "
                    "Please configure 1C OData connection first via /api/integrations/onec/config"
                )
        
        return self._config
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get Basic Auth headers for OData requests."""
        config = self._get_config()
        credentials = f"{config.username}:{config.password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return {
            "Authorization": f"Basic {encoded_credentials}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    async def _odata_request(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make OData request to 1C endpoint.
        
        Args:
            path: OData path (e.g., "Document_РеализацияТоваровУслуг")
            params: Query parameters (e.g., {"$top": 10, "$filter": "..."})
        
        Returns:
            JSON response as dict
        """
        config = self._get_config()
        url = f"{config.odata_base_url}/{path}"
        
        headers = self._get_auth_headers()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
    
    def _setup_tools(self):
        """Register MCP tools."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available 1C OData tools."""
            return [
                Tool(
                    name="onec_ping",
                    description="Test connection to 1C OData endpoint by fetching $metadata.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="onec_sales_list",
                    description="Get list of sales documents (Реализация товаров и услуг) for a period.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "from": {
                                "type": "string",
                                "description": "Start date (ISO 8601 format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
                                "format": "date-time"
                            },
                            "to": {
                                "type": "string",
                                "description": "End date (ISO 8601 format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
                                "format": "date-time"
                            },
                            "organization_guid": {
                                "type": "string",
                                "description": "Optional organization GUID for filtering"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of results (default: 100, max: 1000)",
                                "default": 100
                            }
                        },
                        "required": ["from", "to"]
                    }
                ),
                Tool(
                    name="onec_revenue_by_counterparty_month",
                    description="Get revenue by counterparty aggregated by month from sales documents.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "from": {
                                "type": "string",
                                "description": "Start date (ISO 8601 format: YYYY-MM-DD)",
                                "format": "date"
                            },
                            "to": {
                                "type": "string",
                                "description": "End date (ISO 8601 format: YYYY-MM-DD)",
                                "format": "date"
                            },
                            "organization_guid": {
                                "type": "string",
                                "description": "Optional organization GUID for filtering"
                            }
                        },
                        "required": ["from", "to"]
                    }
                ),
                Tool(
                    name="onec_salary_by_employee_month",
                    description="Get salary by employee aggregated by month from accounting entries (Kt 70).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "from": {
                                "type": "string",
                                "description": "Start date (ISO 8601 format: YYYY-MM-DD)",
                                "format": "date"
                            },
                            "to": {
                                "type": "string",
                                "description": "End date (ISO 8601 format: YYYY-MM-DD)",
                                "format": "date"
                            },
                            "organization_guid": {
                                "type": "string",
                                "description": "Optional organization GUID for filtering"
                            }
                        },
                        "required": ["from", "to"]
                    }
                ),
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                # ========== CONNECTION TEST ==========
                if name == "onec_ping":
                    config = self._get_config()
                    url = f"{config.odata_base_url}/$metadata"
                    headers = self._get_auth_headers()
                    
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(url, headers=headers)
                        response.raise_for_status()
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "connected": True,
                            "message": "Successfully connected to 1C OData endpoint",
                            "odata_url": config.odata_base_url
                        }, indent=2, ensure_ascii=False)
                    )]
                
                # ========== SALES LIST ==========
                elif name == "onec_sales_list":
                    from_date = arguments.get("from")
                    to_date = arguments.get("to")
                    org_guid = arguments.get("organization_guid")
                    max_results = min(arguments.get("max_results", 100), 1000)
                    
                    # Parse dates
                    try:
                        if "T" in from_date:
                            from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
                        else:
                            from_dt = datetime.fromisoformat(f"{from_date}T00:00:00")
                        
                        if "T" in to_date:
                            to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
                        else:
                            to_dt = datetime.fromisoformat(f"{to_date}T23:59:59")
                    except ValueError as e:
                        raise ValueError(f"Invalid date format: {e}")
                    
                    # Build OData query
                    # Note: Field names may vary, using common patterns for БП 3.0
                    filter_parts = [
                        f"Date ge datetime'{from_dt.isoformat()}'",
                        f"Date le datetime'{to_dt.isoformat()}'"
                    ]
                    
                    if org_guid:
                        filter_parts.append(f"Organization_Key eq guid'{org_guid}'")
                    
                    params = {
                        "$filter": " and ".join(filter_parts),
                        "$select": "Ref_Key,Date,Number,Posted,Counterparty_Key,Organization_Key,Amount",
                        "$orderby": "Date desc",
                        "$top": max_results
                    }
                    
                    # Fetch counterparties for names
                    counterparties = {}
                    try:
                        counterparties_data = await self._odata_request("Catalog_Контрагенты", {"$top": 1000})
                        if "value" in counterparties_data:
                            for cp in counterparties_data["value"]:
                                if "Ref_Key" in cp:
                                    counterparties[cp["Ref_Key"]] = cp.get("Description", "Unknown")
                    except Exception as e:
                        logger.warning(f"Failed to fetch counterparties: {e}")
                    
                    # Fetch sales documents
                    try:
                        sales_data = await self._odata_request("Document_РеализацияТоваровУслуг", params)
                    except httpx.HTTPStatusError as e:
                        # Try alternative entity name
                        logger.warning(f"Failed with Document_РеализацияТоваровУслуг, trying alternatives: {e}")
                        try:
                            sales_data = await self._odata_request("Document_Реализация", params)
                        except:
                            raise ValueError(f"Failed to fetch sales documents. Check entity name in OData metadata. Error: {e}")
                    
                    results = []
                    if "value" in sales_data:
                        for doc in sales_data["value"]:
                            cp_key = doc.get("Counterparty_Key", "")
                            cp_name = counterparties.get(cp_key, "Unknown")
                            
                            results.append({
                                "date": doc.get("Date", ""),
                                "number": doc.get("Number", ""),
                                "counterparty_guid": cp_key,
                                "counterparty_name": cp_name,
                                "amount": doc.get("Amount", 0),
                                "posted": doc.get("Posted", False),
                                "ref_key": doc.get("Ref_Key", "")
                            })
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "count": len(results),
                            "period": {
                                "from": from_date,
                                "to": to_date
                            },
                            "sales": results
                        }, indent=2, ensure_ascii=False)
                    )]
                
                # ========== REVENUE BY COUNTERPARTY MONTH ==========
                elif name == "onec_revenue_by_counterparty_month":
                    from_date = arguments.get("from")
                    to_date = arguments.get("to")
                    org_guid = arguments.get("organization_guid")
                    
                    # Parse dates
                    try:
                        from_dt = datetime.fromisoformat(f"{from_date}T00:00:00")
                        to_dt = datetime.fromisoformat(f"{to_date}T23:59:59")
                    except ValueError as e:
                        raise ValueError(f"Invalid date format: {e}")
                    
                    # Build OData query - fetch all sales in period
                    filter_parts = [
                        f"Date ge datetime'{from_dt.isoformat()}'",
                        f"Date le datetime'{to_dt.isoformat()}'",
                        "Posted eq true"  # Only posted documents
                    ]
                    
                    if org_guid:
                        filter_parts.append(f"Organization_Key eq guid'{org_guid}'")
                    
                    params = {
                        "$filter": " and ".join(filter_parts),
                        "$select": "Date,Counterparty_Key,Amount",
                        "$orderby": "Date"
                    }
                    
                    # Fetch counterparties for names
                    counterparties = {}
                    try:
                        counterparties_data = await self._odata_request("Catalog_Контрагенты", {"$top": 1000})
                        if "value" in counterparties_data:
                            for cp in counterparties_data["value"]:
                                if "Ref_Key" in cp:
                                    counterparties[cp["Ref_Key"]] = cp.get("Description", "Unknown")
                    except Exception as e:
                        logger.warning(f"Failed to fetch counterparties: {e}")
                    
                    # Fetch sales documents with pagination
                    all_sales = []
                    skip = 0
                    page_size = 1000
                    
                    while True:
                        page_params = params.copy()
                        page_params["$top"] = page_size
                        page_params["$skip"] = skip
                        
                        try:
                            sales_data = await self._odata_request("Document_РеализацияТоваровУслуг", page_params)
                        except httpx.HTTPStatusError as e:
                            # Try alternative entity name
                            logger.warning(f"Failed with Document_РеализацияТоваровУслуг, trying alternatives: {e}")
                            try:
                                sales_data = await self._odata_request("Document_Реализация", page_params)
                            except:
                                raise ValueError(f"Failed to fetch sales documents. Check entity name in OData metadata. Error: {e}")
                        
                        if "value" not in sales_data or not sales_data["value"]:
                            break
                        
                        all_sales.extend(sales_data["value"])
                        
                        # Check if there are more pages
                        if len(sales_data["value"]) < page_size:
                            break
                        
                        skip += page_size
                        
                        # Safety limit
                        if skip > 10000:
                            logger.warning("Reached pagination limit (10000 records)")
                            break
                    
                    # Aggregate by month and counterparty
                    revenue_by_month_cp = defaultdict(lambda: defaultdict(float))
                    
                    for doc in all_sales:
                        date_str = doc.get("Date", "")
                        if not date_str:
                            continue
                        
                        try:
                            # Parse date (OData format: "2025-01-15T00:00:00" or ISO)
                            if "T" in date_str:
                                doc_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            else:
                                doc_date = datetime.fromisoformat(f"{date_str}T00:00:00")
                            
                            month_key = doc_date.strftime("%Y-%m")
                            cp_key = doc.get("Counterparty_Key", "")
                            amount = float(doc.get("Amount", 0))
                            
                            revenue_by_month_cp[month_key][cp_key] += amount
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Failed to process document date/amount: {e}")
                            continue
                    
                    # Format results
                    results = []
                    for month in sorted(revenue_by_month_cp.keys()):
                        for cp_key, revenue in revenue_by_month_cp[month].items():
                            cp_name = counterparties.get(cp_key, "Unknown")
                            results.append({
                                "month": month,
                                "counterparty_guid": cp_key,
                                "counterparty_name": cp_name,
                                "revenue": round(revenue, 2)
                            })
                    
                    # Sort by month, then by counterparty
                    results.sort(key=lambda x: (x["month"], x["counterparty_name"]))
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "period": {
                                "from": from_date,
                                "to": to_date
                            },
                            "total_records": len(all_sales),
                            "revenue_by_counterparty_month": results
                        }, indent=2, ensure_ascii=False)
                    )]
                
                # ========== SALARY BY EMPLOYEE MONTH ==========
                elif name == "onec_salary_by_employee_month":
                    from_date = arguments.get("from")
                    to_date = arguments.get("to")
                    org_guid = arguments.get("organization_guid")
                    
                    # Parse dates
                    try:
                        from_dt = datetime.fromisoformat(f"{from_date}T00:00:00")
                        to_dt = datetime.fromisoformat(f"{to_date}T23:59:59")
                    except ValueError as e:
                        raise ValueError(f"Invalid date format: {e}")
                    
                    # 1. Получить справочник сотрудников
                    employees = {}
                    try:
                        employees_data = await self._odata_request("Catalog_ФизическиеЛица", {"$top": 1000})
                        if "value" in employees_data:
                            for emp in employees_data["value"]:
                                if "Ref_Key" in emp:
                                    employees[emp["Ref_Key"]] = emp.get("Description", "Unknown")
                    except Exception as e:
                        logger.warning(f"Failed to fetch employees: {e}")
                    
                    # 2. Попробовать получить данные через регистр накопления
                    # В 1С:Бухгалтерия 3.0 проводки обычно хранятся в регистрах
                    # Пробуем AccumulationRegister_ВзаиморасчетыСРаботникамиОрганизаций
                    salary_entries = []
                    
                    # Вариант 1: Попробовать регистр накопления (если есть данные)
                    # Фильтрация по Period через OData не работает, получаем все и фильтруем в коде
                    try:
                        register_names = [
                            "AccumulationRegister_ВзаиморасчетыССотрудниками",  # Правильное название!
                            "AccumulationRegister_БухгалтерскиеВзаиморасчетыССотрудниками",
                            "AccumulationRegister_НачисленияУдержанияПоСотрудникам",
                        ]
                        
                        register_data = None
                        for register_name in register_names:
                            try:
                                # Получаем все записи (фильтрация по Period не работает через OData)
                                register_data = await self._odata_request(register_name, {"$top": 10000, "$orderby": "Period desc"})
                                if "value" in register_data and register_data["value"]:
                                    logger.info(f"Found data in {register_name}: {len(register_data['value'])} entries")
                                    break
                            except Exception as e:
                                logger.debug(f"Failed to fetch from {register_name}: {e}")
                                continue
                        
                        if register_data and "value" in register_data:
                            for entry in register_data["value"]:
                                period_str = entry.get("Period", "")
                                if not period_str:
                                    continue
                                
                                # Фильтруем по периоду в коде
                                try:
                                    if "T" in period_str:
                                        entry_date = datetime.fromisoformat(period_str.replace("Z", "+00:00"))
                                    else:
                                        entry_date = datetime.fromisoformat(f"{period_str}T00:00:00")
                                    
                                    if not (from_dt <= entry_date <= to_dt):
                                        continue
                                except (ValueError, TypeError):
                                    continue
                                
                                # Пробуем разные варианты полей сотрудника
                                employee_key = (entry.get("Сотрудник_Key") or 
                                               entry.get("Работник_Key") or
                                               entry.get("РаботникОрганизаций_Key") or "")
                                amount = entry.get("СуммаОстаток", 0) or entry.get("Сумма", 0)
                                
                                if employee_key and amount:
                                    salary_entries.append({
                                        "date": period_str,
                                        "employee_key": employee_key,
                                        "amount": float(amount)
                                    })
                            
                            if salary_entries:
                                logger.info(f"Extracted {len(salary_entries)} salary entries from accumulation register")
                    except Exception as e:
                        logger.warning(f"Failed to fetch from accumulation register: {e}")
                    
                    # Вариант 2: Если регистр накопления пуст, используем регистр бухгалтерии
                    # Используем RecordsWithExtDimensions для получения проводок с субконто
                    if not salary_entries:
                        logger.info("Using AccountingRegister_Хозрасчетный/RecordsWithExtDimensions (fallback method)")
                        try:
                            # Получаем GUID счета 70
                            account_70_guid = None
                            try:
                                account_data = await self._odata_request("ChartOfAccounts_Хозрасчетный", {"$filter": "Code eq '70'", "$top": 1})
                                if "value" in account_data and account_data["value"]:
                                    account_70_guid = account_data["value"][0].get("Ref_Key")
                                    logger.debug(f"Account 70 GUID: {account_70_guid}")
                            except Exception as e:
                                logger.warning(f"Failed to get account 70 GUID: {e}")
                            
                            # Получаем проводки с субконто через RecordsWithExtDimensions
                            # В этом представлении субконто доступны в полях ExtDimensionCr1, ExtDimensionCr2 и т.д.
                            try:
                                movements = await self._odata_request("AccountingRegister_Хозрасчетный/RecordsWithExtDimensions", {"$top": 10000})
                                
                                if "value" in movements:
                                    for mov in movements["value"]:
                                        # Фильтруем по счету 70 (Кт)
                                        account_cr_key = mov.get("AccountCr_Key", "")
                                        if not account_cr_key:
                                            continue
                                        
                                        # Проверяем, что это счет 70
                                        if account_70_guid and account_cr_key != account_70_guid:
                                            continue
                                        
                                        # Фильтруем по периоду
                                        period_str = mov.get("Period", "")
                                        if not period_str:
                                            continue
                                        
                                        try:
                                            if "T" in period_str:
                                                mov_date = datetime.fromisoformat(period_str.replace("Z", "+00:00"))
                                            else:
                                                mov_date = datetime.fromisoformat(f"{period_str}T00:00:00")
                                            
                                            # Проверяем, что проводка в нужном периоде
                                            if not (from_dt <= mov_date <= to_dt):
                                                continue
                                        except (ValueError, TypeError):
                                            continue
                                        
                                        # Получаем сотрудника из субконто Кт (ExtDimensionCr1)
                                        # Для счета 70 сотрудник хранится в ExtDimensionCr1 (тип Catalog_ФизическиеЛица)
                                        employee_key = mov.get("ExtDimensionCr1", "")
                                        extdim_type = mov.get("ExtDimensionCr1_Type", "")
                                        
                                        # Проверяем, что это действительно сотрудник
                                        if employee_key and "ФизическиеЛица" in extdim_type:
                                            amount = mov.get("Сумма", 0)
                                            if amount:
                                                salary_entries.append({
                                                    "date": period_str,
                                                    "employee_key": employee_key,
                                                    "amount": float(amount)
                                                })
                                
                                logger.info(f"Extracted {len(salary_entries)} salary entries from RecordsWithExtDimensions")
                            except Exception as e:
                                logger.warning(f"Failed to get movements from RecordsWithExtDimensions: {e}")
                        except Exception as e:
                            logger.warning(f"Failed to fetch from accounting register: {e}")
                    
                    if not salary_entries:
                        return [TextContent(
                            type="text",
                            text=json.dumps({
                                "period": {"from": from_date, "to": to_date},
                                "total_records": 0,
                                "salary_by_employee_month": [],
                                "message": "No salary data found. Please check if accounting entries are configured correctly."
                            }, indent=2, ensure_ascii=False)
                        )]
                    
                    # 3. Агрегировать по месяцам и сотрудникам
                    salary_by_month_employee = defaultdict(lambda: defaultdict(float))
                    
                    for entry in salary_entries:
                        date_str = entry.get("date", "")
                        if not date_str:
                            continue
                        
                        try:
                            if "T" in date_str:
                                entry_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            else:
                                entry_date = datetime.fromisoformat(f"{date_str}T00:00:00")
                            
                            month_key = entry_date.strftime("%Y-%m")
                            emp_key = entry.get("employee_key", "")
                            amount = entry.get("amount", 0)
                            
                            salary_by_month_employee[month_key][emp_key] += amount
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Failed to process entry date/amount: {e}")
                            continue
                    
                    # Форматировать результат (Вариант 2)
                    results = []
                    for month in sorted(salary_by_month_employee.keys()):
                        for emp_key, salary in salary_by_month_employee[month].items():
                            emp_name = employees.get(emp_key, "Unknown")
                            results.append({
                                "month": month,
                                "employee_name": emp_name,
                                "salary": round(salary, 2)
                            })
                    
                    # Сортировка по месяцу, потом по сотруднику
                    results.sort(key=lambda x: (x["month"], x["employee_name"]))
                    
                    return [TextContent(
                        type="text",
                        text=json.dumps({
                            "period": {"from": from_date, "to": to_date},
                            "total_records": len(salary_entries),
                            "salary_by_employee_month": results
                        }, indent=2, ensure_ascii=False)
                    )]
                
                else:
                    raise ValueError(f"Unknown tool: {name}")
                    
            except httpx.HTTPStatusError as e:
                error_msg = f"HTTP error {e.response.status_code}: {e.response.text[:500]}"
                logger.error(f"OData request failed: {error_msg}")
                raise ValueError(error_msg)
            except httpx.RequestError as e:
                error_msg = f"Request error: {str(e)}"
                logger.error(f"OData request failed: {error_msg}")
                raise ValueError(error_msg)
            except Exception as e:
                logger.error(f"Tool execution failed: {e}", exc_info=True)
                raise
    
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
    
    parser = argparse.ArgumentParser(description="1C:Бухгалтерия OData MCP Server")
    parser.add_argument(
        "--config-path",
        type=str,
        default="config/onec_config.json",
        help="Path to 1C configuration file"
    )
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    server = OneCMCPServer(Path(args.config_path))
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())

