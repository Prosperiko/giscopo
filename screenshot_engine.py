import math
import os
import re
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright


class ScreenshotEngineError(RuntimeError):
    pass


def _parse_location(location: str) -> tuple[float, float]:
    coord_pattern = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
    match = coord_pattern.match(location)
    if match:
        lat, lng = float(match.group(1)), float(match.group(2))
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ScreenshotEngineError("Coordinates out of valid range")
        return lat, lng

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": location, "format": "json", "limit": 1},
            headers={"User-Agent": "giscopo/1.0"},
            timeout=20,
        )
        response.raise_for_status()
        items = response.json()
        if not items:
            raise ScreenshotEngineError("Unable to resolve location")
        return float(items[0]["lat"]), float(items[0]["lon"])
    except requests.RequestException as exc:
        raise ScreenshotEngineError("Unable to geocode location") from exc


def _download_mapbox_image(lat: float, lng: float, out_path: str) -> bool:
    token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
    if not token:
        return False

    url = (
        "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/"
        f"pin-s+ff0000({lng},{lat})/{lng},{lat},15/1280x720?access_token={token}"
    )
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        Path(out_path).write_bytes(response.content)
        return True
    except requests.RequestException:
        return False


def _capture_with_playwright(lat: float, lng: float, out_path: str) -> None:
    map_url = f"https://www.google.com/maps/@{lat},{lng},18z/data=!3m1!1e3"

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(map_url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(3000)
            page.screenshot(path=out_path, full_page=False)
            browser.close()
    except Exception as exc:
        raise ScreenshotEngineError("Playwright satellite capture failed") from exc


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]:
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _compose_qgis_mock(satellite_path: str, qgis_path: str, lat: float, lng: float, label: str) -> None:
    canvas = Image.new("RGB", (1366, 768), "#2B2F36")
    draw = ImageDraw.Draw(canvas)

    draw.rectangle((0, 0, 1366, 34), fill="#3B4048")
    draw.text((16, 9), "QGIS 3.34 - Academic GIS Workspace", fill="#EDEFF2", font=_load_font(14))

    draw.rectangle((0, 34, 280, 768), fill="#1F2328")
    draw.text((12, 46), "Layers", fill="#F0F3F6", font=_load_font(16))
    layer_lines = [
        "☑ Satellite Imagery",
        "☑ Administrative Boundary",
        f"☑ AOI - {label[:28]}",
        "☐ Road Network",
        "☐ Drainage",
    ]
    y = 80
    for line in layer_lines:
        draw.text((16, y), line, fill="#D4D8DD", font=_load_font(14))
        y += 28

    draw.rectangle((280, 34, 1366, 740), fill="#101418")

    satellite = Image.open(satellite_path).convert("RGB").resize((1030, 650))
    canvas.paste(satellite, (308, 62))

    draw.rectangle((0, 740, 1366, 768), fill="#3B4048")
    coord_text = f"EPSG:4326 | Lat: {lat:.6f}  Lon: {lng:.6f} | Scale 1:{int(math.pow(2, 15)):,}"
    draw.text((16, 747), coord_text, fill="#EDEFF2", font=_load_font(13))

    canvas.save(qgis_path, format="PNG", optimize=True)


def generate_report_images(location: str, output_dir: str) -> dict[str, str]:
    lat, lng = _parse_location(location)

    satellite_path = str(Path(output_dir) / "satellite.png")
    qgis_path = str(Path(output_dir) / "qgis_mock.png")

    mapbox_ok = _download_mapbox_image(lat, lng, satellite_path)
    if not mapbox_ok:
        _capture_with_playwright(lat, lng, satellite_path)

    _compose_qgis_mock(satellite_path, qgis_path, lat, lng, location)
    return {"satellite": satellite_path, "qgis": qgis_path, "latitude": f"{lat:.6f}", "longitude": f"{lng:.6f}"}
