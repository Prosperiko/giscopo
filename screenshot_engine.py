import math
import os
import re
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright


from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import io

class ScreenshotEngineError(RuntimeError):
    pass


# def _parse_location(location: str) -> tuple[float, float]:
#     coord_pattern = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
#     match = coord_pattern.match(location)
#     if match:
#         lat, lng = float(match.group(1)), float(match.group(2))
#         if not (-90 <= lat <= 90 and -180 <= lng <= 180):
#             raise ScreenshotEngineError("Coordinates out of valid range")
#         return lat, lng

#     try:
#         response = requests.get(
#             "https://nominatim.openstreetmap.org/search",
#             params={"q": location, "format": "json", "limit": 1},
#             headers={"User-Agent": "giscopo/1.0"},
#             timeout=20,
#         )
#         response.raise_for_status()
#         items = response.json()
#         if not items:
#             raise ScreenshotEngineError("Unable to resolve location")
#         return float(items[0]["lat"]), float(items[0]["lon"])
#     except requests.RequestException as exc:
#         raise ScreenshotEngineError("Unable to geocode location") from exc


# def _parse_location(location: str) -> tuple[float, float]:
#     coord_pattern = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
#     match = coord_pattern.match(location)
#     if match:
#         lat, lng = float(match.group(1)), float(match.group(2))
#         if not (-90 <= lat <= 90 and -180 <= lng <= 180):
#             raise ScreenshotEngineError("Coordinates out of valid range")
#         return lat, lng

#     # THE FIX: Force the search to look within Nigeria to drastically improve accuracy
#     search_query = location
#     if "nigeria" not in search_query.lower():
#         search_query = f"{location}, Nigeria"

#     try:
#         response = requests.get(
#             "https://nominatim.openstreetmap.org/search",
#             params={"q": search_query, "format": "json", "limit": 1},
#             headers={"User-Agent": "giscopo/1.0"},
#             timeout=20,
#         )
#         response.raise_for_status()
#         items = response.json()
#         if not items:
#             raise ScreenshotEngineError(f"Unable to resolve location: {search_query}")
#         return float(items[0]["lat"]), float(items[0]["lon"])
#     except requests.RequestException as exc:
#         raise ScreenshotEngineError("Unable to geocode location") from exc
    


import os
import re
import urllib.parse
import requests

