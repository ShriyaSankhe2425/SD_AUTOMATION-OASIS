"""File detection and routing: turn an input path into a list of page images.

PDFs are rendered page-by-page at high resolution via PyMuPDF; images are
loaded directly with Pillow. Each page carries an ``is_scanned`` hint used
later to decide whether binarization is safe (digital PDF renders are left
untouched).
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

import config

logger = logging.getLogger(__name__)

# Pages whose text layer has at least this many characters are treated as
# digital renders rather than scans.
_TEXT_LAYER_MIN_CHARS = 30


@dataclass
class PageImage:
    page_index: int
    image: Image.Image
    is_scanned: bool


def load_document(input_path: Path) -> list[PageImage]:
    """Load a PDF or image file into a list of PageImage objects."""
    suffix = input_path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(input_path)
    if suffix in {".jpg", ".jpeg", ".png"}:
        return _load_image(input_path)
    raise ValueError(f"Unsupported file extension: {suffix}")


def _load_pdf(pdf_path: Path) -> list[PageImage]:
    pages: list[PageImage] = []
    zoom = config.PDF_RENDER_DPI / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(pdf_path) as doc:
        logger.info("PDF opened: %s (%d page(s))", pdf_path.name, doc.page_count)
        for index, page in enumerate(doc):
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            has_text_layer = len(page.get_text().strip()) >= _TEXT_LAYER_MIN_CHARS
            pages.append(PageImage(index, image, is_scanned=not has_text_layer))
    return pages


def _load_image(image_path: Path) -> list[PageImage]:
    image = Image.open(image_path)
    image.load()
    if image.mode != "RGB":
        image = image.convert("RGB")
    logger.info("Image loaded: %s (%dx%d)", image_path.name, image.width, image.height)
    # Standalone image files are assumed to be photos/scans of documents.
    return [PageImage(0, image, is_scanned=True)]
