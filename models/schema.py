"""Pydantic models mirroring the Gemini extraction JSON schema.

Every string field defaults to the [MISSING] sentinel rather than None so
that downstream CSV output always has an unambiguous value.
"""

from pydantic import BaseModel

from config import MISSING


class Address(BaseModel):
    name: str = MISSING
    name_candidates: list[str] = []
    customer_number: str = MISSING
    label: str = MISSING
    address: str = MISSING
    city: str = MISSING
    country: str = MISSING
    postal_code: str = MISSING


class LineItem(BaseModel):
    material_description: str = MISSING
    material_code: str = MISSING
    quantity: str = MISSING
    unit_price: str = MISSING
    total: str = MISSING


class PurchaseOrder(BaseModel):
    po_number: str = MISSING
    issue_date: str = MISSING
    sold_to: Address = Address()
    ship_to: Address = Address()
    manufacturer_name: str = MISSING
    manufacturer_candidates: list[str] = []
    shipping_details: str = MISSING
    line_items: list[LineItem] = []
    source_file: str = ""
    page_index: int = 0
    parse_error: bool = False
    parse_error_detail: str = ""
