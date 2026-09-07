"""Fuzzy matching of extracted entities against the Excel reference data.

Composite score = max(token_sort_ratio, partial_ratio, WRatio) so that
reordered words, partial/abbreviated names, and general similarity are all
covered. All matchers share one configurable threshold; results below it
come back as [NO MATCH] slots so the CSV shape never changes.
"""

import logging
import re

import pandas as pd
from rapidfuzz import fuzz

import config
from config import MISSING, NO_MATCH

logger = logging.getLogger(__name__)

_SUFFIX_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(s).replace(r"\.", r"\.?") for s in config.BUSINESS_SUFFIXES) + r")\b\.?",
    re.IGNORECASE,
)

TOP_N = 3


def composite_score(query: str, candidate: str) -> float:
    query = str(query).lower().strip()
    candidate = str(candidate).lower().strip()
    if not query or not candidate:
        return 0.0
    return max(
        fuzz.token_sort_ratio(query, candidate),
        fuzz.partial_ratio(query, candidate),
        fuzz.WRatio(query, candidate),
    )


def strip_business_suffixes(name: str) -> str:
    """Remove common business suffixes (Ltd, Pvt, GmbH, ...) for matching.

    The original string is always preserved for output; this only shapes
    the query. If stripping removes everything, fall back to the original.
    """
    stripped = _SUFFIX_RE.sub(" ", name)
    stripped = re.sub(r"[.,]+", " ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    # Very short remainders (e.g. "MAG CO LTD" -> "MAG") make partial_ratio
    # match everything containing the fragment; keep the original instead.
    if len(stripped) < 4:
        return name.strip()
    return stripped


def _usable(value: str) -> bool:
    return bool(value) and value not in (MISSING, NO_MATCH)


def _col(df: pd.DataFrame, name: str) -> pd.Series | None:
    """Case-insensitive column lookup; warns once per missing column."""
    if df is None or df.empty:
        return None
    for column in df.columns:
        if str(column).strip().lower() == name.lower():
            return df[column]
    logger.warning("Reference column '%s' not found (available: %s)", name, list(df.columns))
    return None


# --- Customer matching -----------------------------------------------------

def no_match_customer_slot() -> dict:
    return {
        "customer_code": NO_MATCH,
        "customer_name1": NO_MATCH,
        "customer_name2": NO_MATCH,
        "customer_country": NO_MATCH,
        "customer_city": NO_MATCH,
        "match_score": 0,
    }


def match_customers(
    name: str,
    customer_df: pd.DataFrame,
    threshold: int,
    customer_number: str = MISSING,
    candidates: tuple[str, ...] | list[str] = (),
) -> list[dict]:
    """Top-3 customer matches for an extracted party.

    Priority order:
    1. An extracted customer/account number that exactly matches the
       ``Customer`` column takes slot 1 with score 100 (no fuzzing needed).
    2. Fuzzy name matching fills the remaining slots. The primary name and
       any candidate readings are each tried as queries; the query whose
       best hit scores highest wins. Rows are scored against both Name 1
       and Name 2 (higher wins).

    Returns exactly TOP_N slots; [NO MATCH] fills anything below threshold.
    """
    slots: list[dict] = []
    if customer_df is None or customer_df.empty:
        return [no_match_customer_slot() for _ in range(TOP_N)]

    def row_slot(row_idx: int, score: int) -> dict:
        def get(column: str) -> str:
            series = _col(customer_df, column)
            return str(series.iloc[row_idx]).strip() if series is not None else NO_MATCH
        return {
            "customer_code": get("Customer"),
            "customer_name1": get("Name 1"),
            "customer_name2": get("Name 2"),
            "customer_country": get("Country"),
            "customer_city": get("City"),
            "match_score": score,
        }

    exact_row: int | None = None
    code_col = _col(customer_df, "Customer") if _usable(customer_number) else None
    if code_col is not None:
        hits = [i for i in range(len(customer_df))
                if str(code_col.iloc[i]).strip() == str(customer_number).strip()]
        if hits:
            exact_row = hits[0]
            slots.append(row_slot(exact_row, 100))
            logger.info("Customer number '%s' matched exactly (code slot 1)", customer_number)

    name1_col = _col(customer_df, "Name 1")
    name2_col = _col(customer_df, "Name 2")
    queries = [q for q in [name, *candidates] if _usable(q)]
    if queries and (name1_col is not None or name2_col is not None):
        best_ranking: list[tuple[float, int]] = []
        for raw_query in queries:
            query = strip_business_suffixes(raw_query)
            scored: list[tuple[float, int]] = []
            for i in range(len(customer_df)):
                score1 = composite_score(query, name1_col.iloc[i]) if name1_col is not None else 0.0
                score2 = composite_score(query, name2_col.iloc[i]) if name2_col is not None else 0.0
                scored.append((max(score1, score2), i))
            scored.sort(key=lambda pair: pair[0], reverse=True)
            if scored and (not best_ranking or scored[0][0] > best_ranking[0][0]):
                best_ranking = scored
                if raw_query != name:
                    logger.info("Candidate name '%s' outscored primary for matching", raw_query)

        for score, row_idx in best_ranking:
            if len(slots) >= TOP_N or score < threshold:
                break
            if row_idx == exact_row:
                continue
            slots.append(row_slot(row_idx, round(score)))

    while len(slots) < TOP_N:
        slots.append(no_match_customer_slot())
    return slots[:TOP_N]


# --- Material matching -----------------------------------------------------

def no_match_material_slot() -> dict:
    return {
        "material_code": NO_MATCH,
        "material_description": NO_MATCH,
        "match_score": 0,
    }


def match_materials(
    description: str, code: str, material_df: pd.DataFrame, threshold: int
) -> list[dict]:
    """Top-3 material matches for one line item.

    An exact material-code hit takes slot 1 with score 100; remaining slots
    are filled by fuzzy description matching. Cross-language descriptions
    (e.g. Chinese PO vs English reference) will not match semantically and
    surface as [NO MATCH] — a documented limitation.
    """
    empty = [no_match_material_slot() for _ in range(TOP_N)]
    if material_df is None or material_df.empty:
        return empty

    code_col = _col(material_df, "Material")
    desc_col = _col(material_df, "Material Description")

    slots: list[dict] = []
    exact_row = None
    if _usable(code) and code_col is not None:
        hits = code_col[code_col.astype(str).str.strip() == str(code).strip()]
        if not hits.empty:
            exact_row = hits.index[0]
            row_pos = material_df.index.get_loc(exact_row)
            slots.append({
                "material_code": str(code_col.iloc[row_pos]).strip(),
                "material_description": (
                    str(desc_col.iloc[row_pos]).strip() if desc_col is not None else NO_MATCH
                ),
                "match_score": 100,
            })

    if desc_col is not None and _usable(description):
        scored = []
        for i in range(len(material_df)):
            if exact_row is not None and material_df.index[i] == exact_row:
                continue
            scored.append((composite_score(description, desc_col.iloc[i]), i))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        for score, row_idx in scored:
            if len(slots) >= TOP_N or score < threshold:
                break
            slots.append({
                "material_code": str(code_col.iloc[row_idx]).strip() if code_col is not None else NO_MATCH,
                "material_description": str(desc_col.iloc[row_idx]).strip(),
                "match_score": round(score),
            })

    while len(slots) < TOP_N:
        slots.append(no_match_material_slot())
    return slots[:TOP_N]


# --- Sales org matching and sales area lookup ------------------------------

def no_match_sales_org() -> dict:
    return {"sales_org_code": NO_MATCH, "sales_org_name": NO_MATCH, "match_score": 0}


def match_sales_org(
    manufacturer_name: str,
    sales_org_df: pd.DataFrame,
    threshold: int,
    candidates: tuple[str, ...] | list[str] = (),
) -> dict:
    """Single best sales-organization match across the manufacturer name and
    any alternate candidate readings extracted from the document."""
    queries = [q for q in [manufacturer_name, *candidates] if _usable(q)]
    if not queries or sales_org_df is None or sales_org_df.empty:
        return no_match_sales_org()

    name_col = _col(sales_org_df, "Name")
    code_col = _col(sales_org_df, "Sales Organization")
    if name_col is None or code_col is None:
        return no_match_sales_org()

    best_score, best_idx, best_query = 0.0, None, None
    for query in queries:
        for i in range(len(sales_org_df)):
            score = composite_score(query, name_col.iloc[i])
            if score > best_score:
                best_score, best_idx, best_query = score, i, query

    if best_idx is None or best_score < threshold:
        return no_match_sales_org()
    if best_query != manufacturer_name:
        logger.info("Manufacturer candidate '%s' outscored primary for sales org matching", best_query)
    return {
        "sales_org_code": str(code_col.iloc[best_idx]).strip(),
        "sales_org_name": str(name_col.iloc[best_idx]).strip(),
        "match_score": round(best_score),
    }


def lookup_sales_area(sales_org_code: str, sales_area_df: pd.DataFrame) -> dict:
    """All Distribution Channel / Division rows for a sales org, pipe-joined."""
    if not _usable(sales_org_code) or sales_area_df is None or sales_area_df.empty:
        return {"distribution_channels": NO_MATCH, "divisions": NO_MATCH}

    org_col = _col(sales_area_df, "Sales Organization")
    channel_col = _col(sales_area_df, "Distribution Channel")
    division_col = _col(sales_area_df, "Division")
    if org_col is None:
        return {"distribution_channels": NO_MATCH, "divisions": NO_MATCH}

    mask = org_col.astype(str).str.strip() == str(sales_org_code).strip()
    positions = [i for i, hit in enumerate(mask) if hit]
    if not positions:
        return {"distribution_channels": NO_MATCH, "divisions": NO_MATCH}

    channels = [str(channel_col.iloc[i]).strip() for i in positions] if channel_col is not None else []
    divisions = [str(division_col.iloc[i]).strip() for i in positions] if division_col is not None else []
    return {
        "distribution_channels": "|".join(channels) if channels else NO_MATCH,
        "divisions": "|".join(divisions) if divisions else NO_MATCH,
    }


# --- Whole-PO matching -----------------------------------------------------

def match_purchase_order(po, reference: dict[str, pd.DataFrame], threshold: int) -> dict:
    """Run every matcher for one PurchaseOrder and bundle the results."""
    sales_org = match_sales_org(po.manufacturer_name, reference.get("salesOrg"), threshold,
                                candidates=po.manufacturer_candidates)
    return {
        "sold_to": match_customers(po.sold_to.name, reference.get("customerList"), threshold,
                                   customer_number=po.sold_to.customer_number,
                                   candidates=po.sold_to.name_candidates),
        "ship_to": match_customers(po.ship_to.name, reference.get("customerList"), threshold,
                                   customer_number=po.ship_to.customer_number,
                                   candidates=po.ship_to.name_candidates),
        "sales_org": sales_org,
        "sales_area": lookup_sales_area(sales_org["sales_org_code"], reference.get("salesArea")),
        "line_items": [
            match_materials(item.material_description, item.material_code,
                            reference.get("materialList"), threshold)
            for item in po.line_items
        ],
    }
