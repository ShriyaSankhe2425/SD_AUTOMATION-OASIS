"""Logging setup and the human-readable --verbose audit trail.

Standard logs go to stderr (stdout stays clean for user-facing CLI
messages). In verbose mode a .log file is written alongside the CSV with a
per-page trace of every extraction and matching decision.
"""

import logging
import sys
from pathlib import Path

from config import MISSING, NO_MATCH
from models.schema import PurchaseOrder

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)


def format_page_record(po: PurchaseOrder, matches: dict) -> str:
    """One audit block per page: extracted values plus every match decision."""
    lines = [f"=== PAGE {po.page_index + 1} ({po.source_file}) ==="]

    if po.parse_error:
        lines.append(f"EXTRACTION FAILED: {po.parse_error_detail}")
        return "\n".join(lines)

    lines.append(f"Extracted PO Number: {po.po_number}")
    lines.append(f"Extracted Issue Date: {po.issue_date}")

    for label, party, slots in (
        ("Sold To", po.sold_to, matches["sold_to"]),
        ("Ship To", po.ship_to, matches["ship_to"]),
    ):
        lines.append(f"Extracted {label}: {party.name}")
        if party.label != MISSING:
            lines.append(f"  (document label: {party.label})")
        if party.customer_number != MISSING:
            lines.append(f"  (customer number on document: {party.customer_number})")
        if party.name_candidates:
            lines.append(f"  (alternate readings: {' | '.join(party.name_candidates)})")
        for slot_num, slot in enumerate(slots, start=1):
            if slot["customer_code"] == NO_MATCH:
                lines.append(f"  -> Match {slot_num}: {NO_MATCH}")
            else:
                lines.append(
                    f"  -> Match {slot_num}: {slot['customer_name1']} "
                    f"(code: {slot['customer_code']}, score: {slot['match_score']})"
                )

    lines.append(f"Extracted Manufacturer: {po.manufacturer_name}")
    if po.manufacturer_candidates:
        lines.append(f"  (alternate readings: {' | '.join(po.manufacturer_candidates)})")
    sales_org = matches["sales_org"]
    if sales_org["sales_org_code"] == NO_MATCH:
        lines.append(f"  -> Sales Org: {NO_MATCH}")
    else:
        lines.append(
            f"  -> Sales Org: {sales_org['sales_org_name']} "
            f"(code: {sales_org['sales_org_code']}, score: {sales_org['match_score']})"
        )
        sales_area = matches["sales_area"]
        lines.append(f"  -> Distribution Channels: {sales_area['distribution_channels']}")
        lines.append(f"  -> Divisions: {sales_area['divisions']}")

    for index, item in enumerate(po.line_items):
        lines.append(f'Extracted Line Item {index + 1}: "{item.material_description}"')
        for slot_num, slot in enumerate(matches["line_items"][index], start=1):
            if slot["material_code"] == NO_MATCH:
                lines.append(f"  -> Material Match {slot_num}: {NO_MATCH}")
            else:
                lines.append(
                    f"  -> Material Match {slot_num}: {slot['material_description']} "
                    f"(code: {slot['material_code']}, score: {slot['match_score']})"
                )
    return "\n".join(lines)


def write_audit_log(records: list[str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write("\n\n".join(records) + "\n")
    logger.info("Audit log written to %s", log_path)
