import pandas as pd
import pytest

from config import MISSING, NO_MATCH
from models.schema import LineItem, PurchaseOrder
from pipeline.matching import (
    lookup_sales_area,
    match_customers,
    match_materials,
    match_purchase_order,
    match_sales_org,
    strip_business_suffixes,
)


@pytest.fixture
def customer_df():
    return pd.DataFrame({
        "Customer": ["C001", "C047", "C102"],
        "Country": ["IN", "IN", "US"],
        "Name 1": ["ACME TRADING LTD", "ACME EXPORTS PVT", "ZENITH GLOBAL CORP"],
        "Name 2": ["", "ACME EXP", "ZENITH"],
        "City": ["PUNE", "MUMBAI", "AUSTIN"],
        "Postal Code": ["411001", "400001", "73301"],
    })


@pytest.fixture
def material_df():
    return pd.DataFrame({
        "Material": ["MAT-4521", "MAT-9000", "MAT-1111"],
        "Language": ["EN", "EN", "C"],
        "Material Description": ["Steel Pipe SS 50mm", "Copper Wire 2mm", "板玻璃托盘"],
    })


@pytest.fixture
def sales_org_df():
    return pd.DataFrame({
        "Sales Organization": ["1010", "1020"],
        "Name": ["Weber&Broutin France", "Natec"],
    })


@pytest.fixture
def sales_area_df():
    return pd.DataFrame({
        "Sales Organization": ["1010", "1010", "1020"],
        "Distribution Channel": ["10", "20", "10"],
        "Division": ["10", "11", "00"],
    })


def test_strip_business_suffixes():
    assert strip_business_suffixes("ACME TRADING PVT LTD") == "ACME TRADING"
    assert strip_business_suffixes("Weber GmbH") == "Weber"
    assert strip_business_suffixes("Solo S.r.l.") == "Solo"
    # Stripping everything falls back to the original.
    assert strip_business_suffixes("Ltd") == "Ltd"
    # A too-short remainder would make partial_ratio match everything, so
    # the original is kept.
    assert strip_business_suffixes("MAG CO LTD") == "MAG CO LTD"


def test_customer_match_top_hit(customer_df):
    slots = match_customers("ACME TRADING PVT LTD", customer_df, threshold=60)
    assert len(slots) == 3
    assert slots[0]["customer_code"] == "C001"
    assert slots[0]["match_score"] >= 90


def test_customer_match_uses_name2(customer_df):
    slots = match_customers("ZENITH", customer_df, threshold=60)
    assert slots[0]["customer_code"] == "C102"


def test_customer_match_below_threshold(customer_df):
    slots = match_customers("Completely Unrelated Query 12345", customer_df, threshold=95)
    assert all(slot["customer_code"] == NO_MATCH for slot in slots)
    assert all(slot["match_score"] == 0 for slot in slots)


def test_customer_number_exact_match_takes_slot_one(customer_df):
    # A wrong/vague name plus a valid customer number: the number wins.
    slots = match_customers("Some Address 123, Tokyo", customer_df, threshold=60,
                            customer_number="C047")
    assert slots[0]["customer_code"] == "C047"
    assert slots[0]["match_score"] == 100


def test_customer_number_exact_plus_fuzzy_fill(customer_df):
    slots = match_customers("ACME TRADING PVT LTD", customer_df, threshold=60,
                            customer_number="C102")
    assert slots[0]["customer_code"] == "C102"  # exact number first
    assert slots[0]["match_score"] == 100
    assert slots[1]["customer_code"] == "C001"  # best fuzzy name hit next


def test_candidate_name_rescues_poor_primary(customer_df):
    # Primary extraction grabbed an address; a candidate holds the real name.
    slots = match_customers("2-1-1 Marunouchi Chiyoda-ku", customer_df, threshold=80,
                            candidates=["ZENITH GLOBAL CORP"])
    assert slots[0]["customer_code"] == "C102"


def test_customer_match_missing_input(customer_df):
    assert all(s["customer_code"] == NO_MATCH for s in match_customers(MISSING, customer_df, 60))
    assert all(s["customer_code"] == NO_MATCH for s in match_customers("x", pd.DataFrame(), 60))


def test_material_exact_code_wins(material_df):
    slots = match_materials("anything", "MAT-9000", material_df, threshold=60)
    assert slots[0]["material_code"] == "MAT-9000"
    assert slots[0]["match_score"] == 100


def test_material_fuzzy_description(material_df):
    slots = match_materials("Stainless Steel Pipe 50mm", MISSING, material_df, threshold=60)
    assert slots[0]["material_code"] == "MAT-4521"
    assert slots[0]["match_score"] >= 60


def test_material_unicode_description(material_df):
    slots = match_materials("板玻璃托盘", MISSING, material_df, threshold=60)
    assert slots[0]["material_code"] == "MAT-1111"
    assert slots[0]["match_score"] == 100


def test_material_cross_language_no_match(material_df):
    # Chinese query against English-only rows: character-level match fails.
    slots = match_materials("不锈钢管五十毫米", MISSING, material_df.iloc[:2], threshold=60)
    assert all(slot["material_code"] == NO_MATCH for slot in slots)


def test_sales_org_match_and_area_lookup(sales_org_df, sales_area_df):
    org = match_sales_org("Weber & Broutin", sales_org_df, threshold=60)
    assert org["sales_org_code"] == "1010"
    area = lookup_sales_area(org["sales_org_code"], sales_area_df)
    assert area["distribution_channels"] == "10|20"
    assert area["divisions"] == "10|11"


def test_sales_org_candidate_fallback(sales_org_df):
    org = match_sales_org("株式会社ナテック", sales_org_df, threshold=80,
                          candidates=["Natec"])
    assert org["sales_org_code"] == "1020"


def test_sales_org_below_threshold(sales_org_df, sales_area_df):
    org = match_sales_org("Totally Unknown Manufacturer", sales_org_df, threshold=95)
    assert org["sales_org_code"] == NO_MATCH
    area = lookup_sales_area(org["sales_org_code"], sales_area_df)
    assert area["distribution_channels"] == NO_MATCH


def test_missing_column_degrades_gracefully(sales_area_df):
    broken = pd.DataFrame({"Wrong Column": ["x"]})
    slots = match_customers("ACME", broken, threshold=60)
    assert all(slot["customer_code"] == NO_MATCH for slot in slots)


def test_match_purchase_order_bundle(customer_df, material_df, sales_org_df, sales_area_df):
    po = PurchaseOrder(
        manufacturer_name="Natec",
        line_items=[LineItem(material_description="Copper Wire 2mm")],
    )
    po.sold_to.name = "ACME TRADING LTD"
    reference = {
        "customerList": customer_df,
        "materialList": material_df,
        "salesOrg": sales_org_df,
        "salesArea": sales_area_df,
    }
    matches = match_purchase_order(po, reference, threshold=60)
    assert matches["sold_to"][0]["customer_code"] == "C001"
    assert matches["ship_to"][0]["customer_code"] == NO_MATCH  # ship_to name is [MISSING]
    assert matches["sales_org"]["sales_org_code"] == "1020"
    assert matches["sales_area"]["distribution_channels"] == "10"
    assert matches["line_items"][0][0]["material_code"] == "MAT-9000"
