# Purchase Order Parsing System — Implementation Plan

## Overview

A Python CLI application that ingests purchase order documents (image or PDF), extracts structured data using the Gemini vision API, matches extracted entities against Excel reference data using fuzzy matching, and exports results to CSV.

---

## Technology Stack

| Layer | Library / Tool | Rationale |
|---|---|---|
| CLI | `click` | Mature, composable, supports flags cleanly |
| PDF handling | `pymupdf` (fitz) | Fast, reliable PDF-to-image conversion; handles rotation |
| Image preprocessing | `Pillow`, `opencv-python` | Skew correction, contrast, binarization |
| Vision extraction | `google-generativeai` | Gemini vision API |
| Excel reading | `openpyxl` or `pandas` | Read `.xlsx` reference data |
| Fuzzy matching | `rapidfuzz` | Fast, multilingual-tolerant, Levenshtein + token sort |
| CSV export | `csv` (stdlib) or `pandas` | Simple; no extra deps needed |
| Logging | `logging` (stdlib) + `rich` (optional) | Structured logs; rich for verbose console output |
| Config | `python-dotenv` | API keys, defaults from `.env` |
| Validation | `pydantic` | Structured extraction schema enforcement |

**Python version:** 3.11+

---

## Project Structure

```
ingestAutomation/
├── main.py                    # CLI entry point
├── config.py                  # Constants, defaults, env loading
├── pipeline/
│   ├── __init__.py
│   ├── ingestion.py           # File detection and routing
│   ├── preprocessing.py       # Image normalization
│   ├── extraction.py          # Gemini API calls and prompt logic
│   ├── normalization.py       # JSON cleaning and field standardization
│   ├── matching.py            # Fuzzy matching against reference data
│   ├── export.py              # CSV writer
│   └── audit.py               # Verbose logging and audit trail
├── reference/
│   └── loader.py              # Load and cache Excel reference data
├── models/
│   └── schema.py              # Pydantic models for extracted PO data
├── data/                      # Excel reference files (user-provided)
│   ├── customerList.xlsx
│   ├── materialList.xlsx
│   ├── salesOrg.xlsx
│   └── salesArea.xlsx
├── output/                    # Default CSV output directory
├── tests/
│   ├── test_preprocessing.py
│   ├── test_extraction.py
│   ├── test_matching.py
│   └── test_export.py
├── .env.example
└── requirements.txt
```

---

## Phase 1 — Project Bootstrap and CLI Scaffold

### Goals
- Establish the project skeleton, config system, and CLI interface.

### Tasks

1. Create `requirements.txt` with all dependencies pinned.
2. Create `.env.example` with `GOOGLE_API_KEY=` and any other secrets.
3. Implement `config.py`:
   - Load env vars via `python-dotenv`.
   - Define defaults: output dir, confidence threshold, default model ID.
4. Implement `main.py` using `click`:

```
Usage: python main.py [OPTIONS] INPUT_PATH

Options:
  --model TEXT         Gemini model ID [default: gemini-1.5-flash]
  --output PATH        Output directory [default: ./output/]
  --threshold INTEGER  Fuzzy match minimum score 0-100 [default: 60]
  --verbose            Write audit logs alongside CSV output
  --help               Show this message and exit.
```

5. Validate that `INPUT_PATH` exists and has a supported extension (`.pdf`, `.jpg`, `.jpeg`, `.png`).
6. Create output directory if it does not exist.

### Uncertainty
- Model ID naming conventions may shift as Google updates Gemini. The model flag should accept any string and pass it directly to the API, with a documented default. Do not hardcode a version beyond the default.

---

## Phase 2 — Document Ingestion and Image Preprocessing

### Goals
- Accept PDFs and images, normalize them into clean PIL/numpy images ready for the vision model.

### Module: `pipeline/ingestion.py`

**Logic:**
- If input is `.pdf`: use `pymupdf` to render each page to a high-resolution image (300 DPI minimum).
- If input is `.jpg/.jpeg/.png`: load directly with Pillow.
- Return a list of `(page_index, PIL.Image)` tuples.

