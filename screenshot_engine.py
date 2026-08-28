import math
import os
import re
import urllib.parse
import uuid
import io
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from dotenv import load_dotenv
import random
import base64

import time


import certifi
import os
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()




load_dotenv(override=True)

class ScreenshotEngineError(RuntimeError):
    pass

# Do not delete this man JIC it doesn't work
# def _parse_location(location: str) -> tuple[float, float]:
#     # 1. Check if the user just pasted raw coordinates (lat, lng)
#     coord_pattern = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
#     match = coord_pattern.match(location)
#     if match:
#         lat, lng = float(match.group(1)), float(match.group(2))
#         if not (-90 <= lat <= 90 and -180 <= lng <= 180):
#             raise ScreenshotEngineError("Coordinates out of valid range")
#         return lat, lng

#     search_query = location
#     if "nigeria" not in search_query.lower():
#         search_query = f"{location}, Nigeria"

#     # 2. OpenStreetMap (Nominatim) Search
#     # OSM is mapped by locals and knows exactly where Nigerian universities are!
#     try:
#         response = requests.get(
#             "https://nominatim.openstreetmap.org/search",
#             params={"q": search_query, "format": "json", "limit": 1},
#             headers={"User-Agent": "giscopo-academic-app/1.0"},
#             timeout=15,
#         )
#         response.raise_for_status()
#         data = response.json()
#         if data:
#             return float(data[0]["lat"]), float(data[0]["lon"])
#     except Exception:
#         pass # If OSM fails, seamlessly fall back to Mapbox

#     # 3. FALLBACK: Mapbox Search
#     token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
#     if not token:
#         raise ScreenshotEngineError("Missing Mapbox token in .env file")

#     try:
#         encoded_query = urllib.parse.quote(search_query)
#         url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_query}.json"
        
#         response = requests.get(
#             url,
#             params={"access_token": token, "limit": 1, "country": "ng"},
#             timeout=15,
#         )
#         response.raise_for_status()
#         data = response.json()
        
#         if data.get("features"):
#             lng, lat = data["features"][0]["center"]
#             return float(lat), float(lng)
            
#     except requests.RequestException:
#         pass
        
#     raise ScreenshotEngineError(f"Unable to resolve location: {location}")



# def _parse_location(coordinates: str) -> tuple[float, float]:
#     # 1. Raw coordinates bypass everything
#     coord_pattern = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
#     match = coord_pattern.match(coordinates)
#     if match:
#         lat, lng = float(match.group(1)), float(match.group(2))
#         if not (-90 <= lat <= 90 and -180 <= lng <= 180):
#             raise ScreenshotEngineError("Coordinates out of valid range")
#         return lat, lng

#     # 2. KNOWN LOCATIONS fast-path (never fails, instant, exact)
#     # Add common UNIBEN spots here to skip geocoding entirely
#     known = {
#         "faculty of engineering, university of benin": (6.401852, 5.615612),
#         "faculty of engineering, uniben": (6.401852, 5.615612),
#         "uniben": (6.401852, 5.615612),
#         "university of benin": (6.401852, 5.615612),
#         "main gate, uniben": (6.397500, 5.623000),
#         "computer science, uniben": (6.403500, 5.618000),
#     }
#     lookup = coordinates.lower().strip().rstrip(",").rstrip(".")
#     if lookup in known:
#         return known[lookup]

#     # 3. OpenStreetMap with Nigeria restriction + Benin City bias
#     search_query = coordinates
#     if "nigeria" not in search_query.lower():
#         search_query = f"{coordinates}, Nigeria"

#     try:
#         response = requests.get(
#             "https://nominatim.openstreetmap.org/search",
#             params={
#                 "q": search_query,
#                 "format": "json",
#                 "limit": 1,
#                 "countrycodes": "ng",           # <-- CRITICAL: lock to Nigeria only
#                 "accept-language": "en",
#                 "addressdetails": 1,
#                 # Bias to Benin City area (left, top, right, bottom)
#                 "viewbox": "5.50,6.30,5.80,6.50",
#                 "bounded": 0,  # 0 = bias, 1 = strict. Use bias so non-Benin queries still work.
#             },
#             headers={"User-Agent": "giscopo-academic-app/1.0"},
#             timeout=15,
#         )
#         response.raise_for_status()
#         data = response.json()
#         if data:
#             lat = float(data[0]["lat"])
#             lng = float(data[0]["lon"])
            
