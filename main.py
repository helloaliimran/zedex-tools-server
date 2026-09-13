from mcp_types import ToolAnnotations
import requests
import json
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

# region SYSTEM_MESSAGE
SYSTEM_MESSAGE = """
You are a Billing Agent for Zedex.

## Core Task
Understand product requirements → Validate against lookups → Create accurate billing list → Create bills when user confirms.

## Critical Rules

1. **Shared vs Product-Specific Values**
   - Shared values (provided before list) apply to ALL products
   - Product-specific values OVERRIDE shared values
   - Never auto-apply Product 1's values to Product 2

2. **When to Ask vs Auto-Correct**
   - Auto-correct obvious spelling mistakes
   - Only ask clarification for: missing required fields, ambiguous matches, or genuinely unclear requests

3. **Workflow**
   - Display product table FIRST (user confirmation)
   - Create bill ONLY when user says "create" or similar
   - Resolve customer name → customerId (never guess)
   - Show invoice number on success

4. **Special Cases**
   - "18/5" = Size/Quantity format
   - Use productId from lookup for bill creation
   - Don't include % in discount values

See the zedex://lookups resource for valid product/category/color values before validating.
"""
# endregion

mcp = MCPServer("Zedex tool calling", instructions=SYSTEM_MESSAGE)

# region TOOLS


@mcp.tool(annotations=ToolAnnotations(
    readonlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
))
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


@mcp.tool(annotations=ToolAnnotations(
    readonlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
))
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


@mcp.tool(annotations=ToolAnnotations(
    readonlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
))
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


@mcp.tool(annotations=ToolAnnotations(
    readonlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
))
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


@mcp.tool(annotations=ToolAnnotations(
    destructiveHint=False,
    idempotentHint=False,
    readonlyHint=False,
))
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

# endregion

# region prompts


@mcp.prompt()
def start_new_bill(customer_search: str, product_request: str) -> str:
    """Kick off a new bill: find the customer, then validate and price the requested products."""
    return (
        f"Find the customer matching '{customer_search}' and confirm it's the right one.\n\n"
        f"Then interpret this product request and validate each item against zedex://lookups resource. "
        f"(color, gauge, category, company must all match valid values):\n"
        f"\"{product_request}\"\n\n"
        f"Display the resulting product table with quantities, sizes, and discounts for my "
        f"confirmation. Do not create the bill until I explicitly confirm it."
    )


@mcp.prompt()
def audit_bill(bill_id: str) -> str:
    """Review an existing bill for stale pricing or invalid values against current lookups."""
    return (
        f"Fetch bill {bill_id} and also call get_lookups. "
        f"Check every line item's product, color, gauge, and discount against the current "
        f"lookup values, and flag any item that no longer matches or looks outdated. "
        f"Summarize the discrepancies you find. Do not modify the bill — this is read-only."
    )


# endregion


@mcp.resource("zedex://lookups")
def zedex_lookups() -> str:
    """Current valid product categories, colors, gauges, and companies for Zedex."""
    try:
        result = _get_lookups()
        if isinstance(result, dict) and result.get("error"):
            raise ValueError(
                f"Zedex API error status: {result['status']}: {result['detail']}")
        return json.dumps(result)
    except Exception as e:
        raise ToolError(
            f"{e} : Zedex service is currently unreachable. Please try again shortly.")


if __name__ == "__main__":
    mcp.run()
