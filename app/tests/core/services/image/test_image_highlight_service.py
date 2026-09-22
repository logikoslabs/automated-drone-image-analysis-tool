"""
Comprehensive tests for ImageHighlightService.

Tests image highlighting and augmentation functionality.
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from core.services.image.ImageHighlightService import ImageHighlightService


@pytest.fixture
def image_highlight_service():
    """Fixture providing an ImageHighlightService instance."""
    return ImageHighlightService()


@pytest.fixture
def test_image():
    """Create a test image."""
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    img[50:150, 50:150] = [255, 255, 255]  # White square
    return img


def test_image_highlight_service_initialization(image_highlight_service):
    """Test ImageHighlightService initialization."""
    assert image_highlight_service is not None


def test_highlight_aois(image_highlight_service, test_image):
    """Test highlighting AOIs on an image."""
    aois = [
        {
            'center': (100, 100),
            'radius': 20,
            'area': 400
        }
    ]

    highlighted = ImageHighlightService.highlight_aoi_pixels(
        test_image,
        aois,
        highlight_color=(255, 0, 0)
    )

    assert highlighted.shape == test_image.shape
    assert highlighted.dtype == test_image.dtype


def test_apply_visibility_mask_hides_pixels_outside_range(test_image):
    """Visibility masks should black out pixels that are not visible."""
    visible_mask = np.zeros((200, 200), dtype=bool)
    visible_mask[75:125, 75:125] = True

    masked = ImageHighlightService.apply_visibility_mask(test_image, visible_mask)

    assert np.all(masked[0, 0] == 0)
    assert np.all(masked[100, 100] == test_image[100, 100])


def test_apply_boolean_mask_highlight_blends_highlight_color(test_image):
    """Boolean mask highlighting should tint only the selected pixels."""
    highlight_mask = np.zeros((200, 200), dtype=bool)
    highlight_mask[100, 100] = True

    highlighted = ImageHighlightService.apply_boolean_mask_highlight(
        test_image,
        highlight_mask,
        highlight_color=(0, 255, 255),
        alpha=0.5
    )

    assert np.array_equal(highlighted[0, 0], test_image[0, 0])
    assert not np.array_equal(highlighted[100, 100], test_image[100, 100])


def test_apply_mask_highlight_missing_path_returns_original(test_image):
    out = ImageHighlightService.apply_mask_highlight(test_image, "")
    assert out is test_image
    out = ImageHighlightService.apply_mask_highlight(test_image, "/no/such/mask.png")
    assert out is test_image


def test_apply_mask_highlight_png(tmp_path, test_image):
    import cv2
    mask = np.zeros((200, 200), dtype=np.uint8)
    mask[80:120, 80:120] = 255
    path = tmp_path / "mask.png"
    cv2.imwrite(str(path), mask)
    out = ImageHighlightService.apply_mask_highlight(test_image, str(path), (255, 0, 0))
    assert out.shape == test_image.shape
    assert not np.array_equal(out[100, 100], test_image[100, 100])


def test_apply_mask_highlight_resizes_and_accepts_tiff(tmp_path, test_image):
    import tifffile
    mask = np.zeros((50, 50), dtype=np.uint8)
    mask[10:40, 10:40] = 255
    path = tmp_path / "mask.tif"
    tifffile.imwrite(str(path), mask)
    out = ImageHighlightService.apply_mask_highlight(test_image, str(path))
    assert out.shape == test_image.shape


def test_apply_mask_highlight_returns_original_when_imread_fails(test_image):
    with patch("cv2.imread", return_value=None):
        out = ImageHighlightService.apply_mask_highlight(test_image, "x.png")
    assert out is test_image
