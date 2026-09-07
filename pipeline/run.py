"""Shared per-document processing loop used by both the CLI and the API.

Runs every page of a document through ingestion, preprocessing, extraction,
normalization, and matching. Blank pages are skipped; a page whose extraction
fails still yields a result (flagged via ``po.parse_error``) so one bad page
never drops the rest of the document.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from models.schema import PurchaseOrder
from pipeline import extraction, ingestion, matching, normalization, preprocessing
from pipeline.extraction import TokenUsage

logger = logging.getLogger(__name__)


@dataclass
class PageResult:
    po: PurchaseOrder
    matches: dict
    token_usage: TokenUsage = field(default_factory=TokenUsage)


def process_document(
    path: Path,
    client,
    model: str,
    reference: dict[str, pd.DataFrame],
    threshold: int,
) -> list[PageResult]:
    """Run the full pipeline over every page of ``path``; return one result per
    non-blank page (in page order)."""
    pages = ingestion.load_document(path)
    results: list[PageResult] = []

    for page in pages:
        page_label = f"{path.name} page {page.page_index + 1}/{len(pages)}"
        if preprocessing.is_blank(page.image):
            logger.warning("%s appears blank; skipping", page_label)
            continue

        image = preprocessing.preprocess(page.image, is_scanned=page.is_scanned)

        usage = TokenUsage()
        try:
            raw, usage = extraction.extract_page(client, image, model)
            po = normalization.normalize_extraction(raw, path.name, page.page_index)
        except extraction.ExtractionError as exc:
            logger.error("%s extraction failed: %s", page_label, exc)
            po = normalization.failed_extraction(path.name, page.page_index, str(exc))

        matches = matching.match_purchase_order(po, reference, threshold)
        results.append(PageResult(po=po, matches=matches, token_usage=usage))
        logger.info(
            "%s processed (%d line item(s)) — page tokens: %d prompt + %d output = %d total",
            page_label, len(po.line_items),
            usage.prompt_tokens, usage.output_tokens, usage.total_tokens,
        )

    doc_total = sum((r.token_usage for r in results), TokenUsage())
    logger.info(
        "=== %s: TOTAL Gemini usage across %d page(s): %d prompt + %d output = %d tokens ===",
        path.name, len(results), doc_total.prompt_tokens, doc_total.output_tokens, doc_total.total_tokens,
    )

    return results
