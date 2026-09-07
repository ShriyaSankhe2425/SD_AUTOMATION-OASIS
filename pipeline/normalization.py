"""Clean the raw extraction JSON and coerce it into the PurchaseOrder model.

- Missing keys, nulls, and empty values become the [MISSING] sentinel.
- Any casing/bracket variant of "missing" is normalized to [MISSING].
- Whitespace is stripped; original date/quantity/price formatting is
  deliberately preserved (no reformatting, no currency conversion).
- Candidate lists (alternate party/manufacturer readings) are cleaned and
  de-duplicated against the primary value.
- A malformed line item degrades to all-[MISSING] fields rather than
  failing the whole PO.
"""

import logging

from config import MISSING
from models.schema import Address, LineItem, PurchaseOrder

logger = logging.getLogger(__name__)

_LINE_ITEM_FIELDS = ("material_description", "material_code", "quantity", "unit_price", "total")


def normalize_extraction(raw: dict, source_file: str, page_index: int) -> PurchaseOrder:
    """Build a validated PurchaseOrder from a raw Gemini response dict."""
    manufacturer = normalize_value(raw.get("manufacturer_name"))
    return PurchaseOrder(
        po_number=normalize_value(raw.get("po_number")),
        issue_date=normalize_value(raw.get("issue_date")),
        sold_to=_normalize_party(raw.get("sold_to")),
        ship_to=_normalize_party(raw.get("ship_to")),
        manufacturer_name=manufacturer,
        manufacturer_candidates=_normalize_candidates(
            raw.get("manufacturer_candidates"), primary=manufacturer
        ),
        shipping_details=normalize_value(raw.get("shipping_details")),
        line_items=_normalize_line_items(raw.get("line_items")),
        source_file=source_file,
        page_index=page_index,
    )


def failed_extraction(source_file: str, page_index: int, detail: str) -> PurchaseOrder:
    """A PurchaseOrder representing a page whose extraction failed."""
    return PurchaseOrder(
        source_file=source_file,
        page_index=page_index,
        parse_error=True,
        parse_error_detail=detail,
    )


def normalize_value(value) -> str:
    """Coerce a single extracted value to a clean string or [MISSING]."""
    if value is None:
        return MISSING
    text = str(value).strip()
    if not text:
        return MISSING
    if text.strip("[]").strip().lower() in ("missing", "null", "none", "n/a"):
        return MISSING
    return text


def _normalize_candidates(raw, primary: str) -> list[str]:
    """Clean a candidates list: drop empties and duplicates of the primary."""
    if not isinstance(raw, list):
        return []
    candidates = []
    for entry in raw:
        value = normalize_value(entry)
        if value != MISSING and value != primary and value not in candidates:
            candidates.append(value)
    return candidates


def _normalize_party(raw) -> Address:
    if not isinstance(raw, dict):
        return Address()
    # "company_name" is the structured-output field; "name" kept for
    # compatibility with older recorded responses.
    name = normalize_value(raw.get("company_name") if raw.get("company_name") is not None else raw.get("name"))
    return Address(
        name=name,
        name_candidates=_normalize_candidates(raw.get("name_candidates"), primary=name),
        customer_number=normalize_value(raw.get("customer_number")),
        label=normalize_value(raw.get("label_text")),
        address=normalize_value(raw.get("address")),
        city=normalize_value(raw.get("city")),
        country=normalize_value(raw.get("country")),
        postal_code=normalize_value(raw.get("postal_code")),
    )


def _normalize_line_items(raw) -> list[LineItem]:
    if not isinstance(raw, list):
        return []
    items = []
    for entry in raw:
        if isinstance(entry, dict):
            items.append(LineItem(**{f: normalize_value(entry.get(f)) for f in _LINE_ITEM_FIELDS}))
        else:
            logger.warning("Malformed line item entry (%r); emitting [MISSING] fields", entry)
            items.append(LineItem())
    return items