**Multi-page PDF handling:**
- Treat each page as a potentially independent PO.
- Pass each page through preprocessing and extraction separately.
- One output CSV row per page that yields a valid PO extraction.
- If a page yields no meaningful extraction (e.g., blank page, cover sheet), log it and skip — do not emit an empty row.

### Module: `pipeline/preprocessing.py`

Apply the following steps in order. Each step should be individually toggleable via constants in `config.py` so they can be disabled if they cause regressions on specific document types.

**Step 1 — Deskew / rotation correction**
- Use OpenCV to detect dominant line angles via Hough transform or `minAreaRect` on text blobs.
- Rotate the image to straighten it.
- Uncertainty: deskew algorithms can fail on heavily noisy or sparse images. Apply a confidence gate: only rotate if the detected angle exceeds 1 degree and is below 45 degrees.

**Step 2 — Upscaling (if needed)**
- If either dimension is below 1000px, upscale using Lanczos resampling to ensure the vision model receives sufficient resolution.

**Step 3 — Grayscale and contrast normalization**
- Convert to grayscale.
- Apply adaptive histogram equalization (CLAHE via OpenCV) to handle uneven lighting in scanned documents.

**Step 4 — Binarization (optional)**
- Apply Otsu or adaptive thresholding only if the image is determined to be a scanned document (not a digital PDF render).
- Digital PDF renders should be left as-is; binarizing them can destroy color cues.

**Step 5 — Final export**
- Return processed image as `PIL.Image` in RGB mode for the Gemini API.

**Note on handwriting:**
- Preprocessing cannot reliably improve handwritten content beyond contrast normalization. The Gemini vision model's native handwriting recognition capability should be relied upon. Do not apply heavy binarization to handwritten documents as it destroys stroke texture.

---

## Phase 3 — Vision Extraction via Gemini

### Module: `pipeline/extraction.py`

### Gemini API Setup
- Use `google-generativeai` Python SDK.
- Initialize `genai.GenerativeModel(model_name=model_id)`.
- Accept `model_id` as a parameter, defaulting to `gemini-1.5-flash`.

### Prompt Engineering Strategy

The prompt is the most critical piece of this system. It must:

1. Define the output format as JSON.
2. List every field to extract.
3. Explicitly instruct the model not to hallucinate.
4. Handle the ambiguity of multiple address types.
5. Instruct the model to preserve multilingual content verbatim.

**Recommended prompt structure (system instructions + user turn):**

```
SYSTEM:
You are a structured data extraction assistant. You extract information from 
purchase order documents exactly as it appears. You never invent, infer, or 
hallucinate data. If a field is not present in the document, return the exact 
string [MISSING] for that field.

USER:
Extract the following fields from this purchase order image. Return a single 
valid JSON object and nothing else.

Schema:
{
  "po_number": "string or [MISSING]",
  "issue_date": "string in original format or [MISSING]",
  "sold_to": {
    "name": "string or [MISSING]",
    "address": "string or [MISSING]",
    "city": "string or [MISSING]",
    "country": "string or [MISSING]",
    "postal_code": "string or [MISSING]"
  },
  "ship_to": {
    "name": "string or [MISSING]",
    "address": "string or [MISSING]",
    "city": "string or [MISSING]",
    "country": "string or [MISSING]",
    "postal_code": "string or [MISSING]"
  },
  "manufacturer_name": "string or [MISSING]",
  "shipping_details": "string or [MISSING]",
  "line_items": [
    {
      "material_description": "string or [MISSING]",
      "material_code": "string or [MISSING]",
      "quantity": "string or [MISSING]",
      "unit_price": "string or [MISSING]",
      "total": "string or [MISSING]"
    }
  ]
}

Rules:
- Preserve all text in its original language. Do not translate.
- Dates should be extracted as they appear in the document, not reformatted.
- If there is no sold-to party (only a ship-to), populate ship_to and leave 
  sold_to fields as [MISSING].
- If there are multiple addresses and you cannot confidently identify which 
  is sold-to vs ship-to, populate the first/most prominent one as sold_to 
  and the second as ship_to.
- Do not return any text outside the JSON object.
```

### API Call

- Send the processed image as base64-encoded bytes alongside the prompt.
- Use `response = model.generate_content([prompt, image])`.
- Set `generation_config` with `temperature=0` to minimize hallucination.
- Set a reasonable timeout (e.g. 60s per page).