def _parse_location(location: str) -> tuple[float, float]:
    # 1. First, check if the user just pasted raw coordinates (lat, lng)
    coord_pattern = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")
    match = coord_pattern.match(location)
    if match:
        lat, lng = float(match.group(1)), float(match.group(2))
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ScreenshotEngineError("Coordinates out of valid range")
        return lat, lng

    # 2. Grab your existing Mapbox token
    token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
    if not token:
        raise ScreenshotEngineError("Missing Mapbox token in .env file")

    # Force the search to look within Nigeria to drastically improve accuracy
    search_query = location
    if "nigeria" not in search_query.lower():
        search_query = f"{location}, Nigeria"

    try:
        # Use Mapbox's highly intelligent geocoding API instead of OpenStreetMap
        encoded_query = urllib.parse.quote(search_query)
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_query}.json"
        
        response = requests.get(
            url,
            params={"access_token": token, "limit": 1},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        
        if not data.get("features"):
            raise ScreenshotEngineError(f"Unable to resolve location: {search_query}")
            
        # IMPORTANT: Mapbox returns coordinates in [longitude, latitude] order!
        lng, lat = data["features"][0]["center"]
        return float(lat), float(lng)
        
    except requests.RequestException as exc:
        raise ScreenshotEngineError("Unable to geocode location") from exc
    
    
    

# def _download_mapbox_image(lat: float, lng: float, out_path: str) -> bool:
#     token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
#     if not token:
#         return False

#     url = (
#         "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/"
#         f"pin-s+ff0000({lng},{lat})/{lng},{lat},15/1280x720?access_token={token}"
#     )
#     try:
#         response = requests.get(url, timeout=30)
#         response.raise_for_status()
#         Path(out_path).write_bytes(response.content)
#         return True
#     except requests.RequestException:
#         return False

# def _download_mapbox_image(lat: float, lng: float, out_path: str) -> bool:
#     token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
#     if not token:
#         print("Mapbox token not found. Falling back to Playwright...")
#         return False

#     # pin-m-p+fce300 creates a Medium-sized, Yellow (#fce300) pin with the letter 'P' inside.
#     # We zoom to level 17 for a close-up academic satellite view.
#     url = (
#         "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/"
#         f"pin-m-p+fce300({lng},{lat})/{lng},{lat},17,0,0/1280x720?access_token={token}"
#     )
    
#     try:
#         response = requests.get(url, timeout=30)
#         response.raise_for_status()
#         Path(out_path).write_bytes(response.content)
#         print("Successfully captured Mapbox satellite image!")
#         return True
#     except requests.RequestException as exc:
#         print(f"Mapbox API failed: {exc}")
#         return False

# def _download_mapbox_image(lat: float, lng: float, out_path: str) -> bool:
#     token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
#     if not token:
#         return False

#     # 1. REMOVED THE 'P': Changed 'pin-m-p' to 'pin-s' (small, blank pin)
#     # 2. THE CROP TRICK: Requested height is 760 (40 pixels taller than we actually want)
#     url = (
#         "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/"
#         f"pin-s+fce300({lng},{lat})/{lng},{lat},17,0,0/1280x760?access_token={token}"
#     )
    
#     try:
#         response = requests.get(url, timeout=30)
#         response.raise_for_status()
        
#         # Load the downloaded bytes directly into memory
#         img = Image.open(io.BytesIO(response.content))
        
#         # 3. CROP THE WATERMARK: Cut off the bottom 40 pixels, leaving us with a perfect 1280x720 image
#         img = img.crop((0, 0, 1280, 720))
        
#         # 4. DE-FOG (Post-Processing):
#         # Boost contrast by 15% and color saturation by 25% to mimic Google Earth's vibrant look
#         enhancer_contrast = ImageEnhance.Contrast(img)
#         img = enhancer_contrast.enhance(1.15)
        
#         enhancer_color = ImageEnhance.Color(img)
#         img = enhancer_color.enhance(1.25)
        
#         # Save the finalized, clean image to disk
#         img.save(out_path, format="PNG", optimize=True)
#         return True
#     except requests.RequestException:
#         return False
    


# def _download_mapbox_image(lat: float, lng: float, out_path: str) -> bool:
#     token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
#     if not token:
#         return False

#     # 1. DEFINE THE RECTANGLE
#     # An offset of 0.0015 degrees roughly equals 150 meters.
#     # We add/subtract this from the center to create 4 corners.
#     offset = 0.0015
    
#     # 2. CREATE THE PINS
#     # Mapbox syntax: pin-{size}-{label}+{color}({lng},{lat})
#     # We use small pins (s), labeled 1-4, colored yellow (fce300)
#     p1 = f"pin-s-1+fce300({lng - offset},{lat + offset})" # Top-Left
#     p2 = f"pin-s-2+fce300({lng + offset},{lat + offset})" # Top-Right
#     p3 = f"pin-s-3+fce300({lng + offset},{lat - offset})" # Bottom-Right
#     p4 = f"pin-s-4+fce300({lng - offset},{lat - offset})" # Bottom-Left
    
#     # Mapbox allows multiple overlays separated by commas
#     overlays = f"{p1},{p2},{p3},{p4}"

#     # 3. BUILD THE URL
#     # We drop the zoom level slightly to 16 so all 4 pins fit nicely in the frame
#     url = (
#         "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/"
#         f"{overlays}/{lng},{lat},16,0,0/1280x760?access_token={token}"
#     )
    
#     try:
#         response = requests.get(url, timeout=30)
#         response.raise_for_status()
        
#         # Load downloaded image into PIL
#         img = Image.open(io.BytesIO(response.content))
        
#         # Crop off the bottom 40px to hide the Mapbox attribution logo
#         img = img.crop((0, 0, 1280, 720))
        
#         # Post-Processing: Enhance contrast and color saturation
#         enhancer_contrast = ImageEnhance.Contrast(img)
#         img = enhancer_contrast.enhance(1.15)
        
#         enhancer_color = ImageEnhance.Color(img)
#         img = enhancer_color.enhance(1.25)
        
#         # Save the finalized, labeled image to disk
#         img.save(out_path, format="PNG", optimize=True)
#         return True
#     except requests.RequestException:
#         return False   


def _download_mapbox_image(lat: float, lng: float, out_path: str) -> bool:
    token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
    if not token:
        return False

    # 1. WIDEN THE RECTANGLE
    # Increased the offset from 0.0015 to 0.0045 (roughly 450+ meters from center)
    # This pushes the pins far apart toward the edges of the campus.
    offset = 0.0045
    
    # 2. CREATE THE PINS
    p1 = f"pin-s-1+fce300({lng - offset},{lat + offset})" # Top-Left
    p2 = f"pin-s-2+fce300({lng + offset},{lat + offset})" # Top-Right
    p3 = f"pin-s-3+fce300({lng + offset},{lat - offset})" # Bottom-Right
    p4 = f"pin-s-4+fce300({lng - offset},{lat - offset})" # Bottom-Left
    
    overlays = f"{p1},{p2},{p3},{p4}"

    # 3. BUILD THE URL
    # Adjusted zoom level to 15.5 to ensure the wider pins fit beautifully in the frame
    url = (
        "https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/"
        f"{overlays}/{lng},{lat},15.5,0,0/1280x760?access_token={token}"
    )
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Load downloaded image into PIL
        img = Image.open(io.BytesIO(response.content))
        
        # Crop off the bottom 40px to hide the Mapbox attribution logo
        img = img.crop((0, 0, 1280, 720))
        
        # Post-Processing: Enhance contrast and color saturation
        enhancer_contrast = ImageEnhance.Contrast(img)
        img = enhancer_contrast.enhance(1.15)
        
        enhancer_color = ImageEnhance.Color(img)
        img = enhancer_color.enhance(1.25)
        
        # Save the finalized, labeled image to disk
        img.save(out_path, format="PNG", optimize=True)
        return True
    except requests.RequestException:
        return False


# def _capture_with_playwright(lat: float, lng: float, out_path: str) -> None:
#     map_url = f"https://www.google.com/maps/@{lat},{lng},18z/data=!3m1!1e3"

#     try:
#         with sync_playwright() as playwright:
#             browser = playwright.chromium.launch(headless=True)
#             page = browser.new_page(viewport={"width": 1280, "height": 720})
#             page.goto(map_url, wait_until="domcontentloaded", timeout=90000)
#             page.wait_for_timeout(3000)
#             page.screenshot(path=out_path, full_page=False)
#             browser.close()
#     except Exception as exc:
#         raise ScreenshotEngineError("Playwright satellite capture failed") from exc

# def _capture_with_playwright(lat: float, lng: float, out_path: str) -> None:
#     # --- ADD THESE 4 LINES ---
#     import asyncio
#     import sys
#     if sys.platform == "win32":
#         asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
#     # -------------------------

#     map_url = f"https://www.google.com/maps/@{lat},{lng},18z/data=!3m1!1e3"

#     try:
#         with sync_playwright() as playwright:
#             browser = playwright.chromium.launch(headless=True)
#             page = browser.new_page(viewport={"width": 1280, "height": 720})
#             page.goto(map_url, wait_until="domcontentloaded", timeout=90000)
#             page.wait_for_timeout(3000)
#             page.screenshot(path=out_path, full_page=False)
#             browser.close()
#     except Exception as exc:
#         raise ScreenshotEngineError("Playwright satellite capture failed") from exc

# def _capture_with_playwright(lat: float, lng: float, out_path: str) -> None:
#     import asyncio
#     import sys
#     if sys.platform == "win32":
#         asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


    
#     # Using the Google Maps embed/satellite parameter which bypasses the consent redirect
#     map_url = f"https://www.google.com/maps/embed?pb=!1m14!1m12!1m3!1d3500!2d{lng}!3d{lat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!5e0!3m2!1sen!2sng!4v1!5m2!1sen!2sng"

#     try:
#         with sync_playwright() as playwright:
#             browser = playwright.chromium.launch(headless=True)
            
#             # Create a context with a standard user-agent so Google doesn't flag it as a bot
#             context = browser.new_context(
#                 viewport={"width": 1280, "height": 720},
#                 user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
#             )
#             page = context.new_page()
            
#             page.goto(map_url, wait_until="domcontentloaded", timeout=90000)
#             page.wait_for_timeout(4000) # Give it an extra second to load the tiles
#             page.screenshot(path=out_path, full_page=False)
#             browser.close()
#     except Exception as exc:
#         raise ScreenshotEngineError("Playwright satellite capture failed") from exc


# def _capture_with_playwright(lat: float, lng: float, out_path: str) -> None:
#     import asyncio
#     import sys
#     if sys.platform == "win32":
#         asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

#     # Wrap the Google Maps embed URL inside a local HTML iframe container to satisfy Google's API policy
#     html_content = f"""
#     <!DOCTYPE html>
#     <html>
#     <head>
#         <style>
#             body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: #111; }}
#             iframe {{ width: 100vw; height: 100vh; border: 0; }}
#         </style>
#     </head>
#     <body>
#         <iframe src="https://www.google.com/maps/embed?pb=!1m14!1m12!1m3!1d3500!2d{lng}!3d{lat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!5e0!3m2!1sen!2sng!4v1!5m2!1sen!2sng" allowfullscreen></iframe>
#     </body>
#     </html>
#     """

#     try:
#         with sync_playwright() as playwright:
#             browser = playwright.chromium.launch(headless=True)
            
#             # Create a context with a standard user-agent
#             context = browser.new_context(
#                 viewport={"width": 1280, "height": 720},
#                 user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
#             )
#             page = context.new_page()
            
#             # Load the local HTML container instead of navigating directly to the URL
#             page.set_content(html_content, wait_until="load")
#             page.wait_for_timeout(5000) # Give the satellite tiles time to render inside the iframe
#             page.screenshot(path=out_path, full_page=False)
#             browser.close()
#     except Exception as exc:
#         raise ScreenshotEngineError("Playwright satellite capture failed") from exc


# def _capture_with_playwright(lat: float, lng: float, out_path: str) -> None:
#     import asyncio
#     import sys
#     if sys.platform == "win32":
#         asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

#     # Direct satellite view URL for Google Maps
#     map_url = f"https://www.google.com/maps/@{lat},{lng},17z/data=!3m1!1e3"

#     try:
#         with sync_playwright() as playwright:
#             browser = playwright.chromium.launch(headless=True)
#             context = browser.new_context(
#                 viewport={"width": 1280, "height": 720},
#                 user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
#             )
#             page = context.new_page()
            
#             # Navigate directly to the satellite layer view
#             page.goto(map_url, wait_until="domcontentloaded", timeout=90000)
            
#             # Automatically click Google's "Accept all" cookie consent button if it appears
#             try:
#                 page.click("#L2AGLb", timeout=4000)
#                 page.wait_for_timeout(1000)
#             except Exception:
#                 pass # Continue if no consent dialog is present
                
#             # Allow high-resolution satellite image tiles to fully render
#             page.wait_for_timeout(5000)
#             page.screenshot(path=out_path, full_page=False)
#             browser.close()
#     except Exception as exc:
#         raise ScreenshotEngineError("Playwright satellite capture failed") from exc


# def _capture_with_playwright(lat: float, lng: float, out_path: str) -> None:
#     import asyncio
#     import sys
#     if sys.platform == "win32":
#         asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

#     # Direct Google Maps URL focused strictly on the Satellite Layer
#     map_url = f"https://www.google.com/maps/@{lat},{lng},17z/data=!3m1!1e3"

#     try:
#         from playwright.sync_api import sync_playwright
#         with sync_playwright() as playwright:
#             browser = playwright.chromium.launch(headless=True)
#             context = browser.new_context(
#                 viewport={"width": 1280, "height": 720},
#                 user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
#             )
            
#             # 1. BYPASS COOKIE WALL: Inject Google's "Accept All" cookie directly before loading
#             context.add_cookies([{
#                 "name": "CONSENT",
#                 "value": "YES+cb.20230501-14-p0.en+FX+410",
#                 "domain": ".google.com",
#                 "path": "/"
#             }])

#             page = context.new_page()
            
#             # 2. LOAD MAP: We use 'domcontentloaded' because Google Maps never truly reaches 'networkidle'
#             page.goto(map_url, wait_until="domcontentloaded", timeout=90000)
            
#             # 3. CLEAN INTERFACE: Hide search bars, side panels, and buttons for a raw satellite look
#             page.add_style_tag(content="""
#                 #omnibox-container, #pane, #scene-header, 
#                 .app-viewcard-strip, .widget-zoom, 
#                 .widget-scene, .app-vertical-widget-holder,
#                 #vas-bottom-right-container { display: none !important; }
#             """)
            
#             # 4. RENDER TIME: Force a hard 10-second wait to guarantee all high-res tiles download fully
#             page.wait_for_timeout(10000)
            
#             page.screenshot(path=out_path, full_page=False)
#             browser.close()
#     except Exception as exc:
#         raise ScreenshotEngineError("Playwright satellite capture failed") from exc


# 


# def _capture_with_playwright(lat: float, lng: float, out_path: str) -> None:
#     import asyncio
#     import sys
#     if sys.platform == "win32":
#         asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

#     # We use the embed URL that successfully bypassed the cookie wall on your machine.
#     # The crucial change is !5e1 (instead of !5e0) which forces Satellite imagery.
#     html_content = f"""
#     <!DOCTYPE html>
#     <html>
#     <head>
#         <style>
#             body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: #000; }}
#             iframe {{ width: 100vw; height: 100vh; border: 0; }}
#         </style>
#     </head>
#     <body>
#         <iframe src="https://www.google.com/maps/embed?pb=!1m14!1m12!1m3!1d3500!2d{lng}!3d{lat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!5e1!3m2!1sen!2sng!4v1!5m2!1sen!2sng" allowfullscreen></iframe>
#     </body>
#     </html>
#     """

#     try:
#         from playwright.sync_api import sync_playwright
#         with sync_playwright() as playwright:
#             browser = playwright.chromium.launch(headless=True)
            
#             context = browser.new_context(
#                 viewport={"width": 1280, "height": 720},
#                 user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
#             )
#             page = context.new_page()
            
#             # Load the local HTML container
#             page.set_content(html_content, wait_until="load")
            
#             # Wait 8 seconds for the heavy high-res satellite tiles to stream in
#             page.wait_for_timeout(8000)
            
#             page.screenshot(path=out_path, full_page=False)
#             browser.close()
#     except Exception as exc:
#         raise ScreenshotEngineError("Playwright satellite capture failed") from exc
    
    
# def _capture_with_playwright(lat: float, lng: float, out_path: str) -> None:
#     import asyncio
#     import sys
#     if sys.platform == "win32":
#         asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

#     # Direct Google Maps URL focused on the Hybrid Satellite Layer (Satellite + Labels)
#     # 18z provides a closer zoom level similar to your reference image
#     map_url = f"https://www.google.com/maps/@{lat},{lng},18z/data=!3m1!1e3"

#     try:
#         from playwright.sync_api import sync_playwright
#         with sync_playwright() as playwright:
#             browser = playwright.chromium.launch(headless=True)
            
#             # Create a context with a standard user-agent to avoid bot detection
#             context = browser.new_context(
#                 viewport={"width": 1280, "height": 720},
#                 user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
#             )
            
#             # 1. BYPASS COOKIE WALL: Inject Google's "Accept All" cookie 
#             # This prevents the consent redirect entirely before we even load the page
#             context.add_cookies([{
#                 "name": "CONSENT",
#                 "value": "YES+cb.20230501-14-p0.en+FX+410",
#                 "domain": ".google.com",
#                 "path": "/"
#             }])

#             page = context.new_page()
            
#             # 2. LOAD MAP: Wait until DOM loads (maps never truly hit networkidle)
#             page.goto(map_url, wait_until="domcontentloaded", timeout=90000)
            
#             # 3. STRIP THE UI: Hide all Google Maps interface elements
#             # This removes the search bar, side panels, zoom controls, and watermarks,
#             # leaving only the raw satellite canvas and on-map labels.
#             page.add_style_tag(content="""
#                 #omnibox-container, #pane, #scene-header, #titlecard,
#                 .app-viewcard-strip, .widget-zoom, .watermark,
#                 .widget-scene, .app-vertical-widget-holder,
#                 #vas-bottom-right-container, .scene-footer-container { 
#                     display: none !important; 
#                 }
#             """)
            
#             # 4. RENDER TIME: Force an 8-second wait to guarantee high-res tiles download fully
#             # Since background tiles load via JS, this is mandatory to avoid blurry grey boxes.
#             page.wait_for_timeout(8000)
            
#             page.screenshot(path=out_path, full_page=False)
#             browser.close()
#     except Exception as exc:
#         raise ScreenshotEngineError("Playwright satellite capture failed") from exc
    
# def _capture_with_playwright(lat: float, lng: float, out_path: str) -> None:
#     import asyncio
#     import sys
#     if sys.platform == "win32":
#         asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

#     # Added ?hl=en to ensure Google loads in English, making button targeting reliable
#     map_url = f"https://www.google.com/maps/@{lat},{lng},18z/data=!3m1!1e3?hl=en"

#     try:
#         from playwright.sync_api import sync_playwright
#         with sync_playwright() as playwright:
#             browser = playwright.chromium.launch(headless=True)
#             context = browser.new_context(
#                 viewport={"width": 1280, "height": 720},
#                 user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
#                 locale="en-US"
#             )
            
#             # 1. MULTI-DOMAIN COOKIE INJECTION
#             # Target both the global and Nigerian domains to prevent regional redirects
#             consent_cookie = "YES+cb.20230501-14-p0.en+FX+410"
#             context.add_cookies([
#                 {"name": "CONSENT", "value": consent_cookie, "domain": ".google.com", "path": "/"},
#                 {"name": "CONSENT", "value": consent_cookie, "domain": ".google.com.ng", "path": "/"}
#             ])

#             page = context.new_page()
            
#             # 2. LOAD MAP
#             page.goto(map_url, wait_until="domcontentloaded", timeout=90000)
            
#             # 3. THE AUTOCLICKER FALLBACK
#             # If we still end up on the consent page, physically click "Accept all"
#             if "consent.google" in page.url:
#                 try:
#                     accept_btn = page.locator('button:has-text("Accept all"), button#L2AGLb').first
#                     accept_btn.click(timeout=5000)
#                     # Wait for it to redirect us back to the actual map
#                     page.wait_for_url("**/maps/**", timeout=15000, wait_until="domcontentloaded")
#                 except Exception:
#                     pass # Ignore if it fails, it might have resolved itself
            
#             # 4. STRIP THE UI
#             page.add_style_tag(content="""
#                 #omnibox-container, #pane, #scene-header, #titlecard,
#                 .app-viewcard-strip, .widget-zoom, .watermark,
#                 .widget-scene, .app-vertical-widget-holder,
#                 #vas-bottom-right-container, .scene-footer-container { 
#                     display: none !important; 
#                 }
#             """)
            
#             # 5. RENDER TIME
#             # 8 seconds allows the high-res satellite tiles to stream in cleanly
#             page.wait_for_timeout(8000)
            
#             page.screenshot(path=out_path, full_page=False)
#             browser.close()
#     except Exception as exc:
#         raise ScreenshotEngineError("Playwright satellite capture failed") from exc
    
    
def _capture_with_playwright(lat: float, lng: float, out_path: str) -> None:
    import asyncio
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    map_url = f"https://www.google.com/maps/@{lat},{lng},18z/data=!3m1!1e3?hl=en"

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            
            # 1. FIX THE GRAY GRID: Force WebGL and hardware acceleration bypasses
            browser = playwright.chromium.launch(
                headless=True,
                args=[
                    "--ignore-gpu-blocklist", 
                    "--enable-webgl",
                    "--use-gl=swiftshader", # Forces software rendering if GPU is missing
                    "--disable-blink-features=AutomationControlled"
                ]
            )
            
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                locale="en-US"
            )
            
            consent_cookie = "YES+cb.20230501-14-p0.en+FX+410"
            context.add_cookies([
                {"name": "CONSENT", "value": consent_cookie, "domain": ".google.com", "path": "/"},
                {"name": "CONSENT", "value": consent_cookie, "domain": ".google.com.ng", "path": "/"}
            ])

            page = context.new_page()
            
            page.goto(map_url, wait_until="domcontentloaded", timeout=90000)
            
            if "consent.google" in page.url:
                try:
                    accept_btn = page.locator('button:has-text("Accept all"), button#L2AGLb').first
                    accept_btn.click(timeout=5000)
                    page.wait_for_url("**/maps/**", timeout=15000, wait_until="domcontentloaded")
                except Exception:
                    pass
            
            # 2. FIX THE UI: Nuke the new Google Maps layout containers
            page.add_style_tag(content="""
                /* Hide the massive new search/sidebar container */
                #QA0Szd { display: none !important; }
                
                /* Hide the leftmost navigation rail */
                div[role="navigation"] { display: none !important; }
                
                /* Catch-all for old UI and overlays */
                #omnibox-container, #pane, #scene-header, #titlecard,
                .app-viewcard-strip, .widget-zoom, .watermark, .gmnoprint,
                .widget-scene, .app-vertical-widget-holder,
                #vas-bottom-right-container, .scene-footer-container { 
                    display: none !important; 
                    opacity: 0 !important;
                }
            """)
            
            # THE NUCLEAR OPTION: Physically remove the UI from the DOM
            page.evaluate("""
                const selectors = [
                    '#QA0Szd', /* The new massive side panel container */
                    '[role="navigation"]', /* Nav rails */
                    '#omnibox-container', /* Search bar */
                    '#pane', /* Old side panel */
                    '.widget-zoom', /* Zoom buttons */
                    '.gmnoprint', /* Various map controls */
                    '.app-viewcard-strip', /* Bottom strips */
                    '.scene-footer-container', /* Footers */
                    '#titlecard', /* Location titles */
                    '#watermark' /* Google watermark */
                ];
                selectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => el.remove());
                });
            """)
            
            
            # Wait 8 seconds for the simulated WebGL engine to render the tiles
            page.wait_for_timeout(8000)
            
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


