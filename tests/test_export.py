import csv

from config import MISSING, NO_MATCH
from models.schema import LineItem, PurchaseOrder
from pipeline.export import CSV_COLUMNS, po_to_rows, write_csv
from pipeline.matching import no_match_customer_slot, no_match_material_slot


def _empty_matches(num_items: int) -> dict:
    return {
        "sold_to": [no_match_customer_slot() for _ in range(3)],
        "ship_to": [no_match_customer_slot() for _ in range(3)],
        "sales_org": {"sales_org_code": NO_MATCH, "sales_org_name": NO_MATCH, "match_score": 0},
        "sales_area": {"distribution_channels": NO_MATCH, "divisions": NO_MATCH},
        "line_items": [[no_match_material_slot() for _ in range(3)] for _ in range(num_items)],
    }


def _sample_po(num_items: int) -> PurchaseOrder:
    po = PurchaseOrder(
        po_number="PO-1",
        issue_date="15.01.2024",
        source_file="doc.pdf",
        page_index=0,
        line_items=[
            LineItem(material_description=f"Item {i}", quantity=str(i)) for i in range(num_items)
        ],
    )
    po.sold_to.name = "ACME 株式会社"
    return po


def test_one_row_per_line_item():
    po = _sample_po(3)
    rows = po_to_rows(po, _empty_matches(3))
    assert len(rows) == 3
    assert [row["line_item_index"] for row in rows] == [0, 1, 2]
    # PO-level fields repeat on every row.
    assert all(row["po_number"] == "PO-1" for row in rows)
    assert rows[1]["line_item_material_description"] == "Item 1"
    assert rows[0]["line_item_material_code"] == MISSING


def test_po_without_line_items_emits_one_row():
    po = _sample_po(0)
    rows = po_to_rows(po, _empty_matches(0))
    assert len(rows) == 1
    assert rows[0]["line_item_index"] == ""
    assert rows[0]["line_item_quantity"] == MISSING


def test_csv_write_columns_and_bom(tmp_path):
    po = _sample_po(2)
    rows = po_to_rows(po, _empty_matches(2))
    out = tmp_path / "doc_output.csv"
    write_csv(rows, out)

    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM for Excel

    with open(out, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == CSV_COLUMNS
        read_rows = list(reader)
    assert len(read_rows) == 2
    assert read_rows[0]["sold_to_name"] == "ACME 株式会社"
    assert read_rows[0]["ship_to_name"] == MISSING
    assert read_rows[0]["sold_to_match_1_code"] == NO_MATCH


def test_every_row_key_is_a_known_column():
    rows = po_to_rows(_sample_po(1), _empty_matches(1))
    assert set(rows[0]) == set(CSV_COLUMNS)
