import pytest
import piexif
import utm
from unittest.mock import patch, MagicMock
from PIL import Image, UnidentifiedImageError
from app.helpers.LocationInfo import LocationInfo


@pytest.fixture
def example_image_path(testData):
    """Absolute path, via the shared testData fixture - a hardcoded
    "app/tests/data/..." relative string only resolves when pytest runs from
    the repo root."""
    return testData['EXIF_Input_Path']


@pytest.fixture
def example_gps_data():
    return {
        'GPS': {
            piexif.GPSIFD.GPSLatitude: [(37, 1), (48, 1), (20, 1)],
            piexif.GPSIFD.GPSLatitudeRef: b'N',
            piexif.GPSIFD.GPSLongitude: [(122, 1), (25, 1), (20, 1)],
            piexif.GPSIFD.GPSLongitudeRef: b'W'
        }
    }


def test_get_gps_jpg(example_image_path, example_gps_data):
    # Simulate a valid JPEG file via PIL
    with patch("PIL.Image.open") as mock_open, \
            patch("piexif.load", return_value=example_gps_data):

        mock_img = MagicMock()
        mock_img.format = "JPEG"
        mock_open.return_value.__enter__.return_value = mock_img

        result = LocationInfo.get_gps(full_path=example_image_path)
        assert result == {'latitude': 37.805556, 'longitude': -122.422222}


def test_get_gps_non_jpg(example_image_path):
    # Simulate a non-JPEG image (e.g., PNG)
    with patch("PIL.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.format = "PNG"
        mock_open.return_value.__enter__.return_value = mock_img

        result = LocationInfo.get_gps(full_path=example_image_path)
        assert result == {}


def test_convert_degrees_to_utm():
    lat, lng = 37.805556, -122.422222
    result = LocationInfo.convert_degrees_to_utm(lat, lng)
    utm_coordinates = utm.from_latlon(lat, lng)
    expected = {
        'easting': utm_coordinates[0],
        'northing': utm_coordinates[1],
        'zone_number': utm_coordinates[2],
        'zone_letter': utm_coordinates[3]
    }
    assert result['easting'] == pytest.approx(expected['easting'], rel=1e-5)
    assert result['northing'] == pytest.approx(expected['northing'], rel=1e-5)
    assert result['zone_number'] == expected['zone_number']
    assert result['zone_letter'] == expected['zone_letter']


def test_convert_decimal_to_dms():
    lat, lng = 37.805556, -122.422222
    result = LocationInfo.convert_decimal_to_dms(lat, lng)
    expected = {
        'latitude': {'degrees': 37, 'minutes': 48, 'seconds': 20.0, 'reference': 'N'},
        'longitude': {'degrees': 122, 'minutes': 25, 'seconds': 20.0, 'reference': 'W'}
    }
    assert result == expected


def test__convert_to_degrees():
    value = [(37, 1), (48, 1), (20, 1)]
    result = LocationInfo._convert_to_degrees(value)
    assert result == pytest.approx(37.805556, rel=1e-6)


def _gps_exif(lat_dms, lat_ref, lon_dms, lon_ref):
    return {
        'GPS': {
            piexif.GPSIFD.GPSLatitude: lat_dms,
            piexif.GPSIFD.GPSLatitudeRef: lat_ref,
            piexif.GPSIFD.GPSLongitude: lon_dms,
            piexif.GPSIFD.GPSLongitudeRef: lon_ref,
        }
    }


def test_get_gps_from_exif_data_north_east():
    """N/E refs must stay positive — the happy-path hemisphere."""
    exif = _gps_exif(
        [(37, 1), (48, 1), (20, 1)], b'N',
        [(122, 1), (25, 1), (20, 1)], b'E',
    )
    result = LocationInfo.get_gps(exif_data=exif)
    assert result['latitude'] == pytest.approx(37.805556, abs=1e-6)
    assert result['longitude'] == pytest.approx(122.422222, abs=1e-6)


def test_get_gps_from_exif_data_south_west():
    """S/W refs must flip sign — silent hemisphere bugs place AOIs oceans away."""
    exif = _gps_exif(
        [(33, 1), (52, 1), (12, 1)], b'S',
        [(151, 1), (12, 1), (36, 1)], b'W',
    )
    result = LocationInfo.get_gps(exif_data=exif)
    assert result['latitude'] < 0
    assert result['longitude'] < 0
    assert result['latitude'] == pytest.approx(-33.870000, abs=1e-5)
    assert result['longitude'] == pytest.approx(-151.210000, abs=1e-5)


def test_get_gps_missing_keys_returns_empty():
    assert LocationInfo.get_gps(exif_data={'GPS': {}}) == {}
    assert LocationInfo.get_gps(exif_data={}) == {}
    # Latitude present but longitude missing → KeyError path.
    partial = {
        'GPS': {
            piexif.GPSIFD.GPSLatitude: [(1, 1), (0, 1), (0, 1)],
            piexif.GPSIFD.GPSLatitudeRef: b'N',
        }
    }
    assert LocationInfo.get_gps(exif_data=partial) == {}


def test_get_gps_unreadable_or_non_jpeg_returns_empty(tmp_path):
    bad = tmp_path / "corrupt.jpg"
    bad.write_bytes(b"not-an-image")
    assert LocationInfo.get_gps(full_path=str(bad)) == {}

    with patch("PIL.Image.open") as mock_open:
        mock_img = MagicMock()
        mock_img.format = "PNG"
        mock_open.return_value.__enter__.return_value = mock_img
        assert LocationInfo.get_gps(full_path=str(tmp_path / "x.png")) == {}


def test_format_coordinates_covers_common_export_styles():
    lat, lon = -33.87, 151.21
    assert "33" in LocationInfo.format_coordinates(lat, lon, 'Decimal Degrees')
    dms = LocationInfo.format_coordinates(lat, lon, 'Degrees Minutes Seconds')
    assert 'S' in dms and 'E' in dms
    ddm = LocationInfo.format_coordinates(lat, lon, 'Degrees Decimal Minutes')
    assert 'S' in ddm and 'E' in ddm
    assert LocationInfo.format_coordinates(lat, lon, 'Unknown Style').startswith("-33")