# def _compose_qgis_mock(satellite_path: str, qgis_path: str, lat: float, lng: float, label: str) -> None:
#     canvas = Image.new("RGB", (1366, 768), "#2B2F36")
#     draw = ImageDraw.Draw(canvas)

#     draw.rectangle((0, 0, 1366, 34), fill="#3B4048")
#     draw.text((16, 9), "QGIS 3.34 - Academic GIS Workspace", fill="#EDEFF2", font=_load_font(14))

#     draw.rectangle((0, 34, 280, 768), fill="#1F2328")
#     draw.text((12, 46), "Layers", fill="#F0F3F6", font=_load_font(16))
#     layer_lines = [
#         "☑ Satellite Imagery",
#         "☑ Administrative Boundary",
#         f"☑ AOI - {label[:28]}",
#         "☐ Road Network",
#         "☐ Drainage",
#     ]
#     y = 80
#     for line in layer_lines:
#         draw.text((16, y), line, fill="#D4D8DD", font=_load_font(14))
#         y += 28

#     draw.rectangle((280, 34, 1366, 740), fill="#101418")

#     satellite = Image.open(satellite_path).convert("RGB").resize((1030, 650))
#     canvas.paste(satellite, (308, 62))

#     draw.rectangle((0, 740, 1366, 768), fill="#3B4048")
#     coord_text = f"EPSG:4326 | Lat: {lat:.6f}  Lon: {lng:.6f} | Scale 1:{int(math.pow(2, 15)):,}"
#     draw.text((16, 747), coord_text, fill="#EDEFF2", font=_load_font(13))