### Response Parsing

- Strip any markdown fences (```json ... ```) from the response text before parsing.
- Parse with `json.loads()`.
- If parsing fails, retry once with a clarifying prompt asking the model to return only valid JSON.
- If the retry also fails, log the raw response and mark the entire PO extraction as failed with a `parse_error` flag.

### Rate Limiting and Retry
- Implement exponential backoff (2, 4, 8 seconds) on HTTP 429 or 500 responses.
- Max 3 retries per page.

---

## Phase 4 — Normalization and Validation

### Module: `pipeline/normalization.py`
### Module: `models/schema.py`

### Pydantic Schema

Define a `PurchaseOrder` Pydantic model mirroring the extraction JSON schema. This serves two purposes:
1. Validates that all required keys are present after extraction.
2. Provides type-safe access throughout the pipeline.

```python
class Address(BaseModel):
    name: str
    address: str
    city: str
    country: str
    postal_code: str

class LineItem(BaseModel):
    material_description: str
    material_code: str
    quantity: str
    unit_price: str
    total: str

class PurchaseOrder(BaseModel):
    po_number: str
    issue_date: str
    sold_to: Address
    ship_to: Address
    manufacturer_name: str
    shipping_details: str
    line_items: list[LineItem]
    source_file: str
    page_index: int
    parse_error: bool = False
    parse_error_detail: str = ""
```

All field values default to `"[MISSING]"` if absent, not `None`. This ensures the CSV always has a value and `[MISSING]` is unambiguous.

### Normalization Steps

- Strip leading/trailing whitespace from all string values.
- Normalize `[MISSING]` casing: any variant (`missing`, `MISSING`, `[missing]`) should be coerced to `[MISSING]`.
- Do not attempt to reformat dates, quantities, or prices. Preserve original formatting to avoid introducing errors.
- Do not attempt currency conversion or unit normalization.

---

## Phase 5 — Reference Data Loading

### Module: `reference/loader.py`

Load all four Excel files once at startup and cache them in memory as pandas DataFrames. This avoids repeated disk I/O during batch processing.

**Loading logic:**

```python
def load_reference_data(data_dir: Path) -> dict[str, pd.DataFrame]:
    return {
        "customerList": pd.read_excel(data_dir / "customerList.xlsx"),
        "materialList": pd.read_excel(data_dir / "materialList.xlsx"),
        "salesOrg": pd.read_excel(data_dir / "salesOrg.xlsx"),
        "salesArea": pd.read_excel(data_dir / "salesArea.xlsx"),
    }
```

**Preprocessing on load:**
- Strip whitespace from all string columns.
- Fill NaN values with empty string `""` so matching functions never receive NaN.
- Normalize column names: strip whitespace, preserve original casing.
- Log a warning if an expected column is missing from any file (do not crash — gracefully degrade matching for that column).

**Uncertainty:** The exact column names in the user's Excel files may differ slightly from what is documented (e.g., extra spaces, different casing). Use case-insensitive column lookup with a fallback warning rather than a hard crash.

---

## Phase 6 — Fuzzy Matching

### Module: `pipeline/matching.py`

### Library: `rapidfuzz`

Use `rapidfuzz` for all fuzzy matching. It is significantly faster than `fuzzywuzzy` and does not require `python-Levenshtein` separately.

### Matching Strategy

Use a **composite scoring approach** rather than a single algorithm:

| Algorithm | Use case |
|---|---|
| `token_sort_ratio` | Names with reordered words (e.g. "ACME Corp Ltd" vs "Ltd Corp ACME") |
| `partial_ratio` | Short abbreviations or prefixes matching a longer full name |
| `WRatio` | General-purpose weighted ratio combining multiple strategies |

Final score = `max(token_sort_ratio, partial_ratio, WRatio)` for each candidate.

### Customer Matching

**Input:** extracted `sold_to.name` or `ship_to.name`

**Against:** `customerList` — search both `Name 1` and `Name 2` columns separately.

