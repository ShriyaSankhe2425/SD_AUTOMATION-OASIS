"""FastAPI backend for the SD-Automation frontend.

Wraps the existing PO-parsing pipeline (``pipeline/run.py``) behind the
6-endpoint contract the frontend's ``src/services/apiClient.ts`` expects.
Reference data and the Gemini client are loaded once at startup and reused
across requests; extraction results are kept in an in-memory store keyed by
a generated extraction id (resets on server restart).
"""

import logging
import re
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import config
from models.schema import PurchaseOrder
from pipeline import extraction
from pipeline.run import PageResult, process_document
from reference.loader import load_reference_data

logger = logging.getLogger(__name__)

# extraction_id -> list[PageResult]
_STORE: dict[str, list[PageResult]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.reference = load_reference_data(config.DATA_DIR)
    app.state.client = extraction.get_client(config.GOOGLE_API_KEY) if config.GOOGLE_API_KEY else None
    yield


app = FastAPI(title="SD-Automation API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        code, message = detail["code"], detail["message"]
    else:
        code, message = "ERROR", str(detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": code, "message": message}, "timestamp": _now()},
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ok(data) -> dict:
    return {"success": True, "data": data, "timestamp": _now()}


def _usable(value) -> bool:
    return bool(value) and value not in (config.MISSING, config.NO_MATCH)


def _clean(value: str) -> str:
    return value if _usable(value) else ""


def _to_float(value: str) -> float:
    if not _usable(value):
        return 0.0
    match = re.search(r"-?\d[\d,]*\.?\d*", str(value))
    if not match:
        return 0.0
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return 0.0


def _get_results(extraction_id: str) -> list[PageResult]:
    results = _STORE.get(extraction_id)
    if results is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"No extraction found for id '{extraction_id}'"},
        )
    return results


# --- Response builders -------------------------------------------------

def _header_rows(po: PurchaseOrder, matches: dict) -> list[dict]:
    sold_to_slots = matches.get("sold_to") or []
    ship_to_slots = matches.get("ship_to") or []
    sold_to_top = sold_to_slots[0] if sold_to_slots else {}
    ship_to_top = ship_to_slots[0] if ship_to_slots else {}
    sales_org = matches.get("sales_org") or {}
    sales_area = matches.get("sales_area") or {}

    sold_to_code = _clean(po.sold_to.customer_number) or _clean(sold_to_top.get("customer_code", ""))
    ship_to_code = _clean(po.ship_to.customer_number) or _clean(ship_to_top.get("customer_code", ""))

    return [
        {"field": "BSTNK", "table": "VBKD", "description": "Customer PO Number",
         "value": _clean(po.po_number), "status": "MATCHED" if _usable(po.po_number) else "MISSING", "notes": ""},
        {"field": "BSTDK", "table": "VBKD", "description": "Customer PO Date",
         "value": _clean(po.issue_date), "status": "MATCHED" if _usable(po.issue_date) else "MISSING", "notes": ""},
        {"field": "VKORG", "table": "VBAK", "description": "Sales Organization",
         "value": _clean(sales_org.get("sales_org_code", "")),
         "status": "MATCHED" if _usable(sales_org.get("sales_org_code", "")) else "UNMATCHED",
         "notes": _clean(sales_org.get("sales_org_name", ""))},
        {"field": "VTWEG", "table": "VBAK", "description": "Distribution Channel",
         "value": _clean(sales_area.get("distribution_channels", "")),
         "status": "MATCHED" if _usable(sales_area.get("distribution_channels", "")) else "UNMATCHED", "notes": ""},
        {"field": "SPART", "table": "VBAK", "description": "Division",
         "value": _clean(sales_area.get("divisions", "")),
         "status": "MATCHED" if _usable(sales_area.get("divisions", "")) else "UNMATCHED", "notes": ""},
        {"field": "AUART", "table": "VBAK", "description": "Sales Document Type",
         "value": "", "status": "REQUIRED", "notes": "Not extracted from the PO; user input required"},
        {"field": "KUNNR (Sold-to)", "table": "VBPA", "description": "Sold-to Party",
         "value": sold_to_code, "status": "MATCHED" if sold_to_code else "REQUIRED",
         "notes": _clean(po.sold_to.name) or _clean(sold_to_top.get("customer_name1", ""))},
        {"field": "KUNNR (Ship-to)", "table": "VBPA", "description": "Ship-to Party",
         "value": ship_to_code, "status": "MATCHED" if ship_to_code else "REQUIRED",
         "notes": _clean(po.ship_to.name) or _clean(ship_to_top.get("customer_name1", ""))},
    ]


def _line_item_rows(po: PurchaseOrder, matches: dict) -> list[dict]:
    material_matches = matches.get("line_items") or []
    rows = []
    for idx, item in enumerate(po.line_items):
        slots = material_matches[idx] if idx < len(material_matches) else []
        top = slots[0] if slots else {}
        matnr = _clean(top.get("material_code", ""))
        rows.append({
            "lineNumber": str((idx + 1) * 10),
            "poDescription": _clean(item.material_description),
            "matnr": matnr,
            "matchScore": top.get("match_score", 0),
            "quantity": _to_float(item.quantity),
            "unit": "PC",  # not extracted by the Gemini schema; defaulted
            "unitPrice": _to_float(item.unit_price),
            "totalPrice": _to_float(item.total),
            "deliveryDate": "",
            "status": "MATCHED" if matnr else "UNMATCHED",
        })
    return rows


def _build_order(po_index: int, result: PageResult) -> dict:
    po = result.po
    return {
        "poIndex": po_index,
        "poNumber": _clean(po.po_number) or f"PO-{po_index}",
        "header": _header_rows(po, result.matches),
        "lineItems": _line_item_rows(po, result.matches),
    }


def _build_extracted_data(results: list[PageResult]) -> dict:
    first = results[0]
    po, matches = first.po, first.matches
    sales_org = matches.get("sales_org") or {}

    line_items = []
    material_matches = matches.get("line_items") or []
    for idx, item in enumerate(po.line_items):
        slots = material_matches[idx] if idx < len(material_matches) else []
        top = slots[0] if slots else {}
        total_price = _to_float(item.total)
        line_items.append({
            "lineNumber": str((idx + 1) * 10),
            "materialNumber": _clean(top.get("material_code", "")),
            "materialDescription": _clean(item.material_description),
            "quantity": _to_float(item.quantity),
            "unitOfMeasure": "PC",
            "unitPrice": _to_float(item.unit_price),
            "totalPrice": total_price,
        })

    total_amount = sum(li["totalPrice"] for li in line_items)

    return {
        "poNumber": _clean(po.po_number),
        "poDate": _clean(po.issue_date),
        "vendor": {
            "name": _clean(po.manufacturer_name),
            "number": _clean(sales_org.get("sales_org_code", "")),
        },
        "lineItems": line_items,
        "totalAmount": total_amount if total_amount else None,
        "currency": None,
        "rawText": "PO extracted via Gemini vision OCR",
        "rawJSON": po.model_dump(),
        "orders": [_build_order(i + 1, r) for i, r in enumerate(results)],
    }


def _build_mappings(results: list[PageResult]) -> list[dict]:
    mappings = []
    for page_number, result in enumerate(results, start=1):
        po, matches = result.po, result.matches
        # Must match _build_order's fallback exactly (same page_number-based
        # scheme), or the frontend's header-row lookup (keyed by poNumber)
        # misses whenever po_number extraction fails on a page.
        po_number = _clean(po.po_number) or f"PO-{page_number}"
        sold_to_slots = matches.get("sold_to") or []
        ship_to_slots = matches.get("ship_to") or []
        sold_to_top = sold_to_slots[0] if sold_to_slots else {}
        ship_to_top = ship_to_slots[0] if ship_to_slots else {}
        material_matches = matches.get("line_items") or []

        for idx, item in enumerate(po.line_items):
            slots = material_matches[idx] if idx < len(material_matches) else []
            top = slots[0] if slots else {}
            material_number = _clean(top.get("material_code", ""))
            mappings.append({
                "poNumber": po_number,
                "lineNumber": str((idx + 1) * 10),
                "materialNumber": material_number,
                "materialDescription": _clean(item.material_description),
                "quantity": _to_float(item.quantity),
                "unitOfMeasure": "PC",
                "unitPrice": _to_float(item.unit_price),
                "totalPrice": _to_float(item.total),
                "suggestedSoldTo": _clean(sold_to_top.get("customer_code", "")),
                "suggestedShipTo": _clean(ship_to_top.get("customer_code", "")),
                "pricingDate": _clean(po.issue_date),
                "matchScore": top.get("match_score", 0),
                "status": "MATCHED" if material_number else "UNMATCHED",
            })
    return mappings


# --- Endpoints -----------------------------------------------------------

@app.post("/api/v1/extract")
async def upload_pdf(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in config.SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail={
            "code": "UNSUPPORTED_FILE_TYPE",
            "message": f"Unsupported file type '{suffix}'. Supported: {', '.join(sorted(config.SUPPORTED_EXTENSIONS))}",
        })
    if app.state.client is None:
        raise HTTPException(status_code=500, detail={
            "code": "MISSING_API_KEY",
            "message": "GOOGLE_API_KEY is not set on the server. Copy .env.example to .env and add your key.",
        })

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        results = process_document(
            tmp_path, app.state.client, config.DEFAULT_MODEL, app.state.reference, config.DEFAULT_THRESHOLD,
        )
    except Exception as exc:
        logger.exception("Extraction failed for %s", file.filename)
        raise HTTPException(status_code=500, detail={"code": "EXTRACTION_FAILED", "message": str(exc)}) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    if not results:
        raise HTTPException(status_code=422, detail={
            "code": "NO_PAGES", "message": f"No non-blank pages found in {file.filename}.",
        })

    extraction_id = f"extract_{uuid.uuid4().hex[:12]}"
    _STORE[extraction_id] = results
    return _ok({"extractionId": extraction_id, "status": "completed"})


@app.get("/api/v1/extract/{extraction_id}")
async def get_extracted_data(extraction_id: str):
    results = _get_results(extraction_id)
    return _ok(_build_extracted_data(results))


@app.get("/api/v1/mapping/suggest/{extraction_id}")
async def get_mapping_suggestions(extraction_id: str):
    results = _get_results(extraction_id)
    return _ok({"mappings": _build_mappings(results)})


@app.post("/api/v1/mapping/validate")
async def validate_mapping(payload: dict):
    mappings = payload.get("mappings", [])
    errors = []
    for idx, mapping in enumerate(mappings):
        if not mapping.get("materialNumber"):
            errors.append({"field": f"mappings[{idx}].materialNumber", "message": "Material Number is required"})
        if not (mapping.get("soldToParty") or mapping.get("suggestedSoldTo")):
            errors.append({"field": f"mappings[{idx}].soldToParty", "message": "Sold-to Party is required"})
        if not (mapping.get("shipToParty") or mapping.get("suggestedShipTo")):
            errors.append({"field": f"mappings[{idx}].shipToParty", "message": "Ship-to Party is required"})
    return _ok({"isValid": len(errors) == 0, "errors": errors})


@app.post("/api/v1/sap/create-order")
async def create_sap_order(payload: dict):
    # No real SAP system in this repo; stub matching the frontend's own
    # documented mock response, kept here as a placeholder for a future
    # SAP integration.
    sap_order_number = f"5000{uuid.uuid4().hex[:8].upper()}"
    return _ok({"sapOrderNumber": sap_order_number, "status": "created"})


@app.get("/api/v1/master-data/{data_type}")
async def get_master_data(data_type: str):
    reference = app.state.reference
    columns_by_type = {
        "materials": ("materialList", ["Material", "Material Description"]),
        "customers": ("customerList", ["Customer", "Name 1", "Name 2", "Country", "City"]),
        "vendors": ("salesOrg", ["Sales Organization", "Name"]),
    }
    if data_type not in columns_by_type:
        raise HTTPException(status_code=404, detail={
            "code": "UNKNOWN_TYPE", "message": f"Unknown master-data type '{data_type}'.",
        })

    key, columns = columns_by_type[data_type]
    df = reference.get(key)
    if df is None or df.empty:
        return _ok({"data": []})

    existing_columns = [c for c in columns if c in df.columns]
    return _ok({"data": df[existing_columns].to_dict(orient="records")})