#     canvas.save(qgis_path, format="PNG", optimize=True)


# def _compose_qgis_mock(satellite_path: str, qgis_path: str, lat: float, lng: float, label: str) -> None:
#     # 1. Load your realistic QGIS screenshot template
#     # Make sure this path points to where you saved your screenshot!
#     template_path = "static/qgis_template.png" 
    
#     try:
#         canvas = Image.open(template_path).convert("RGB")
#     except FileNotFoundError:
#         raise ScreenshotEngineError(f"Missing QGIS template! Please place your screenshot at {template_path}")

#     # 2. Define exactly where the map should be pasted (The "Canvas Hole")
#     # You will need to adjust these numbers slightly to match your specific screenshot
#     # Example measurements based on a standard 1366x768 screen:
#     MAP_X = 250      # Pixels from the left edge (to clear the browser/layers panel)
#     MAP_Y = 160      # Pixels from the top edge (to clear the toolbars)
    
#     # Calculate how big the map needs to be based on the template's size
#     # Assuming a right margin of ~50px and a bottom status bar of ~30px
#     MAP_WIDTH = canvas.width - MAP_X - 50 
#     MAP_HEIGHT = canvas.height - MAP_Y - 30

#     # 3. Load and resize the generated Mapbox satellite image to fit the hole
#     satellite = Image.open(satellite_path).convert("RGB").resize((MAP_WIDTH, MAP_HEIGHT))
    