#             # VALIDATION: if user mentioned Benin/UNIBEN, result MUST be near Benin City
#             if any(k in coordinates.lower() for k in ["benin", "uniben"]):
#                 # Benin City is roughly lat 6.3-6.5, lng 5.5-5.8
#                 if not (6.2 <= lat <= 6.6 and 5.4 <= lng <= 5.9):
#                     print(f"  ⚠️  OSM returned suspicious coords ({lat}, {lng}) for Benin query. Falling back...")
#                     raise ScreenshotEngineError("OSM result outside Benin City")
            
#             return lat, lng
#     except ScreenshotEngineError:
#         raise  # Re-raise our own validation errors
#     except Exception as e:
#         print(f"  ⚠️  OSM failed: {e}")

#     # 4. FALLBACK: Mapbox (also restricted to Nigeria)
#     token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
#     if not token:
#         raise ScreenshotEngineError("Missing Mapbox token in .env file")

#     try:
#         encoded_query = urllib.parse.quote(search_query)
#         url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_query}.json"
        
#         response = requests.get(
#             url,
#             params={"access_token": token, "limit": 1, "country": "ng"},
#             timeout=15,
#         )
#         response.raise_for_status()
#         data = response.json()
        
#         if data.get("features"):
#             lng, lat = data["features"][0]["center"]
#             return float(lat), float(lng)
            
#     except requests.RequestException as e:
#         print(f"  ⚠️  Mapbox failed: {e}")
        
#     raise ScreenshotEngineError(f"Unable to resolve coordinates: {location}")


