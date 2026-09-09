from pydantic import BaseModel


class ProductQuery(BaseModel):
    """One product search criterion for the Zedex product search endpoint."""
    productName: str
    color: str | None = None
    gauge: str | None = None
    category: str | None = None
    company: str | None = None


class BillItem(BaseModel):
    """One item in a bill for the Zedex create/update bill endpoint."""
    productId: int
    quantity: int
    sizeFt: float
    discountPercent: int
    billItemId: int | None = 0  # Optional, defaults to 0 for new items


class CreateUpdateBill(BaseModel):

    """Data model for creating or updating a bill in the Zedex API."""
    items: list[BillItem]
    customer_id: int
    bill_id: int | None = None
    remarks: str | None = None
