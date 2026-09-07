"""Image normalization ahead of vision extraction.

Steps (each toggleable in config.py, each individually fault-tolerant —
a failing step logs a warning and passes the image through unchanged):

1. Deskew via minAreaRect over text pixels, gated to plausible angles.
2. Upscale with Lanczos when the image is below the minimum resolution.
3. Grayscale + CLAHE contrast normalization for uneven scan lighting.
4. Optional adaptive binarization, applied only to scanned pages.
5. Return an RGB PIL image for the Gemini API.
"""

import logging

import cv2
import numpy as np
from PIL import Image

import config

logger = logging.getLogger(__name__)


def is_blank(image: Image.Image) -> bool:
    """A page with almost no pixel variance is treated as blank."""
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    return float(gray.std()) < config.BLANK_PAGE_STD_THRESHOLD


def preprocess(image: Image.Image, is_scanned: bool = True) -> Image.Image:
    """Run the full preprocessing chain and return an RGB PIL image."""
    if config.ENABLE_DESKEW:
        image = _safe(_deskew, image, "deskew")
    if config.ENABLE_UPSCALE:
        image = _safe(_upscale, image, "upscale")
    if config.ENABLE_CONTRAST:
        image = _safe(_normalize_contrast, image, "contrast normalization")
    if config.ENABLE_BINARIZATION and is_scanned:
        image = _safe(_binarize, image, "binarization")
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image


def _safe(step, image: Image.Image, step_name: str) -> Image.Image:
    try:
        return step(image)
    except Exception as exc:  # never let one step sink the page
        logger.warning("Preprocessing step '%s' failed (%s); using unprocessed image", step_name, exc)
        return image


def _deskew(image: Image.Image) -> Image.Image:
    gray = np.asarray(image.convert("L"))
    # Text pixels are dark on light backgrounds; invert so they are foreground.
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(binary)
    if coords is None or len(coords) < 50:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    # Normalize to [-45, 45]: OpenCV reports axis-aligned rects as 0, 90,
    # or -90 depending on version/orientation.
    if angle > 45:
        angle -= 90
    elif angle < -45:
        angle += 90

    if not (config.DESKEW_MIN_ANGLE <= abs(angle) < config.DESKEW_MAX_ANGLE):
        return image

    logger.info("Deskewing by %.2f degrees", angle)
    rgb = np.asarray(image.convert("RGB"))
    height, width = rgb.shape[:2]
    rotation = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    rotated = cv2.warpAffine(
        rgb,
        rotation,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )
    return Image.fromarray(rotated)


def _upscale(image: Image.Image) -> Image.Image:
    shortest = min(image.width, image.height)
    if shortest >= config.MIN_DIMENSION_PX:
        return image
    scale = config.MIN_DIMENSION_PX / shortest
    new_size = (round(image.width * scale), round(image.height * scale))
    logger.info("Upscaling %dx%d -> %dx%d", image.width, image.height, *new_size)
    return image.resize(new_size, Image.LANCZOS)


def _normalize_contrast(image: Image.Image) -> Image.Image:
    gray = np.asarray(image.convert("L"))
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    equalized = clahe.apply(gray)
    return Image.fromarray(equalized).convert("RGB")


def _binarize(image: Image.Image) -> Image.Image:
    gray = np.asarray(image.convert("L"))
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, blockSize=31, C=15
    )
    return Image.fromarray(binary).convert("RGB")