#     # 4. Paste the satellite image onto the QGIS template
#     canvas.paste(satellite, (MAP_X, MAP_Y))

#     # 5. (Optional) Dynamically write the exact coordinates into the bottom status bar!
#     # If your template has a blank space at the bottom for coordinates, this writes it in.
#     draw = ImageDraw.Draw(canvas)
#     coord_text = f"Coordinate {lng:.6f},{lat:.6f}    Scale 1:6837"
    
#     # Adjust the X, Y text placement to match your status bar
#     text_x = canvas.width // 2
#     text_y = canvas.height - 22 
#     draw.text((text_x, text_y), coord_text, fill="#000000", font=_load_font(12))

#     # Save the final realistic image
#     canvas.save(qgis_path, format="PNG", optimize=True)


def _compose_qgis_mock(satellite_path: str, qgis_path: str, lat: float, lng: float, label: str) -> None:
    template_path = "static/qgis_template.png" 
    
    try:
        canvas = Image.open(template_path).convert("RGB")
    except FileNotFoundError:
        raise ScreenshotEngineError(f"Missing QGIS template! Please place your screenshot at {template_path}")

    draw = ImageDraw.Draw(canvas)

    # --- 1. FIX THE CENTERING (The Map Canvas Hole) ---
    # These numbers are estimated based on your template. 
    # Tweak them slightly if the map is still a few pixels off!
    MAP_X = 312      # Start pasting 312 pixels from the left edge (clears the side panel)
    MAP_Y = 135      # Start pasting 135 pixels from the top (clears the toolbars)
    MAP_WIDTH = 1045 # Make the map exactly 1045 pixels wide
    MAP_HEIGHT = 595 # Make the map exactly 595 pixels tall

    satellite = Image.open(satellite_path).convert("RGB").resize((MAP_WIDTH, MAP_HEIGHT))
    canvas.paste(satellite, (MAP_X, MAP_Y))


    # --- 2. ADD DYNAMIC UNCHECKED LAYERS ---
    # First, draw a white rectangle over the Layers panel to wipe it clean
    # (Just in case your template already has text there)
    draw.rectangle([(10, 480), (300, 700)], fill="#FFFFFF")

    # Define where the layer list starts
    layer_start_x = 25
    layer_start_y = 490
    line_height = 24 # Vertical spacing between layers

    # Your custom list of layers
    layers = [
        f"AOI - {label[:15]}...", # Truncates the location name so it fits
        "Road Network",
        "Administrative Boundary",
        "Drainage Data",
        "Georeferenced Points"
    ]

    font = _load_font(12)
    y_offset = layer_start_y

    for layer_name in layers:
        # Draw the unchecked checkbox (a simple 12x12 empty square)
        box_size = 12
        draw.rectangle(
            [(layer_start_x, y_offset + 2), (layer_start_x + box_size, y_offset + 2 + box_size)],
            outline="#555555", fill="#FFFFFF", width=1
        )
        
        # Draw the text right next to the checkbox
        draw.text((layer_start_x + 22, y_offset), layer_name, fill="#000000", font=font)
        
        # Move down for the next line
        y_offset += line_height


    # --- 3. FIX THE OVERLAPPING STATUS BAR TEXT ---
    # Draw a small grey rectangle over the old coordinates on the template to act as "white-out"
    draw.rectangle([(400, canvas.height - 25), (750, canvas.height - 5)], fill="#F0F0F0") 

    # Now write our dynamic coordinates cleanly on top
    coord_text = f"Coordinate {lng:.6f},{lat:.6f}    Scale 1:6837"
    draw.text((450, canvas.height - 22), coord_text, fill="#000000", font=font)

    canvas.save(qgis_path, format="PNG", optimize=True)