**Steps:**
1. Preprocess the query string: lowercase, strip common business suffixes (`Ltd`, `Pvt`, `Inc`, `Co`, `Corp`, `GmbH`, `S.A.`, `S.r.l.`, etc.) before matching, but preserve the original for output.
2. For each row in `customerList`, compute the composite score against both `Name 1` and `Name 2`. Take the higher of the two as the row's score.
3. Sort all rows by score descending.
4. Return top 3 results with their scores.
5. If the top score is below the configured threshold, return `[NO MATCH]` for all three slots.

**Output per match slot:**
```
{
  "customer_code": "...",
  "customer_name1": "...",
  "customer_name2": "...",
  "customer_country": "...",
  "customer_city": "...",
  "match_score": 87
}
```

### Material Matching

**Input:** extracted `material_description` and optionally `material_code`

**Against:** `materialList` — match against `Material Description` column.

**Steps:**
1. If `material_code` is present and not `[MISSING]`, attempt an exact lookup against the `Material` column first. If found, treat as score=100.
2. Otherwise, fuzzy match `material_description` against `Material Description` using the composite score.
3. Filter by `Language` column if the detected language of the description is known. If language detection is not implemented, do not filter.
4. Return top 3 results.

**Note on language:** `rapidfuzz` handles Unicode correctly, so Chinese, Japanese, and French characters will match appropriately at the character level. However, semantic similarity across languages is not supported — only surface-level text similarity. If a PO contains a Chinese description and the materialList contains English descriptions only, fuzzy matching will likely fail. Flag this scenario as `[NO MATCH]` and document the limitation clearly.

### Sales Org Matching

**Input:** extracted `manufacturer_name`

**Against:** `salesOrg` — match against `Name` column.

**Steps:**
1. Fuzzy match using composite score.
2. Return the single best match (top 1 is sufficient here since we need a single Sales Organization code to drive the salesArea lookup).
3. If below threshold, mark as `[NO MATCH]` and skip salesArea lookup.

### Sales Area Lookup

**Input:** `Sales Organization` code from salesOrg match result.

**Against:** `salesArea` — exact lookup on `Sales Organization` column.

**Steps:**
1. Filter `salesArea` DataFrame where `Sales Organization` equals the matched code (exact string match after stripping whitespace).
2. Return all matching rows (there may be multiple Distribution Channel / Division combinations).
3. Include all matching rows in the output.

**Uncertainty:** The spec does not clarify what to do with multiple salesArea rows for one Sales Organization. The safest approach: include all of them in the output, joined with a separator (e.g., pipe `|`), and document this behavior.

### Configurable Threshold

- Threshold is passed into all matching functions as a parameter.
- Default: 60.
- Overridable via `--threshold` CLI flag.
- The same threshold applies to all entity types (customer, material, salesOrg).

---

## Phase 7 — CSV Export

### Module: `pipeline/export.py`

### Output File Naming

- `{input_filename}_output.csv` saved into `--output` directory.
- If the input is a multi-page PDF, all pages go into the same CSV file (one row per page/PO).

### CSV Schema

Each row represents one extracted PO. Columns:

| Column | Source |
|---|---|
| `source_file` | Input filename |
| `page_index` | Page number (0-indexed) |
| `po_number` | Extracted |
| `issue_date` | Extracted |
| `sold_to_name` | Extracted |
| `sold_to_address` | Extracted |
| `sold_to_city` | Extracted |
| `sold_to_country` | Extracted |
| `sold_to_postal_code` | Extracted |
| `ship_to_name` | Extracted |
| `ship_to_address` | Extracted |
| `ship_to_city` | Extracted |
| `ship_to_country` | Extracted |
| `ship_to_postal_code` | Extracted |
| `manufacturer_name` | Extracted |
| `shipping_details` | Extracted |
| `sold_to_match_1_code` | Match result |
| `sold_to_match_1_name` | Match result |
| `sold_to_match_1_score` | Match result |
| `sold_to_match_2_code` | Match result |
| `sold_to_match_2_name` | Match result |
| `sold_to_match_2_score` | Match result |
| `sold_to_match_3_code` | Match result |
| `sold_to_match_3_name` | Match result |
| `sold_to_match_3_score` | Match result |
| `ship_to_match_1_code` | Match result |
| ... (same pattern) | |
| `sales_org_code` | salesOrg match |
| `sales_org_score` | salesOrg match |
| `distribution_channels` | salesArea lookup (pipe-joined) |
| `divisions` | salesArea lookup (pipe-joined) |
| `parse_error` | Boolean |
| `parse_error_detail` | String |

