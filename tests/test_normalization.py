from config import MISSING
from pipeline.normalization import failed_extraction, normalize_extraction, normalize_value


def test_normalize_value_variants():
    assert normalize_value(None) == MISSING
    assert normalize_value("") == MISSING
    assert normalize_value("   ") == MISSING
    assert normalize_value("missing") == MISSING
    assert normalize_value("MISSING") == MISSING
    assert normalize_value("[missing]") == MISSING
    assert normalize_value("[MISSING]") == MISSING
    assert normalize_value("  ACME Ltd  ") == "ACME Ltd"
    assert normalize_value(42) == "42"


def test_normalize_extraction_full():
    raw = {
        "po_number": " PO-123 ",
        "issue_date": "2024/01/15",
        "sold_to": {"company_name": "ACME", "address": "1 Main St", "city": "Pune",
                    "country": "IN", "postal_code": "411001",
                    "customer_number": " 742943 ", "label_text": "発注元",
                    "name_candidates": ["ACME", "ACME Holdings", "", None]},
        "ship_to": {"company_name": None},
        "manufacturer_name": "Natec",
        "manufacturer_candidates": ["Natec", "Natec GmbH"],
        "shipping_details": None,
        "line_items": [
            {"material_description": "Steel Pipe", "material_code": "M1",
             "quantity": "10", "unit_price": "5.00", "total": "50.00"},
            "garbage entry",
        ],
    }
    po = normalize_extraction(raw, "test.pdf", 2)
    assert po.po_number == "PO-123"
    assert po.issue_date == "2024/01/15"
    assert po.sold_to.name == "ACME"
    assert po.sold_to.customer_number == "742943"
    assert po.sold_to.label == "発注元"
    # Candidates drop empties and duplicates of the primary value.
    assert po.sold_to.name_candidates == ["ACME Holdings"]
    assert po.manufacturer_candidates == ["Natec GmbH"]
    assert po.ship_to.name == MISSING
    assert po.ship_to.city == MISSING
    assert po.shipping_details == MISSING
    assert po.source_file == "test.pdf"
    assert po.page_index == 2
    assert not po.parse_error
    assert len(po.line_items) == 2
    assert po.line_items[0].material_description == "Steel Pipe"
    # Malformed entry degrades to all-[MISSING] instead of failing the PO.
    assert po.line_items[1].material_description == MISSING


def test_normalize_party_accepts_legacy_name_key():
    po = normalize_extraction({"sold_to": {"name": "Legacy Co"}}, "old.pdf", 0)
    assert po.sold_to.name == "Legacy Co"


def test_null_variants_become_missing():
    from pipeline.normalization import normalize_value
    assert normalize_value("null") == MISSING
    assert normalize_value("None") == MISSING
    assert normalize_value("N/A") == MISSING


def test_normalize_extraction_missing_keys():
    po = normalize_extraction({}, "empty.png", 0)
    assert po.po_number == MISSING
    assert po.sold_to.name == MISSING
    assert po.line_items == []


def test_failed_extraction():
    po = failed_extraction("bad.pdf", 1, "parse_error: not JSON")
    assert po.parse_error
    assert po.parse_error_detail == "parse_error: not JSON"
    assert po.po_number == MISSING