import random
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import os

# def _compose_final_layout(vector_path: str, layout_path: str, lat: float, lng: float, label: str) -> None:
#     # This should point to your new image_466afc.jpg template!
#     template_path = "static/map_layout_template.png" 
    
#     try:
#         canvas = Image.open(template_path).convert("RGB")
#     except FileNotFoundError:
#         raise ScreenshotEngineError(f"Missing layout template at {template_path}")

#     draw = ImageDraw.Draw(canvas)

#     # --- 1. PASTE THE MAP INTO THE BLANK CENTER ---
#     # You will need to fine-tune these numbers to perfectly align with the black inner borders
#     MAP_X = 63      
#     MAP_Y = 188     
#     MAP_WIDTH = 878 
#     MAP_HEIGHT = 582
    
#     vector_img = Image.open(vector_path).convert("RGB").resize((MAP_WIDTH, MAP_HEIGHT))
#     canvas.paste(vector_img, (MAP_X, MAP_Y))


#     # --- 2. DYNAMIC TITLE (The White-Out Trick) ---
#     title_font = _load_font(22) # Ensure you have a nice serif font loaded for the title
    
#     # Grab the location name, uppercase it, and strip it down
#     clean_label = label.split(',')[0].strip().upper()
#     title_text = f"A DETAILED MAP OF {clean_label}"
    
