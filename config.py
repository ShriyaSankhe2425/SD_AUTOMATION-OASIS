"""Central configuration: environment loading, defaults, and pipeline toggles."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "jp_data"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# The --model CLI flag accepts any string and passes it straight to the API,
# so new Gemini model IDs work without code changes.
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
DEFAULT_THRESHOLD = int(os.getenv("MATCH_THRESHOLD", "60"))

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

# Sentinel values used throughout the pipeline and in the CSV output.
MISSING = "[MISSING]"
NO_MATCH = "[NO MATCH]"

# --- Ingestion ---
PDF_RENDER_DPI = 300

# --- Preprocessing toggles (disable individually if a step causes
# regressions on a specific document type) ---
ENABLE_DESKEW = True
ENABLE_UPSCALE = True
ENABLE_CONTRAST = True
# Binarization destroys stroke texture on handwriting and color cues on
# digital renders, so it is off by default. When enabled it is only applied
# to pages detected as scans (never to digital PDF renders).
ENABLE_BINARIZATION = False

# Only rotate when the detected skew is meaningful but plausible.
DESKEW_MIN_ANGLE = 1.0
DESKEW_MAX_ANGLE = 45.0

# Upscale so the shorter side is at least this many pixels.
MIN_DIMENSION_PX = 1000

# Pages whose grayscale standard deviation falls below this are treated as
# blank and skipped.
BLANK_PAGE_STD_THRESHOLD = 3.0

# --- Gemini API ---
API_TIMEOUT_SECONDS = 60
MAX_API_RETRIES = 3
RETRY_BACKOFF_SECONDS = (2, 4, 8)
RETRYABLE_STATUS_CODES = {429, 500, 503}

# --- Matching ---
# Business suffixes stripped from the query string before customer matching.
# The original extracted name is always preserved for output.
BUSINESS_SUFFIXES = (
    "ltd",
    "ltd.",
    "limited",
    "pvt",
    "pvt.",
    "private",
    "inc",
    "inc.",
    "incorporated",
    "co",
    "co.",
    "company",
    "corp",
    "corp.",
    "corporation",
    "gmbh",
    "s.a.",
    "sa",
    "s.r.l.",
    "srl",
    "s.p.a.",
    "spa",
    "llc",
    "llp",
    "plc",
    "ag",
    "bv",
    "b.v.",
    "nv",
    "n.v.",
    "kk",
    "k.k.",
    "oy",
    "ab",
    "pte",
    "pty",
)

# Reference workbook base names (looked up case-insensitively, .xlsx/.XLSX).
REFERENCE_FILES = {
    "customerList": "customerList.xlsx",
    "materialList": "materialList.xlsx",
    "salesOrg": "salesOrg.xlsx",
    "salesArea": "salesArea.xlsx",
}
