# SD-Automation: Purchase Order to SAP Sales Order Transformation

A web application that extracts structured data from Purchase Order documents (PDF or image, any language/layout) using the Gemini vision API, fuzzy-matches the extracted entities against reference master data, and takes a user through a guided review-and-correct flow that ends in a copyable SAP OData sales-order payload.

```
PO document (PDF/JPG/PNG)
   └─> page images ─> preprocessing ─> Gemini extraction ─> normalization
        ─> fuzzy matching vs reference master data ─> interactive review (web app) ─> SAP payload
```

Built as two parts sharing one pipeline (`pipeline/run.py::process_document`): a **FastAPI backend** (`api/`) and a **React frontend** (`frontend/`).

## Requirements

- Python 3.11+ (developed on 3.14)
- Node.js 18+ and npm
- A Google AI Studio API key ([get one here](https://aistudio.google.com/apikey))
- Reference master-data files (see [Reference data](#reference-data)) — this repo ships `jp_data/` (default) and `cn_data/`

## Setup

```bash
# 1. Python environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt

# 2. Configure your API key
copy .env.example .env        # Windows (cp on macOS/Linux)
# then edit .env and set GOOGLE_API_KEY=<your key>

# 3. Frontend dependencies
cd frontend
npm install
cd ..
```

## Running it

Run both in separate terminals:

```bash
# Terminal 1 — backend (from the project root)
.venv/Scripts/python.exe -m uvicorn api.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev
```

Open `http://localhost:5173`. The wizard has 4 steps:

1. **Ingestion Hub** — drag/drop or select a PO (PDF/image), click Process. This uploads to `POST /api/v1/extract`, which runs the full pipeline synchronously and returns an `extractionId`.
2. **Intelligence Review** — read-only side-by-side view of the original PO document and everything extracted/matched, one card per PO/page (`GET /api/v1/extract/{id}`).
3. **SAP Mapping** — editable grid of SAP header fields (Sales Org, Distribution Channel, Division, Sales Document Type, Sold-to/Ship-to) and line items, pre-filled with the pipeline's best matches (`GET /api/v1/mapping/suggest/{id}`). Multi-value matches (e.g. multiple valid distribution channels) render as dropdowns.
4. **Push to SAP** — builds a SAP OData-shaped JSON payload from the current (possibly edited) field values and displays it with a Copy to Clipboard button, for manual testing against a real SAP endpoint via Postman. No live SAP system is connected in this repo — `POST /api/v1/sap/create-order` is a stub.

Environment variables (via `.env` or the shell): `GOOGLE_API_KEY` (required), `GEMINI_MODEL` and `MATCH_THRESHOLD` (optional default overrides). Frontend: `VITE_API_URL` (defaults to `http://localhost:8000/api/v1`).

Supported PO input types: `.pdf`, `.jpg`, `.jpeg`, `.png`. Each PDF page is treated as a potentially independent PO.

## Reference data

Purchase orders processed by this tool are frequently written in Japanese, Chinese, and other non-English languages — matching them against master data (customers, materials, sales organizations) requires that master data to be available for lookup in the first place. Four categories of SAP master data drive the matching step:

| Data | Used for |
|---|---|
| Customer master (Sold-to / Ship-to) | Matching extracted party names/codes to SAP customer records |
| Material master | Matching extracted line-item descriptions/codes to SAP material numbers |
| Sales organization | Matching the extracted manufacturer/supplier to a sales org |
| Sales area (distribution channel / division) | Looked up from the matched sales org |

**`jp_data/`** (Japanese) and **`cn_data/`** (Chinese) are local data dumps of this master data, used **as a stand-in until a live SAP connection is available**. Once that connection exists, these lookups should be replaced with a real-time API/OData call against SAP directly instead of static local files — the matching logic in `pipeline/matching.py` would stay the same, only the data source changes.

A missing file or column never crashes a run — it logs a warning and the affected match columns come back as `[NO MATCH]`.

## Pipeline stages and their logic

### 1. Ingestion — `pipeline/ingestion.py`

Routes the input by extension. PDFs are rendered page-by-page at 300 DPI with PyMuPDF; images are loaded directly with Pillow. Each page also gets a *scanned vs digital* hint: a PDF page with a real text layer is a digital render, everything else is treated as a scan. That hint decides later whether binarization is safe.

### 2. Preprocessing — `pipeline/preprocessing.py`

Normalizes each page image before it goes to the vision model. Every step can be toggled in `config.py`, and a step that throws logs a warning and passes the image through unchanged:

1. **Deskew** — threshold the page (Otsu), find the text pixels' minimum-area rectangle, and rotate by the detected angle. Gated to angles between 1° and 45° so noise never triggers a wild rotation.
2. **Upscale** — if the shorter side is under 1000 px, Lanczos-upscale so the model gets enough resolution.
3. **Contrast** — grayscale + CLAHE adaptive histogram equalization to flatten uneven scan lighting.
4. **Binarization** *(off by default)* — adaptive thresholding, applied only to scanned pages when enabled. It is disabled by default because it destroys handwriting stroke texture and color cues on digital renders.

Pages with almost no pixel variance are detected as blank and skipped entirely.

### 3. Extraction — `pipeline/extraction.py`

Sends the processed image to Gemini (`temperature=0`, 60 s timeout) using **native structured outputs**: the JSON schema is enforced server-side via `response_schema` (a Pydantic model), per [Google's structured-output guidance](https://ai.google.dev/gemini-api/docs/structured-output), which also warns against pasting the schema into the prompt. Each schema field carries a `description` that steers the model — most importantly, `company_name` is defined as *"the organization's name ONLY … never a street address, city, postal code, phone number, or numeric code"*, and codes printed near a party block are routed to a dedicated `customer_number` field.

Because POs have no fixed template, the prompt is a **reading guide** rather than a schema dump: a multilingual label glossary (English + Japanese: 発注元/注文者 = sold-to, 納入先/納品先 = ship-to, 仕入先/メーカー/御中-addressee = manufacturer, 品名/数量/単価/金額 = line-item columns, …) that Gemini translates internally to locate fields, while all output **values** stay verbatim in their original language.

Ambiguity is captured instead of forced: uncertain party names and manufacturer readings go into `name_candidates` / `manufacturer_candidates` lists, and the literal label found near each party is recorded in `label_text` for auditability. Response handling:

- Structured output returns clean JSON; fence-stripping and parsing are kept as a defensive fallback.
- Invalid JSON triggers **one** retry with a clarifying prompt; if that also fails, the page is marked `parse_error=True` (with the reason in `parse_error_detail`) and the batch continues.
- HTTP 429/500/503 are retried with exponential backoff (2 s, 4 s, 8 s), max 3 attempts per call.
- Gemini's token usage (prompt/output/total) is logged per call and summed per document.

### 4. Normalization — `pipeline/normalization.py` + `models/schema.py`

Coerces the raw JSON into a validated Pydantic `PurchaseOrder` model. All values are whitespace-stripped; any variant of "missing" (`missing`, `MISSING`, `[missing]`) becomes the canonical `[MISSING]`; absent keys default to `[MISSING]`. Dates, quantities, and prices are deliberately **not** reformatted — original document formatting is preserved. A malformed line item degrades to all-`[MISSING]` fields instead of failing the PO.

### 5. Reference loading — `reference/loader.py`

Loads all four master-data files once at startup as string DataFrames (so codes like `0001` keep their leading zeros), strips whitespace, and replaces NaN with `""`. Column lookups later in the pipeline are case-insensitive.

### 6. Fuzzy matching — `pipeline/matching.py`

All matching uses RapidFuzz with a composite score — `max(token_sort_ratio, partial_ratio, WRatio)` — so reordered words, abbreviations, and general similarity are all covered. One threshold (default 60, `MATCH_THRESHOLD`) applies to every entity type; anything below it becomes `[NO MATCH]`.

- **Customers** (sold-to and ship-to): an extracted **customer number** that exactly matches the `Customer` column takes slot 1 with score 100 — no fuzzing needed. Otherwise, common business suffixes (`Ltd`, `Pvt`, `GmbH`, …) are stripped from the query (unless that would leave a uselessly short fragment; originals are always preserved for output), each row is scored against both `Name 1` and `Name 2` (higher wins), and the **top 3** matches are returned. If the primary extracted name scores poorly, each `name_candidates` alternate is tried and the best-scoring query wins.
- **Materials** (per line item): an exact `Material` code hit takes slot 1 with score 100; remaining slots are filled by fuzzy-matching the description against `Material Description`. Top 3 returned. RapidFuzz handles Unicode, so Chinese/Japanese/French descriptions match at the character level — but *cross-language* matching (e.g. Chinese PO vs English-only reference) is surface-level only and will return `[NO MATCH]`.
- **Sales org** (manufacturer name): single best match against `Name`, trying the primary name and every `manufacturer_candidates` alternate — one code is enough to drive the sales area lookup.
- **Sales area**: exact lookup of the matched sales org code; **all** matching Distribution Channel / Division rows are returned pipe-joined (e.g. `10|20`) — the SAP Mapping screen renders these as a dropdown when more than one distinct value exists.

### Error handling principle

A single page, API hiccup, or bad line item never crashes the batch. Failures are logged, flagged in the output (`parse_error`, `[MISSING]`, `[NO MATCH]`), and processing continues.

## API endpoints (`api/main.py`)

All responses are wrapped in `{success, data?, error?, timestamp}`.

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/extract` | Upload a PO, run the full pipeline synchronously, return an `extractionId` |
| `GET /api/v1/extract/{id}` | Full extracted + matched data for that upload (Intelligence Review screen) |
| `GET /api/v1/mapping/suggest/{id}` | Flattened, pre-filled mapping suggestions (SAP Mapping screen) |
| `POST /api/v1/mapping/validate` | Lightweight required-field check |
| `POST /api/v1/sap/create-order` | Stub — no real SAP system connected |
| `GET /api/v1/master-data/{materials\|customers\|vendors}` | Serves the loaded reference master data |

Extraction results are held in an **in-memory store**, not a database — restarting the backend clears all previously-uploaded results.

## Testing

```bash
python -m pytest tests -q
```

44 tests cover preprocessing (deskew/upscale/contrast/blank detection on synthetic images), extraction (JSON parsing, fence stripping, clarify-retry, backoff, token-usage accounting — all against a mocked client, no live API calls), normalization, and matching (including Unicode and cross-language cases).

## Known limitations

- **Cross-language matching**: fuzzy matching is surface-level; a Chinese description will not match an English reference entry. Such cases return `[NO MATCH]`. (A Gemini translation pre-pass would be a future enhancement.)
- **Multiple sales areas per org** are pipe-joined rather than disambiguated automatically (surfaced as a dropdown for the user to pick in the SAP Mapping screen).
- **Handwriting** relies entirely on Gemini's native capability; no dedicated OCR pass.
- **Address ambiguity**: documents with 3+ unlabeled addresses may have sold-to/ship-to assigned incorrectly.
- **No persistent storage anywhere** — no database; extraction results, wizard state, and the SAP payload all live only in server/browser memory until refresh or restart.
- **No real SAP integration** — the final step produces a copyable payload for manual testing, not a live submission.
- **Unit of measure is not extracted** by the Gemini schema; the API layer defaults it to `"PC"` everywhere.