**Line items** are the awkward case for CSV flattening. Two options:

**Option A (recommended):** One row per line item. PO-level fields repeat on every row. Add a `line_item_index` column. This is the most analysis-friendly format.

**Option B:** One row per PO, with line item fields concatenated using a separator (e.g., `|`). Simpler but harder to query.

Recommend **Option A** and document the behavior.

Line item columns appended to the schema:
- `line_item_index`
- `line_item_material_description`
- `line_item_material_code`
- `line_item_quantity`
- `line_item_unit_price`
- `line_item_total`
- `material_match_1_code`, `material_match_1_description`, `material_match_1_score`
- `material_match_2_code`, `material_match_2_description`, `material_match_2_score`
- `material_match_3_code`, `material_match_3_description`, `material_match_3_score`

### CSV Encoding

Write with `encoding="utf-8-sig"` to ensure Excel opens multilingual content correctly (BOM prefix).

---

## Phase 8 — Logging and Verbose Audit Trail

### Module: `pipeline/audit.py`

### Standard Logging (always on)

Use Python's `logging` module. Log to stderr (not stdout, which is reserved for user-facing messages). Log levels:

- `INFO`: File processed, page count, output path.
- `WARNING`: Parse retry triggered, field missing, match below threshold, column not found in reference data.
- `ERROR`: File not readable, API failure after all retries, critical parse failure.

### Verbose Mode (`--verbose` flag)

When `--verbose` is set, additionally write a `.log` file alongside the CSV with per-page audit records. Each record includes:

```
=== PAGE 1 ===
Extracted PO Number: PO-20240115-003
Extracted Sold To: ACME TRADING PVT LTD
  -> Match 1: ACME TRADING LTD (code: C001, score: 91)
  -> Match 2: ACME EXPORTS PVT (code: C047, score: 78)
  -> Match 3: ACME GLOBAL CORP (code: C102, score: 65)
Extracted Line Item 1: "Stainless Steel Pipe 50mm"
  -> Material Match 1: Steel Pipe SS 50mm (code: MAT-4521, score: 88)
  -> Material Match 2: ...
...
```

This gives the user a human-readable trace of all extraction and matching decisions without requiring them to interpret the CSV columns.

---

## Phase 9 — Error Handling Strategy

| Failure Type | Behavior |
|---|---|
| File not found / unsupported extension | Immediate CLI error, exit code 1 |
| Gemini API key missing | Immediate CLI error with `.env` setup instructions |
| Gemini API HTTP 429 | Exponential backoff, 3 retries, then mark page as failed |
| Gemini API response not valid JSON | One retry with clarifying prompt; if still invalid, mark page as `parse_error=True` and continue |
| Reference Excel file missing | Warning logged; matching for that entity type returns `[NO MATCH]` for all documents |
| Reference Excel column missing | Warning logged per column; affected match columns return `[NO MATCH]` |
| PDF page renders as blank image | Skip page, log warning |
| Preprocessing failure (e.g., deskew crash) | Log warning, proceed with unprocessed image |
| Single line item extraction fails | Mark that item's fields as `[MISSING]`, do not fail the whole PO |

**Principle:** Never let a single page or line item failure crash the entire batch. Always continue and report failures in the output.

---

## Phase 10 — Data Flow Summary

```
CLI Input (file path, flags)
        |
        v
[ingestion.py]
  PDF → pages as PIL images
  Image → single PIL image
        |
        v
[preprocessing.py]
  Deskew → upscale → contrast → (optional binarize)
        |
        v
[extraction.py]
  Send image + prompt to Gemini API
  Parse JSON response
  Retry on failure
        |
        v
[normalization.py + schema.py]
  Validate and coerce to PurchaseOrder Pydantic model
  Normalize [MISSING] values
        |
        v
[matching.py]
  sold_to.name → customerList → top 3 matches
  ship_to.name → customerList → top 3 matches
  each line_item → materialList → top 3 matches
  manufacturer_name → salesOrg → best match → salesArea lookup
        |
        v
[export.py]
  Flatten to CSV rows (one per line item)
  Write UTF-8 BOM CSV to output dir
        |
        v
[audit.py] (if --verbose)
  Write .log file with per-page decision trace
```

