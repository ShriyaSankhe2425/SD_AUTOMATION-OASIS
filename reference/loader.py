"""Load and cache the four Excel reference workbooks.

All files are read once at startup as string DataFrames (preserving codes
like "0001"), whitespace-stripped, and NaN-filled with "". Filenames are
resolved case-insensitively (handles salesArea.XLSX vs salesArea.xlsx). A
missing file or column degrades that matcher to [NO MATCH] with a warning
instead of crashing the run.
"""

import logging
from pathlib import Path

import pandas as pd

import config

logger = logging.getLogger(__name__)

# Columns each workbook is expected to contain; absence is a warning only.
EXPECTED_COLUMNS = {
    "customerList": ["Customer", "Country", "Name 1", "Name 2", "City", "Postal Code"],
    "materialList": ["Material", "Language", "Material Description"],
    "salesOrg": ["Sales Organization", "Name"],
    "salesArea": ["Sales Organization", "Distribution Channel", "Division"],
}


def load_reference_data(data_dir: Path) -> dict[str, pd.DataFrame]:
    """Load every reference workbook; missing ones become empty DataFrames."""
    reference: dict[str, pd.DataFrame] = {}
    for key, filename in config.REFERENCE_FILES.items():
        path = _find_file(data_dir, filename)
        if path is None:
            logger.warning(
                "Reference file '%s' not found in %s; %s matching will return [NO MATCH]",
                filename, data_dir, key,
            )
            reference[key] = pd.DataFrame()
            continue
        df = pd.read_excel(path, dtype=str)
        df.columns = [str(col).strip() for col in df.columns]
        df = df.fillna("")
        for column in df.columns:
            df[column] = df[column].astype(str).str.strip()
        _warn_missing_columns(key, df)
        logger.info("Loaded %s: %d rows from %s", key, len(df), path.name)
        reference[key] = df
    return reference


def _find_file(data_dir: Path, filename: str) -> Path | None:
    """Case-insensitive lookup of a workbook in the data directory."""
    if not data_dir.is_dir():
        return None
    target = filename.lower()
    for candidate in data_dir.iterdir():
        if candidate.name.lower() == target:
            return candidate
    return None


def _warn_missing_columns(key: str, df: pd.DataFrame) -> None:
    present = {str(col).strip().lower() for col in df.columns}
    for expected in EXPECTED_COLUMNS.get(key, []):
        if expected.lower() not in present:
            logger.warning(
                "Reference file '%s' is missing expected column '%s'; "
                "matches depending on it will return [NO MATCH]",
                key, expected,
            )
