"""
1C:Бухгалтерия OData MCP tool wrappers for LangChain.
Provides validated interfaces to 1C OData operations.
"""

import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from src.utils.mcp_loader import get_mcp_manager
from src.utils.exceptions import ToolExecutionError, ValidationError
from src.utils.retry import retry_on_mcp_error


class GetSalesListInput(BaseModel):
    """Input schema for onec_get_sales_list tool."""
    
    from_date: str = Field(description="Start date (ISO 8601 format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")
    to_date: str = Field(description="End date (ISO 8601 format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)")
    organization_guid: Optional[str] = Field(default=None, description="Optional organization GUID for filtering")
    max_results: int = Field(default=100, description="Maximum number of results (default: 100, max: 1000)")


class GetSalesListTool(BaseTool):
    """Tool for getting list of sales documents from 1C."""
    
    name: str = "onec_get_sales_list"
    description: str = """
    Get list of sales documents (Реализация товаров и услуг) from 1C:Бухгалтерия for a specified period.
    
    Input:
    - from_date: Start date (ISO 8601 format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    - to_date: End date (ISO 8601 format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
    - organization_guid: Optional organization GUID for filtering
    - max_results: Maximum number of results (default: 100, max: 1000)
    
    Returns list of sales documents with date, number, counterparty, amount, and posted status.
    """
    args_schema: type = GetSalesListInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        from_date: str,
        to_date: str,
        organization_guid: Optional[str] = None,
        max_results: int = 100
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            # Validate dates
            try:
                if "T" in from_date:
                    datetime.fromisoformat(from_date.replace("Z", "+00:00"))
                else:
                    datetime.fromisoformat(f"{from_date}T00:00:00")
                
                if "T" in to_date:
                    datetime.fromisoformat(to_date.replace("Z", "+00:00"))
                else:
                    datetime.fromisoformat(f"{to_date}T23:59:59")
            except ValueError as e:
                raise ValidationError(f"Invalid date format: {e}")
            
            # Validate max_results
            if max_results < 1 or max_results > 1000:
                raise ValidationError("max_results must be between 1 and 1000")
            
            # Prepare arguments for MCP tool
            args = {
                "from": from_date,
                "to": to_date,
                "max_results": max_results
            }
            if organization_guid:
                args["organization_guid"] = organization_guid
            
            # Call MCP tool
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("onec_sales_list", args, server_name="onec")
            
            # Parse result
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    pass
            
            # Format result for display
            if isinstance(result, dict):
                count = result.get("count", 0)
                sales = result.get("sales", [])
                
                if count == 0:
                    return f"No sales documents found for the period {from_date} to {to_date}."
                
                summary = f"Found {count} sales document(s) for period {from_date} to {to_date}:\n\n"
                for i, sale in enumerate(sales[:20], 1):  # Show first 20
                    summary += f"{i}. {sale.get('date', 'N/A')} - {sale.get('number', 'N/A')} - "
                    summary += f"{sale.get('counterparty_name', 'Unknown')} - "
                    summary += f"Amount: {sale.get('amount', 0):.2f} - "
                    summary += f"Posted: {'Yes' if sale.get('posted', False) else 'No'}\n"
                
                if count > 20:
                    summary += f"\n... and {count - 20} more documents."
                
                return summary
            
            return str(result)
            
        except ValidationError as e:
            raise ToolExecutionError(
                f"Validation failed: {e.message}",
                tool_name=self.name,
                tool_args={"from_date": from_date, "to_date": to_date}
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get sales list: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


class GetRevenueByCounterpartyMonthInput(BaseModel):
    """Input schema for onec_get_revenue_by_counterparty_month tool."""
    
    from_date: str = Field(description="Start date (ISO 8601 format: YYYY-MM-DD)")
    to_date: str = Field(description="End date (ISO 8601 format: YYYY-MM-DD)")
    organization_guid: Optional[str] = Field(default=None, description="Optional organization GUID for filtering")


class GetRevenueByCounterpartyMonthTool(BaseTool):
    """Tool for getting revenue by counterparty aggregated by month from 1C."""
    
    name: str = "onec_get_revenue_by_counterparty_month"
    description: str = """
    Get revenue by counterparty aggregated by month from 1C:Бухгалтерия sales documents.
    
    This tool aggregates sales data (Реализация товаров и услуг) by month and counterparty,
    showing total revenue for each counterparty in each month.
    
    Input:
    - from_date: Start date (ISO 8601 format: YYYY-MM-DD)
    - to_date: End date (ISO 8601 format: YYYY-MM-DD)
    - organization_guid: Optional organization GUID for filtering
    
    Returns aggregated revenue data grouped by month and counterparty.
    """
    args_schema: type = GetRevenueByCounterpartyMonthInput
    
    @retry_on_mcp_error()
    async def _arun(
        self,
        from_date: str,
        to_date: str,
        organization_guid: Optional[str] = None
    ) -> str:
        """Execute the tool asynchronously."""
        try:
            # Validate dates
            try:
                datetime.fromisoformat(f"{from_date}T00:00:00")
                datetime.fromisoformat(f"{to_date}T23:59:59")
            except ValueError as e:
                raise ValidationError(f"Invalid date format: {e}. Use YYYY-MM-DD format.")
            
            # Prepare arguments for MCP tool
            args = {
                "from": from_date,
                "to": to_date
            }
            if organization_guid:
                args["organization_guid"] = organization_guid
            
            # Call MCP tool
            mcp_manager = get_mcp_manager()
            result = await mcp_manager.call_tool("onec_revenue_by_counterparty_month", args, server_name="onec")
            
            # Parse result
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except:
                    pass
            
            # Format result for display
            if isinstance(result, dict):
                revenue_data = result.get("revenue_by_counterparty_month", [])
                total_records = result.get("total_records", 0)
                
                if not revenue_data:
                    return f"No revenue data found for the period {from_date} to {to_date}."
                
                # Group by month for better display
                by_month = {}
                for item in revenue_data:
                    month = item.get("month", "Unknown")
                    if month not in by_month:
                        by_month[month] = []
                    by_month[month].append(item)
                
                summary = f"Revenue by counterparty by month (from {total_records} sales documents):\n\n"
                
                for month in sorted(by_month.keys()):
                    summary += f"## {month}\n"
                    month_total = 0
                    for item in sorted(by_month[month], key=lambda x: x.get("revenue", 0), reverse=True):
                        cp_name = item.get("counterparty_name", "Unknown")
                        revenue = item.get("revenue", 0)
                        month_total += revenue
                        summary += f"  - {cp_name}: {revenue:,.2f}\n"
                    summary += f"  Month total: {month_total:,.2f}\n\n"
                
                # Overall summary
                grand_total = sum(item.get("revenue", 0) for item in revenue_data)
                summary += f"Grand total: {grand_total:,.2f}"
                
                return summary
            
            return str(result)
            
        except ValidationError as e:
            raise ToolExecutionError(
                f"Validation failed: {e.message}",
                tool_name=self.name,
                tool_args={"from_date": from_date, "to_date": to_date}
            ) from e
        except Exception as e:
            raise ToolExecutionError(
                f"Failed to get revenue data: {e}",
                tool_name=self.name
            ) from e
    
    def _run(self, *args, **kwargs) -> str:
        raise NotImplementedError("Use async execution")


def get_onec_tools() -> List[BaseTool]:
    """
    Get all 1C OData tools.
    
    Returns:
        List of 1C tool instances
    """
    return [
        GetSalesListTool(),
        GetRevenueByCounterpartyMonthTool(),
    ]



