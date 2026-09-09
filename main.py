import requests

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from models import CreateUpdateBill, ProductQuery
from tools.zedex_calling import (
    find_customer as _find_customer,
    get_lookups as _get_lookups,
    search_product as _search_product,
    get_bill as _get_bill,
    create_or_update_bill as _create_or_update_bill,
)

mcp = MCPServer("Zedex tool calling")


@mcp.tool()
def find_customer(search: str | None = None):
    """Find a customer by name or ID.

    Args:
        search (str, optional): The search term to find the customer. Defaults to None.

    Returns:
        dict: The customer information or an error message.
    """
    try:
        result = _find_customer(search)
    except requests.exceptions.RequestException as e:
        raise ToolError(
            "Zedex service is currently unreachable. Please try again shortly.") from e

    if isinstance(result, dict) and result.get("error"):
        raise ToolError(
            f"Zedex API error status: {result['status']}: {result['detail']}")

    return result


@mcp.tool()
def get_lookups():
    """Get lookup data from the Zedex API such as colors, categories, companies, gauges.

    Returns:
        dict: The lookup data or an error message.
    """
    try:
        result = _get_lookups()
    except requests.exceptions.RequestException as e:
        raise ToolError(
            "Zedex service is currently unreachable. Please try again shortly.") from e

    if isinstance(result, dict) and result.get("error"):
        raise ToolError(
            f"Zedex API error status: {result['status']}: {result['detail']}")

    return result


@mcp.tool()
def search_product(products: list[ProductQuery]):
    """Search for products in the Zedex API.

    Args:
        products (list): A list of product dictionaries to search for.

    Returns:
        dict: The search results or an error message.
    """
    try:
        result = _search_product([p.model_dump() for p in products])

    except requests.exceptions.RequestException as e:
        raise ToolError(
            "Zedex service is currently unreachable. Please try again shortly.") from e

    if isinstance(result, dict) and result.get("error"):
        raise ToolError(
            f"Zedex API error status: {result['status']}: {result['detail']}")

    return result


@mcp.tool()
def get_bill(id_or_invoice_number: str):
    """Get a bill by ID or invoice number from the Zedex API.

    Args:
        id_or_invoice_number (str): The ID or invoice number of the bill.

    Returns:
        dict: The bill information or an error message.
    """
    try:
        result = _get_bill(id_or_invoice_number)
    except requests.exceptions.RequestException as e:
        raise ToolError(
            "Zedex service is currently unreachable. Please try again shortly.") from e

    if isinstance(result, dict) and result.get("error"):
        raise ToolError(
            f"Zedex API error status: {result['status']}: {result['detail']}")

    return result


@mcp.tool()
def create_or_update_bill(bill_data: CreateUpdateBill):
    """Create or update a bill in the Zedex API.

    Args:
        items (list): A list of item dictionaries for the bill.
        customerId (str): The ID of the customer for the bill.
        billid (str, optional): The ID of the bill to update. Defaults to None.
        remarks (str, optional): Remarks for the bill. Defaults to None.
    """
    try:
        payload = {
            "billId": bill_data.billId,
            "customerId": bill_data.customerId,
            "remarks": bill_data.remarks or "AI generated bill",
            "items": [item.model_dump() for item in bill_data.items],
        }
        result = _create_or_update_bill(payload)
    except Exception as e:
        raise ToolError(
            f" {e} : Zedex service is currently unreachable. Please try again shortly.") from e

    if isinstance(result, dict) and result.get("error"):
        raise ToolError(
            f"Zedex API error status: {result['status']}: {result['detail']}")

    return result


if __name__ == "__main__":
    mcp.run()