---

## Phase 11 — Testing Strategy

### Unit Tests

| Test file | What it tests |
|---|---|
| `test_preprocessing.py` | Deskew on a rotated test image; upscaling; contrast normalization. Use small synthetic images. |
| `test_extraction.py` | Mock the Gemini API response; verify JSON parsing; verify retry logic on malformed response; verify `[MISSING]` handling. |
| `test_matching.py` | Customer name matching with known inputs and expected scores; material matching; salesOrg lookup; salesArea join; threshold enforcement; `[NO MATCH]` cases. |
| `test_export.py` | Verify CSV column count, row count per line item, UTF-8 BOM encoding, and `[MISSING]` values pass through correctly. |
| `test_normalization.py` | Verify Pydantic validation, `[MISSING]` coercion, whitespace stripping. |

### Integration Tests

- Provide 2-3 sample PO images/PDFs (redacted if necessary) as test fixtures.
- Run the full pipeline against each and assert that output CSV exists, has the expected number of rows, and that certain known fields match expected values.
- Do not run integration tests against the live Gemini API in CI. Use a recorded response fixture (VCR-style or a saved JSON file) for deterministic testing.

### Edge Case Tests

- Blank page in a multi-page PDF.
- PDF with a single page.
- Image file with extreme skew (45 degrees).
- PO with no line items.
- PO with 20+ line items.
- PO in Chinese with no English content.
- PO where sold-to and ship-to are the same entity.
- PO where no sold-to party exists.

---

## Implementation Phases — Suggested Order

| Phase | Deliverable | Risk |
|---|---|---|
| 1 | CLI scaffold, config, .env | Low |
| 2 | PDF/image ingestion, preprocessing | Medium (deskew tuning) |
| 3 | Gemini extraction, prompt, retry | High (prompt quality) |
| 4 | Normalization and Pydantic schema | Low |
| 5 | Reference data loader | Low |
| 6 | Fuzzy matching all entity types | Medium (threshold tuning) |
| 7 | CSV export | Low |
| 8 | Verbose logging and audit trail | Low |
| 9 | Integration tests | Medium |
| 10 | Edge case hardening | Ongoing |

---

## Known Limitations and Open Questions

1. **Cross-language matching:** If a PO contains Chinese text and `materialList` contains English descriptions only, fuzzy character-level matching will not find semantic equivalents. This is a fundamental limitation. Options: (a) accept the limitation and return `[NO MATCH]`, (b) add an optional translation step using Gemini before matching. This plan does not include translation; it should be a future enhancement only if the user confirms the need.

2. **Multiple salesArea rows per Sales Organization:** The plan returns all of them pipe-joined. If the business requires selecting a specific row, additional disambiguation logic is needed that is not described in the requirements.

3. **Handwritten POs:** Gemini's vision model handles handwriting, but accuracy depends on legibility. No additional OCR step (e.g., Google Cloud Vision OCR) is included. If Gemini underperforms on specific handwritten documents, a dedicated OCR pre-pass could be added as an optional pipeline stage.

4. **PO business flow disambiguation:** The extraction prompt instructs Gemini to distinguish sold-to vs ship-to as best it can, but for documents that contain three or more addresses without clear labels, disambiguation may be incorrect. The audit log will capture this ambiguity and allow manual review.

5. **Configurable business suffix list:** The list of suffixes to strip before customer matching (`Ltd`, `Pvt`, etc.) is hardcoded. If the reference data contains entries with these suffixes intact, stripping before matching may help. If the reference data already has them stripped, double-stripping is harmless. This should be validated against actual reference data before finalizing.

6. **Gemini model IDs:** As of this plan, `gemini-1.5-flash` is a valid model ID. Google may change or deprecate model IDs. The `--model` flag allows runtime override without code changes.

7. **Concurrency:** This plan processes pages sequentially. For large batch inputs or many-page PDFs, Gemini API calls could be parallelized using `concurrent.futures.ThreadPoolExecutor` with a configurable worker count. This is not included in the initial implementation but the architecture supports adding it later without structural changes.