def _parse_location(location: str) -> tuple[float, float]:
    # 1. Raw coordinates just to bypass everything
    coord_pattern = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
    match = coord_pattern.match(location)
    if match:
        lat, lng = float(match.group(1)), float(match.group(2))
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ScreenshotEngineError("Coordinates out of valid range")
        return lat, lng

    # 2. KNOWN LOCATIONS — exact coordinates, zero API calls, never fails (OGA standby)
    # Add every common location your users search for here
    known = {
        # UNIBEN
        "faculty of engineering, university of benin": (6.401852, 5.615612),
        "faculty of engineering, uniben": (6.401852, 5.615612),
        "uniben": (6.401852, 5.615612),
        "university of benin": (6.401852, 5.615612),
        "main gate, uniben": (6.397500, 5.623000),
        "computer science, uniben": (6.403500, 5.618000),
        "library, uniben": (6.400000, 5.620000),
        "uniben gym": (6.404000, 5.617000),
        "akindeko auditorium, uniben": (6.398500, 5.614000),
        
        # Benin City general
        "ring road, benin city": (6.335000, 5.603000),
        "ring road benin": (6.335000, 5.603000),
        "benin city": (6.335000, 5.603000),
        "benin": (6.335000, 5.603000),
        "kings square, benin city": (6.335500, 5.603500),
        "sapele road, benin city": (6.340000, 5.580000),
        "airport road, benin city": (6.320000, 5.620000),
        "ugbowo, benin city": (6.395000, 5.630000),
        "ekewan road, benin city": (6.330000, 5.610000),
    }
    
    lookup = location.lower().strip().rstrip(",").rstrip(".")
    # Also try without "nigeria" suffix if user added it
    lookup_clean = lookup.replace(", nigeria", "").replace(",nigeria", "")
    
    if lookup in known:
        return known[lookup]
    if lookup_clean in known:
        return known[lookup_clean]

    # 3. OpenStreetMap with STRICT validation
    search_query = location
    if "nigeria" not in search_query.lower():
        search_query = f"{location}, Nigeria"

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": search_query,
                "format": "json",
                "limit": 1,
                "countrycodes": "ng",  # Lock to Nigeria
                "accept-language": "en",
            },
            headers={"User-Agent": "giscopo-academic-app/1.0"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if data:
            lat = float(data[0]["lat"])
            lng = float(data[0]["lon"])
            
            # STRICT VALIDATION: If query mentions Benin/Uniben, coords MUST be near Benin City
            is_benin_query = any(k in location.lower() for k in ["benin", "uniben", "ugbowo", "ekewan", "sapele road", "airport road"])
            if is_benin_query:
                # Benin City is roughly lat 6.2-6.6, lng 5.4-5.9
                if not (6.2 <= lat <= 6.6 and 5.4 <= lng <= 5.9):
                    print(f"  ⚠️  OSM returned WRONG coords ({lat}, {lng}) for Benin query. Forcing fallback...")
                    # Force known Benin City center instead of failing
                    return (6.335000, 5.603000)
            
            return lat, lng
    except Exception as e:
        print(f"  ⚠️  OSM failed: {e}")

    # 4. FALLBACK: Mapbox
    token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
    if not token:
        raise ScreenshotEngineError("Missing Mapbox token in .env file")

    try:
        encoded_query = urllib.parse.quote(search_query)
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_query}.json"
        response = requests.get(
            url,
            params={"access_token": token, "limit": 1, "country": "ng"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("features"):
            lng, lat = data["features"][0]["center"]
            return float(lat), float(lng)
    except Exception as e:
        print(f"  ⚠️  Mapbox failed: {e}")
        
    raise ScreenshotEngineError(f"Unable to resolve location: {location}")





import ee
import requests
import io
from PIL import Image

def init_earth_engine():
    # If using a service account, you should authenticate here.
    # For local testing, just run `earthengine authenticate` in my  terminal first.
    try:
        ee.Initialize()
    except Exception as e:
        print(f"Failed to initialize Earth Engine. Did you authenticate? Error: {e}")
        return False
    return True





import math
import random
from io import BytesIO


def _deg2tile(lat_deg: float, lon_deg: float, zoom: int) -> tuple[int, int]:
    """Convert lat/lng to tile x,y at a given zoom."""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


# def _capture_google_earth(
#     lat: float, 
#     lng: float, 
#     out_path: str, 
#     zoom: int = 18, 
#     grid_size: int = 4
# ) -> bool:
#     """
#     Fetches Google Satellite tiles and stitches them into a high-res image.
#     No labels, no icons, no UI — pure satellite imagery exactly like Google Earth web.
    
#     Args:
#         lat, lng: Center coordinates
#         out_path: Where to save the PNG
#         zoom: Zoom level (17-20 is good for buildings). 18 = ~0.6m/pixel
#         grid_size: How many tiles across/down (e.g., 4 = 4x4 grid = 1024x1024px)
#     """
#     tile_size = 256
#     center_x, center_y = _deg2tile(lat, lng, zoom)
    
#     offset = grid_size // 2
#     min_x, max_x = center_x - offset, center_x + offset
#     min_y, max_y = center_y - offset, center_y + offset
    
#     canvas_width = (max_x - min_x + 1) * tile_size
#     canvas_height = (max_y - min_y + 1) * tile_size
#     canvas = Image.new("RGB", (canvas_width, canvas_height))
    
#     headers = {
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
#         "Referer": "https://www.google.com/",
#     }
    
#     success_count = 0
#     total_tiles = 0
    
#     for x in range(min_x, max_x + 1):
#         for y in range(min_y, max_y + 1):
#             total_tiles += 1
#             # Google load-balances across these subdomains
#             server = random.choice(["mt0", "mt1", "mt2", "mt3"])
#             # lyrs=s = satellite only (no labels, no roads, no POIs)
#             url = f"https://{server}.google.com/vt/lyrs=s&x={x}&y={y}&z={zoom}"
            
#             try:
#                 response = requests.get(url, headers=headers, timeout=15)
#                 response.raise_for_status()
#                 tile = Image.open(BytesIO(response.content)).convert("RGB")
                
#                 px = (x - min_x) * tile_size
#                 py = (y - min_y) * tile_size
#                 canvas.paste(tile, (px, py))
#                 success_count += 1
                
#             except Exception as e:
#                 # Grey placeholder for failed tiles so the image isn't broken
#                 canvas.paste(
#                     (200, 200, 200),
#                     (
#                         (x - min_x) * tile_size,
#                         (y - min_y) * tile_size,
#                         (x - min_x + 1) * tile_size,
#                         (y - min_y + 1) * tile_size,
#                     ),
#                 )
#                 print(f"  ⚠️  Tile {x},{y} failed: {e}")
    
#     if success_count == 0:
#         print("All tiles failed — check your internet connection.")
#         return False
    
#     # Optional: crop to the exact center area if grid is large
#     # This keeps the file size reasonable for PDF embedding
#     if grid_size > 3:
#         left = tile_size
#         top = tile_size
#         right = canvas_width - tile_size
#         bottom = canvas_height - tile_size
#         canvas = canvas.crop((left, top, right, bottom))
    
#     canvas.save(out_path, format="PNG", optimize=True)
#     print(f"Saved satellite image: {out_path} ({canvas.size[0]}x{canvas.size[1]} px, {success_count}/{total_tiles} tiles)")
#     return True


def _capture_google_earth(lat: float, lng: float, out_path: str, zoom: int = 18, grid_size: int = 4) -> bool:
    tile_size = 256
    center_x, center_y = _deg2tile(lat, lng, zoom)
    offset = grid_size // 2
    min_x, max_x = center_x - offset, center_x + offset
    min_y, max_y = center_y - offset, center_y + offset
    
    canvas_width = (max_x - min_x + 1) * tile_size
    canvas_height = (max_y - min_y + 1) * tile_size
    canvas = Image.new("RGB", (canvas_width, canvas_height))
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Referer": "https://www.google.com/",
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    }
    
    success_count = 0
    total_tiles = (max_x - min_x + 1) * (max_y - min_y + 1)
    
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            server = random.choice(["mt0", "mt1", "mt2", "mt3"])
            url = f"https://{server}.google.com/vt/lyrs=s&x={x}&y={y}&z={zoom}"
            
            # Retry failed tiles up to 3 times
            tile_img = None
            for attempt in range(3):
                try:
                    response = requests.get(url, headers=headers, timeout=15)
                    response.raise_for_status()
                    tile_img = Image.open(BytesIO(response.content)).convert("RGB")
                    break  # Success, stop retrying
                except Exception as e:
                    if attempt < 2:
                        time.sleep(0.5 * (attempt + 1))  # 0.5s, 1s
                    else:
                        print(f"  ⚠️  Tile {x},{y} failed after 3 attempts: {e}")
            
            px = (x - min_x) * tile_size
            py = (y - min_y) * tile_size
            
            if tile_img:
                canvas.paste(tile_img, (px, py))
                success_count += 1
            else:
                # Grey placeholder for failed tiles
                canvas.paste((200, 200, 200), (px, py, px + tile_size, py + tile_size))
    
    if success_count == 0:
        print("All tiles failed — check your internet connection.")
        return False
    
    # Optional center crop
    if grid_size > 3:
        margin = tile_size
        canvas = canvas.crop((margin, margin, canvas_width - margin, canvas_height - margin))
    
    canvas.save(out_path, format="PNG", optimize=True)
    print(f"Saved satellite image: {out_path} ({canvas.size[0]}x{canvas.size[1]} px, {success_count}/{total_tiles} tiles)")
    return True




def _download_mapbox_image(lat: float, lng: float, out_path: str) -> bool:
    # Used purely as a safety fallback if Google Earth fails
    token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
    if not token:
        return False

    offset = 0.0045
    p1 = f"pin-s-1+fce300({lng - offset},{lat + offset})" 
    p2 = f"pin-s-2+fce300({lng + offset},{lat + offset})" 
    p3 = f"pin-s-3+fce300({lng + offset},{lat - offset})" 
    p4 = f"pin-s-4+fce300({lng - offset},{lat - offset})" 
    
    overlays = f"{p1},{p2},{p3},{p4}"
    url = f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/{overlays}/{lng},{lat},15.5,0,0/1280x760?access_token={token}"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        img = Image.open(io.BytesIO(response.content))
        img = img.crop((0, 0, 1280, 720)) 
        
        img = ImageEnhance.Contrast(img).enhance(1.15)
        img = ImageEnhance.Color(img).enhance(1.25)
        
        img.save(out_path, format="PNG", optimize=True)
        return True
    except requests.RequestException:
        return False


def _download_vector_map(lat: float, lng: float, out_path: str) -> bool:
    token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
    if not token:
        return False

    url = f"https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/static/{lng},{lat},16.5,0,0/1050x570?access_token={token}"
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        img = Image.open(io.BytesIO(response.content)).convert("RGB")
        img = img.crop((0, 0, 1050, 545)) 
        img.save(out_path, format="PNG", optimize=True)
        return True
    except requests.RequestException:
        return False


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "times.ttf",
        "arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except IOError:
            continue
    return ImageFont.load_default()


def _compose_qgis_mock(satellite_path: str, qgis_path: str, lat: float, lng: float, label: str) -> None:
    template_path = "static/qgis_template.png" 
    try:
        canvas = Image.open(template_path).convert("RGB")
    except FileNotFoundError:
        raise ScreenshotEngineError(f"Missing QGIS template at {template_path}")

    draw = ImageDraw.Draw(canvas)
    MAP_X, MAP_Y = 312, 135
    MAP_WIDTH, MAP_HEIGHT = 1045, 595

    satellite = Image.open(satellite_path).convert("RGB").resize((MAP_WIDTH, MAP_HEIGHT))
    canvas.paste(satellite, (MAP_X, MAP_Y))

    draw.rectangle([(10, 480), (300, 700)], fill="#FFFFFF")
    layer_start_x, layer_start_y, line_height = 25, 490, 24
    layers = [
        f"AOI - {label[:15]}...",
        "Road Network",
        "Administrative Boundary",
        "Drainage Data",
        "Georeferenced Points"
    ]
    font = _load_font(12)
    y_offset = layer_start_y

    for layer_name in layers:
        draw.rectangle([(layer_start_x, y_offset + 2), (layer_start_x + 12, y_offset + 14)], outline="#555555", fill="#FFFFFF", width=1)
        draw.text((layer_start_x + 22, y_offset), layer_name, fill="#000000", font=font)
        y_offset += line_height

    draw.rectangle([(400, canvas.height - 25), (750, canvas.height - 5)], fill="#F0F0F0") 
    coord_text = f"Coordinate {lng:.6f},{lat:.6f}    Scale 1:6837"
    draw.text((450, canvas.height - 22), coord_text, fill="#000000", font=font)

    canvas.save(qgis_path, format="PNG", optimize=True)


def _compose_final_layout(vector_path: str, layout_path: str, lat: float, lng: float, label: str) -> None:
    template_path = "static/map_layout_template.png" 
    try:
        canvas = Image.open(template_path).convert("RGB").resize((1200, 850))
    except FileNotFoundError:
        raise ScreenshotEngineError(f"Missing layout template at {template_path}")

    draw = ImageDraw.Draw(canvas)

    MAP_X, MAP_Y = 77, 168
    MAP_WIDTH, MAP_HEIGHT = 1043, 485
    vector_img = Image.open(vector_path).convert("RGB").resize((MAP_WIDTH, MAP_HEIGHT))
    canvas.paste(vector_img, (MAP_X, MAP_Y))

    title_font = _load_font(32)
    scale_font = _load_font(36)

    clean_label = label.split(',')[0].strip().upper()
    title_text = f"A DETAILED MAP OF {clean_label}"
    draw.rectangle([(130, 90), (1070, 145)], fill="#F4EBED") 
    
    text_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_x = (canvas.width - (text_bbox[2] - text_bbox[0])) // 2
    draw.text((title_x, 102), title_text, fill="#000000", font=title_font)

    random_scale = random.choice(range(7500, 9500, 50))
    draw.rectangle([(520, 710), (660, 755)], fill="#F4F6F5") 
    draw.text((530, 712), f"1 : {random_scale:,}", fill="#000000", font=scale_font)

    canvas.save(layout_path, format="PNG", optimize=True)


def _image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def generate_report_images(coordinates: str, location: str, temp_dir: str) -> tuple[str, str, str]:
    lat, lng = _parse_location(coordinates)

    job_id = uuid.uuid4().hex
    
    
    # DEBUG: Print what the geocoder actually resolved
    print(f"\n{'='*50}")
    print(f"LOCATION INPUT: {coordinates}")
    print(f"RESOLVED COORDS: lat={lat}, lng={lng}")
    print(f"GOOGLE MAPS URL: https://www.google.com/maps/@{lat},{lng},18z")
    print(f"TILE TEST URL: https://mt1.google.com/vt/lyrs=s&x={int((lng+180)/360*2**18)}&y={int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*2**18)}&z=18")
    print(f"{'='*50}\n")
    
    
    sat_path = os.path.join(temp_dir, f"satellite_{job_id}.png")
    qgis_path = os.path.join(temp_dir, f"qgis_mock_{job_id}.png")
    vector_path = os.path.join(temp_dir, f"vector_map_{job_id}.png")
    layout_path = os.path.join(temp_dir, f"final_layout_{job_id}.png")

    try:
        # THE FIX: Prioritize Google Earth!
        if not _capture_google_earth(lat, lng, sat_path):
            # Fallback to Mapbox only if Google Earth fails
            print("Google Earth capture failed, falling back to Mapbox...")
            if not _download_mapbox_image(lat, lng, sat_path):
                raise ScreenshotEngineError("Failed to download satellite imagery")
            
        if not _download_vector_map(lat, lng, vector_path):
            raise ScreenshotEngineError("Failed to download vector imagery")

        _compose_qgis_mock(sat_path, qgis_path, lat, lng, coordinates)
        _compose_final_layout(vector_path, layout_path, lat, lng, location)

        sat_b64 = _image_to_base64(sat_path)
        qgis_b64 = _image_to_base64(qgis_path)
        layout_b64 = _image_to_base64(layout_path)

        return sat_b64, qgis_b64, layout_b64
        
    finally:
        for path in [sat_path, qgis_path, vector_path, layout_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
