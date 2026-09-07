"""Flatten matched purchase orders into CSV rows and write the output file.

One row per line item (PO-level fields repeat on every row). A PO with no
line items — including parse failures — still emits one row so nothing is
silently dropped. Written as UTF-8 with BOM so Excel renders multilingual
content correctly.
"""

import csv
import logging
from pathlib import Path

from config import MISSING
from models.schema import PurchaseOrder
from pipeline.matching import (
    no_match_customer_slot,
    no_match_material_slot,
    TOP_N,
)

logger = logging.getLogger(__name__)


def _customer_columns(prefix: str) -> list[str]:
    columns = []
    for slot in range(1, TOP_N + 1):
        columns += [
            f"{prefix}_match_{slot}_code",
            f"{prefix}_match_{slot}_name",
            f"{prefix}_match_{slot}_score",
        ]
    return columns


def _material_columns() -> list[str]:
    columns = []
    for slot in range(1, TOP_N + 1):
        columns += [
            f"material_match_{slot}_code",
            f"material_match_{slot}_description",
            f"material_match_{slot}_score",
        ]
    return columns


CSV_COLUMNS = (
    [
        "source_file",
        "page_index",
        "po_number",
        "issue_date",
        "sold_to_name",
        "sold_to_name_candidates",
        "sold_to_customer_number",
        "sold_to_address",
        "sold_to_city",
        "sold_to_country",
        "sold_to_postal_code",
        "ship_to_name",
        "ship_to_name_candidates",
        "ship_to_customer_number",
        "ship_to_address",
        "ship_to_city",
        "ship_to_country",
        "ship_to_postal_code",
        "manufacturer_name",
        "manufacturer_candidates",
        "shipping_details",
    ]
    + _customer_columns("sold_to")
    + _customer_columns("ship_to")
    + [
        "sales_org_code",
        "sales_org_name",
        "sales_org_score",
        "distribution_channels",
        "divisions",
        "parse_error",
        "parse_error_detail",
        "line_item_index",
        "line_item_material_description",
        "line_item_material_code",
        "line_item_quantity",
        "line_item_unit_price",
        "line_item_total",
    ]
    + _material_columns()
)


def po_to_rows(po: PurchaseOrder, matches: dict) -> list[dict]:
    """Flatten one matched PurchaseOrder into CSV row dicts."""
    base = {
        "source_file": po.source_file,
        "page_index": po.page_index,
        "po_number": po.po_number,
        "issue_date": po.issue_date,
        "sold_to_name": po.sold_to.name,
        "sold_to_name_candidates": "|".join(po.sold_to.name_candidates),
        "sold_to_customer_number": po.sold_to.customer_number,
        "sold_to_address": po.sold_to.address,
        "sold_to_city": po.sold_to.city,
        "sold_to_country": po.sold_to.country,
        "sold_to_postal_code": po.sold_to.postal_code,
        "ship_to_name": po.ship_to.name,
        "ship_to_name_candidates": "|".join(po.ship_to.name_candidates),
        "ship_to_customer_number": po.ship_to.customer_number,
        "ship_to_address": po.ship_to.address,
        "ship_to_city": po.ship_to.city,
        "ship_to_country": po.ship_to.country,
        "ship_to_postal_code": po.ship_to.postal_code,
        "manufacturer_name": po.manufacturer_name,
        "manufacturer_candidates": "|".join(po.manufacturer_candidates),
        "shipping_details": po.shipping_details,
        "sales_org_code": matches["sales_org"]["sales_org_code"],
        "sales_org_name": matches["sales_org"]["sales_org_name"],
        "sales_org_score": matches["sales_org"]["match_score"],
        "distribution_channels": matches["sales_area"]["distribution_channels"],
        "divisions": matches["sales_area"]["divisions"],
        "parse_error": po.parse_error,
        "parse_error_detail": po.parse_error_detail,
    }
    for prefix in ("sold_to", "ship_to"):
        slots = matches.get(prefix) or [no_match_customer_slot() for _ in range(TOP_N)]
        for slot_num, slot in enumerate(slots[:TOP_N], start=1):
            base[f"{prefix}_match_{slot_num}_code"] = slot["customer_code"]
            base[f"{prefix}_match_{slot_num}_name"] = slot["customer_name1"]
            base[f"{prefix}_match_{slot_num}_score"] = slot["match_score"]

    if not po.line_items:
        row = dict(base)
        row["line_item_index"] = ""
        for field in ("material_description", "material_code", "quantity", "unit_price", "total"):
            row[f"line_item_{field}"] = MISSING
        _fill_material_slots(row, [no_match_material_slot() for _ in range(TOP_N)])
        return [row]

    rows = []
    material_matches = matches.get("line_items") or []
    for index, item in enumerate(po.line_items):
        row = dict(base)
        row["line_item_index"] = index
        row["line_item_material_description"] = item.material_description
        row["line_item_material_code"] = item.material_code
        row["line_item_quantity"] = item.quantity
        row["line_item_unit_price"] = item.unit_price
        row["line_item_total"] = item.total
        slots = (
            material_matches[index]
            if index < len(material_matches)
            else [no_match_material_slot() for _ in range(TOP_N)]
        )
        _fill_material_slots(row, slots)
        rows.append(row)
    return rows


def _fill_material_slots(row: dict, slots: list[dict]) -> None:
    for slot_num, slot in enumerate(slots[:TOP_N], start=1):
        row[f"material_match_{slot_num}_code"] = slot["material_code"]
        row[f"material_match_{slot_num}_description"] = slot["material_description"]
        row[f"material_match_{slot_num}_score"] = slot["match_score"]


def write_csv(rows: list[dict], output_path: Path) -> None:
    """Write rows as UTF-8-BOM CSV so Excel opens multilingual text cleanly."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Wrote %d row(s) to %s", len(rows), output_path)
