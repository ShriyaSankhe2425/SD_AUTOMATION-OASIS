import numpy as np
from PIL import Image, ImageDraw

from pipeline.preprocessing import _deskew, _normalize_contrast, _upscale, is_blank, preprocess


def _document_image(width=800, height=600):
    """Synthetic 'document': white page with horizontal black text bars."""
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for y in range(80, height - 80, 40):
        draw.rectangle([60, y, width - 60, y + 12], fill="black")
    return image


def test_is_blank():
    assert is_blank(Image.new("RGB", (200, 200), "white"))
    assert not is_blank(_document_image())


def test_upscale_small_image():
    small = Image.new("RGB", (300, 200), "white")
    upscaled = _upscale(small)
    assert min(upscaled.size) >= 1000
    # Aspect ratio preserved.
    assert abs(upscaled.width / upscaled.height - 1.5) < 0.01


def test_upscale_leaves_large_image_alone():
    large = Image.new("RGB", (2000, 1500), "white")
    assert _upscale(large).size == (2000, 1500)


def test_deskew_straightens_rotated_document():
    def detected_angle(img):
        import cv2
        gray = np.asarray(img.convert("L"))
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = cv2.findNonZero(binary)
        angle = cv2.minAreaRect(coords)[-1]
        if angle > 45:
            angle -= 90
        elif angle < -45:
            angle += 90
        return angle

    rotated = _document_image().rotate(5, expand=True, fillcolor="white")
    assert abs(detected_angle(rotated)) > 1
    straightened = _deskew(rotated)
    assert abs(detected_angle(straightened)) < 1


def test_deskew_skips_tiny_angles():
    document = _document_image()
    result = _deskew(document)
    assert result.size == document.size


def test_contrast_normalization_preserves_size():
    image = _document_image()
    result = _normalize_contrast(image)
    assert result.size == image.size
    assert result.mode == "RGB"


def test_preprocess_end_to_end_returns_rgb():
    result = preprocess(_document_image(), is_scanned=True)
    assert result.mode == "RGB"
    assert min(result.size) >= 1000  # upscaling applied