#     # Draw a rectangle over the existing "UNIVERSITY OF BENIN" text to erase it.
#     # The hex color #F4EBED roughly matches that faint pinkish-grey background in your title box.
#     draw.rectangle([(120, 115), (850, 155)], fill="#F4EBED") 
    
#     # Center the new title dynamically
#     text_bbox = draw.textbbox((0, 0), title_text, font=title_font)
#     text_width = text_bbox[2] - text_bbox[0]
#     title_x = (canvas.width - text_width) // 2
#     title_y = 120 
    
#     draw.text((title_x, title_y), title_text, fill="#000000", font=title_font)


#     # --- 3. DYNAMIC SCALE ---
#     scale_font = _load_font(28)
    
#     # Generate a unique scale for every student (e.g., stepping by 50 between 7500 and 9500)
#     # This makes every single map mathematically unique!
#     random_scale = random.choice(range(7500, 9500, 50))
#     scale_text = f"1 : {random_scale:,}"
    
#     # White-out the old "1 : 8,000" text
#     # #F4F6F5 roughly matches the off-white background near the bottom
#     draw.rectangle([(450, 830), (600, 880)], fill="#F4F6F5") 
    
#     # Write the new unique scale
#     draw.text((465, 835), scale_text, fill="#000000", font=scale_font)


#     # Save the finalized map layout
#     canvas.save(layout_path, format="PNG", optimize=True)

# def _compose_final_layout(vector_path: str, layout_path: str, lat: float, lng: float, label: str) -> None:
#     template_path = "static/map_layout_template.png" 
    
#     try:
#         # Load and FORCE resize the template so coordinates are guaranteed to match
#         canvas = Image.open(template_path).convert("RGB").resize((1200, 850))
#     except FileNotFoundError:
#         raise ScreenshotEngineError(f"Missing layout template at {template_path}")

#     draw = ImageDraw.Draw(canvas)

#     # --- 1. PASTE THE MAP INTO THE BLANK CENTER ---
#     MAP_X = 75      
#     MAP_Y = 168     
    
#     vector_img = Image.open(vector_path).convert("RGB")
#     canvas.paste(vector_img, (MAP_X, MAP_Y))


#     # --- 2. DYNAMIC TITLE (The White-Out Trick) ---
#     title_font = _load_font(26) # Slightly larger font
#     clean_label = label.split(',')[0].strip().upper()
#     title_text = f"A DETAILED MAP OF {clean_label}"
    
#     # White-out the old title (Coordinates calibrated for 1200x850)
#     draw.rectangle([(130, 90), (1070, 145)], fill="#F4EBED") 
    
#     text_bbox = draw.textbbox((0, 0), title_text, font=title_font)
#     text_width = text_bbox[2] - text_bbox[0]
#     title_x = (canvas.width - text_width) // 2
#     title_y = 105 
    
#     draw.text((title_x, title_y), title_text, fill="#000000", font=title_font)


#     # --- 3. DYNAMIC SCALE ---
#     scale_font = _load_font(28)
#     random_scale = random.choice(range(7500, 9500, 50))
#     scale_text = f"1 : {random_scale:,}"
    
#     # White-out the old scale (Coordinates calibrated for 1200x850)
#     draw.rectangle([(510, 775), (680, 825)], fill="#F4F6F5") 
    
#     draw.text((520, 785), scale_text, fill="#000000", font=scale_font)

#     canvas.save(layout_path, format="PNG", optimize=True)

import random
from PIL import Image, ImageDraw, ImageFont
import os

def _compose_final_layout(vector_path: str, layout_path: str, lat: float, lng: float, label: str) -> None:
    template_path = "static/map_layout_template.png" 
    
    try:
        canvas = Image.open(template_path).convert("RGB").resize((1200, 850))
    except FileNotFoundError:
        raise ScreenshotEngineError(f"Missing layout template at {template_path}")

    draw = ImageDraw.Draw(canvas)

    # --- FIX 1: RESIZE THE MAP TO FIT EXACTLY INSIDE THE BORDERS ---
    # We squish the Mapbox image to fit perfectly inside the black frame
    MAP_X = 77      
    MAP_Y = 168     
    MAP_WIDTH = 1043  
    MAP_HEIGHT = 485  
    
    vector_img = Image.open(vector_path).convert("RGB").resize((MAP_WIDTH, MAP_HEIGHT))
    canvas.paste(vector_img, (MAP_X, MAP_Y))


    # --- FIX 2: FORCE STANDARD WINDOWS FONTS SO TEXT IS HUGE ---
    try:
        # Tries to load standard Times New Roman (perfect for academic maps)
        title_font = ImageFont.truetype("times.ttf", 32)
        scale_font = ImageFont.truetype("times.ttf", 36)
    except IOError:
        # Fallback to Arial if Times isn't found on your Windows machine
        try:
            title_font = ImageFont.truetype("arial.ttf", 32)
            scale_font = ImageFont.truetype("arial.ttf", 36)
        except IOError:
            # Absolute worst-case scenario fallback
            title_font = ImageFont.load_default()
            scale_font = ImageFont.load_default()


    # --- 3. DYNAMIC TITLE ---
    clean_label = label.split(',')[0].strip().upper()
    title_text = f"A DETAILED MAP OF {clean_label}"
    
    # Title white-out box (This looked perfectly placed in your screenshot!)
    draw.rectangle([(130, 90), (1070, 145)], fill="#F4EBED") 
    
    text_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    text_width = text_bbox[2] - text_bbox[0]
    title_x = (canvas.width - text_width) // 2
    title_y = 102 
    
    draw.text((title_x, title_y), title_text, fill="#000000", font=title_font)


    # --- 4. DYNAMIC SCALE ---
    random_scale = random.choice(range(7500, 9500, 50))
    scale_text = f"1 : {random_scale:,}"
    
    # FIX 3: MOVE THE SCALE WHITE-OUT BOX UP!
    # Moved the Y-coordinates up so it erases "1 : 8,000" instead of the scale bar
    draw.rectangle([(520, 710), (660, 755)], fill="#F4F6F5") 
    
    draw.text((530, 712), scale_text, fill="#000000", font=scale_font)

    canvas.save(layout_path, format="PNG", optimize=True)


import io
from PIL import Image, ImageEnhance
import requests
import os

# def _download_vector_map(lat: float, lng: float, out_path: str) -> bool:
#     token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
#     if not token:
#         return False

#     # Using 'light-v11' to simulate a digitized vector GIS environment
#     url = (
#         "https://api.mapbox.com/styles/v1/mapbox/light-v11/static/"
#         f"{lng},{lat},15.5,0,0/1000x600?access_token={token}"
#     )
    
#     try:
#         response = requests.get(url, timeout=30)
#         response.raise_for_status()
        
#         img = Image.open(io.BytesIO(response.content)).convert("RGB")
#         # Crop attribution logo
#         img = img.crop((0, 0, 1000, 560))
        
#         # Boost contrast slightly so the "buildings" pop out
#         enhancer = ImageEnhance.Contrast(img)
#         img = enhancer.enhance(1.2)
        
#         img.save(out_path, format="PNG", optimize=True)
#         return True
#     except requests.RequestException:
#         return False

def _download_vector_map(lat: float, lng: float, out_path: str) -> bool:
    token = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()
    if not token:
        return False

    # Switch to 'outdoors-v12' for green grass and distinct buildings
    # Zoom level increased to 16.5 to make buildings pop
    url = (
        "https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/static/"
        f"{lng},{lat},16.5,0,0/1050x570?access_token={token}"
    )
    
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        img = Image.open(io.BytesIO(response.content)).convert("RGB")
        # Crop the Mapbox watermark logo at the bottom
        img = img.crop((0, 0, 1050, 545)) 
        
        img.save(out_path, format="PNG", optimize=True)
        return True
    except requests.RequestException:
        return False


# def generate_report_images(location: str, output_dir: str) -> dict[str, str]:
#     lat, lng = _parse_location(location)

#     satellite_path = str(Path(output_dir) / "satellite.png")
#     qgis_path = str(Path(output_dir) / "qgis_mock.png")

#     mapbox_ok = _download_mapbox_image(lat, lng, satellite_path)
#     if not mapbox_ok:
#         _capture_with_playwright(lat, lng, satellite_path)

#     _compose_qgis_mock(satellite_path, qgis_path, lat, lng, location)
#     return {"satellite": satellite_path, "qgis": qgis_path, "latitude": f"{lat:.6f}", "longitude": f"{lng:.6f}"}


import base64

def _image_to_base64(image_path: str) -> str:
    """Reads a saved image from disk and converts it to a base64 string."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")



def generate_report_images(location: str, temp_dir: str) -> tuple[str, str, str]:
    # 1. Geocode the location
    lat, lng = _parse_location(location)

    # File paths for saving temporary images
    sat_path = os.path.join(temp_dir, "satellite.png")
    qgis_path = os.path.join(temp_dir, "qgis_mock.png")
    vector_path = os.path.join(temp_dir, "vector_map.png")
    layout_path = os.path.join(temp_dir, "final_layout.png")

    # 2. Download Base Maps
    if not _download_mapbox_image(lat, lng, sat_path):
        raise ScreenshotEngineError("Failed to download satellite imagery")
        
    if not _download_vector_map(lat, lng, vector_path):
        raise ScreenshotEngineError("Failed to download vector imagery")

    # 3. Compose Templates
    _compose_qgis_mock(sat_path, qgis_path, lat, lng, location)
    _compose_final_layout(vector_path, layout_path, lat, lng, location)

    # 4. Convert all 3 final images to Base64 to inject into HTML
    sat_b64 = _image_to_base64(sat_path)
    qgis_b64 = _image_to_base64(qgis_path)
    layout_b64 = _image_to_base64(layout_path)

    return sat_b64, qgis_b64, layout_b64
