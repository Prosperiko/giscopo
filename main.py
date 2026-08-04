import base64
import io
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any
import time


import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from mailer import EmailPayload, MailerError, send_report_email
from pdf_engine import PDFGenerationError, build_report_pdf
from screenshot_engine import ScreenshotEngineError, generate_report_images
import os
import json
from openai import OpenAI




logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("giscopo")

PAYSTACK_VERIFY_URL = "https://api.paystack.co/transaction/verify/{reference}"
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")

app = FastAPI(title="GISCOPO Report Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")






















class ReportRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    student_id: str = Field(min_length=2, max_length=60)
    department: str = Field(min_length=2, max_length=120)
    email: EmailStr
    location: str = Field(min_length=2, max_length=200)
    coordinates: str = Field(default="", max_length=100)
    payment_reference: str = Field(min_length=6, max_length=120)

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("full_name", "student_id", "department", "location")
    @classmethod
    def block_control_chars(cls, value: str) -> str:
        if any(ord(ch) < 32 for ch in value):
            raise ValueError("Invalid characters in input")
        return value


class JobStatus(BaseModel):
    status: str
    message: str
    updated_at: str


JOB_STATE: dict[str, JobStatus] = {}








import json
from pathlib import Path



REFS_FILE = Path("processed_refs.json")

def _load_processed_refs() -> set[str]:
    if REFS_FILE.exists():
        return set(json.loads(REFS_FILE.read_text()))
    return set()

def _save_processed_refs(refs: set[str]) -> None:
    REFS_FILE.write_text(json.dumps(list(refs)))
    
PROCESSED_REFS = _load_processed_refs()

    
    
    
def _set_job_state(job_id: str, status: str, message: str) -> None:
    JOB_STATE[job_id] = JobStatus(
        status=status,
        message=message,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )




def verify_paystack_payment(reference: str) -> dict[str, Any]:
    if not PAYSTACK_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Paystack secret is not configured")

    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    
    try:
        response = requests.get(
            PAYSTACK_VERIFY_URL.format(reference=reference),
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        logger.exception(f"Paystack verification failed for reference: {reference}")
        raise HTTPException(status_code=502, detail="Payment provider unavailable") from exc

    data: dict[str, Any] = payload.get("data") or {}
    status = (data.get("status") or "").strip().lower()
    
    # FIX 1: Provide a default fallback of 0 so `amount` is never None. 
    # If `amount` is None, `None < 245000` will crash the server with a TypeError.
    amount = data.get("amount") or 0

    if status != "success":
        raise HTTPException(status_code=402, detail="Payment not successful")
        
    # Prefer to read the expected amount from an environment variable so deployments
    # can tune price without changing code. Default to the common kobo value
    # (₦2,450.00 -> 245000) used elsewhere in comments if not provided.
    try:
        EXPECTED_AMOUNT_KOBO = int(os.getenv("PAYSTACK_EXPECTED_AMOUNT_KOBO", "245000"))
    except Exception:
        EXPECTED_AMOUNT_KOBO = 245000

    # Require at least the expected amount (allow small overpayment due to fees)
    if amount < EXPECTED_AMOUNT_KOBO:
        # 400 Bad Request is correct here
        raise HTTPException(status_code=400, detail=f"Incorrect payment amount. Expected at least {EXPECTED_AMOUNT_KOBO} kobo, got {amount} kobo.")
    
    
    
    # Log the metadata so you can see it in your server logs too
    metadata = data.get("metadata") or {}
    logger.info("Paystack metadata for %s: %s", reference, json.dumps(metadata))
    
    return data






def _process_report(job_id: str, request: ReportRequest) -> None:
    _set_job_state(job_id, "processing", "Generating screenshots")

    
    
    try:
        with tempfile.TemporaryDirectory(prefix="giscopo-") as temp_dir:
            # ONLY CALL THIS ONCE
            # Since the updated function already handles the base64 conversion, 
            # we just unpack the three strings directly!
            coords_to_use = request.coordinates if request.coordinates else request.location
            sat_b64, qgis_b64, final_layout_b64 = generate_report_images(coords_to_use, request.location, temp_dir)

        # 1. Generate the unique, personalized text via GitHub Models
        _set_job_state(job_id, "processing", "AI generating academic content...")
        
        dynamic_text = generate_dynamic_sections(request.location, request.department)

        # 2. Build the PDF, injecting both the images and the new AI text
        _set_job_state(job_id, "processing", "Compiling PDF report...")
        pdf_bytes = build_report_pdf(
            {
                "full_name": request.full_name,
                "student_id": request.student_id,
                "department": request.department,
                "location": request.location,
                "generated_date": datetime.now(timezone.utc).strftime("%d %B %Y"),
                "satellite_image_b64": sat_b64,
                "qgis_image_b64": qgis_b64,
                "final_layout_b64": final_layout_b64,
                # INJECT THE DYNAMIC AI SECTIONS HERE:
                "overview": dynamic_text.get("overview", ""),
                "data_description": dynamic_text.get("data_description", ""),
                "methodology": dynamic_text.get("methodology", ""),
                "discussion": dynamic_text.get("discussion", ""),
                "conclusion": dynamic_text.get("conclusion", ""),
            }
        )

        _set_job_state(job_id, "processing", "Sending report email")
        logger.info("About to send email to %s via provider %s", 
                    request.email, 
                    os.getenv("MAIL_PROVIDER", "NOT SET"))
        send_report_email(
            EmailPayload(
                recipient=request.email,
                subject=f"Your GIS Academic Report - {request.location}",
                body=(
                    f"Hello {request.full_name},\n\n"
                    "Attached is your personalized GIS report in PDF format.\n\n"
                    "Regards,\nGISCOPO Team"
                ),
                attachment_filename="gis_report.pdf",
                attachment_bytes=pdf_bytes,
            )
        )
    except (ScreenshotEngineError, PDFGenerationError, MailerError) as exc:
        logger.exception("Pipeline failed for job %s", job_id)
        _set_job_state(job_id, "failed", str(exc))
        return
    except Exception as exc:  # pragma: no cover - fallback handler
        logger.exception("Unexpected pipeline failure for job %s", job_id)
        _set_job_state(job_id, "failed", "Unexpected error occurred")
        return

    _set_job_state(job_id, "completed", "Report generated and delivered")



@app.get("/")
def get_index() -> FileResponse:
    return FileResponse("static/index.html")


@app.get("/api/paystack-config")
def get_paystack_config() -> dict[str, str]:
    if not PAYSTACK_PUBLIC_KEY:
        raise HTTPException(status_code=500, detail="Paystack public key is not configured")
    return {"public_key": PAYSTACK_PUBLIC_KEY}











# @app.post("/api/generate-report")
# def generate_report(payload: ReportRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
#     verify_paystack_payment(payload.payment_reference, payload.email)

#     job_id = str(uuid.uuid4())
#     _set_job_state(job_id, "queued", "Report request accepted")
#     background_tasks.add_task(_process_report, job_id, payload)

#     return {
#         "job_id": job_id,
#         "status": "queued",
#         "message": "Payment verified. Your report is being prepared and will be sent via email shortly.",
#     }

# @app.post("/api/generate-report")
# def generate_report(payload: ReportRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    
#     # Bypass Paystack during local backend testing
#     if payload.payment_reference != "test_bypass":
#         verify_paystack_payment(payload.payment_reference, payload.email)

#     job_id = str(uuid.uuid4())
#     _set_job_state(job_id, "queued", "Report request accepted")
#     background_tasks.add_task(_process_report, job_id, payload)

#     return {
#         "job_id": job_id,
#         "status": "queued",
#         "message": "Payment verified. Your report is being prepared and will be sent via email shortly.",
#     }


@app.post("/api/generate-report")
def generate_report(payload: ReportRequest) -> dict[str, str]:
    
    # Bypass Paystack during local backend testing
    
    # 🔒 BLOCK DUPLICATE REFERENCES IMMEDIATELY
    if payload.payment_reference in PROCESSED_REFS:
        logger.warning("Duplicate request blocked for reference: %s", payload.payment_reference)
        raise HTTPException(status_code=409, detail="This payment has already been processed. Check your email.")
    
    if payload.payment_reference in PROCESSED_REFS:
        raise HTTPException(status_code=409, detail="This payment has already been processed. Check your email.")
    
    payment_data = None
    if payload.payment_reference != "test_bypass":
        # Verify payment and grab the provider response so we can log and check
        payment_data = verify_paystack_payment(payload.payment_reference)
        paid_email = ((payment_data.get("customer") or {}).get("email") or "").strip().lower()
        amount = payment_data.get("amount", 0)
        logger.info("Paystack verification success reference=%s paid_email=%s amount=%s", payload.payment_reference, paid_email, amount)

        # Allow mismatches (e.g., paying with personal email, receiving on school email)
        if paid_email and paid_email != payload.email.lower():
            logger.info("Email mismatch noted: Paid with %s, delivering to %s", paid_email, payload.email)

    PROCESSED_REFS.add(payload.payment_reference)
    _save_processed_refs(PROCESSED_REFS)

    job_id = str(uuid.uuid4())
    _set_job_state(job_id, "queued", "Report request accepted")
    # background_tasks.add_task(_process_report, job_id, payload)
    _process_report(job_id, payload)

    
    
    return {
        "job_id": job_id,
        "status": "completed",
        "message": "Payment verified. Your report is beFing prepared and will be sent via email shortly.",
    }



@app.get("/api/report-status/{job_id}", response_model=JobStatus)
def report_status(job_id: str) -> JobStatus:
    status = JOB_STATE.get(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job ID not found")
    return status


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}




GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_TOKEN
    
)



# Point the standard OpenAI client to the free GitHub Models endpoint
client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.getenv("GITHUB_TOKEN"),
)

# def generate_dynamic_sections(location: str, department: str) -> dict[str, str]:
#     # We explicitly ask the LLM to write the 5 text-heavy sections from your outline
#     prompt = (
#         f"You are an academic assistant helping a {department} student write a GIS report for {location}. "
#         "Generate realistic, academic content for a spatial analysis project. "
#         "Return the response in strict JSON format with these exact keys: "
#         "'overview', 'data_description', 'methodology', 'discussion', 'conclusion'."
#     )

#     try:
#         response = client.chat.completions.create(
#             model="gpt-4o-mini", # High-tier model, completely free via GitHub!
#             messages=[
#                 {"role": "system", "content": "You are a GIS assistant that outputs strict JSON."},
#                 {"role": "user", "content": prompt}
#             ],
#             response_format={ "type": "json_object" },
#             temperature=0.7,
#             timeout=15
#         )
        
#         # Parse the JSON string returned by the model into a standard Python dictionary
#         raw_text = response.choices[0].message.content
#         return json.loads(raw_text)

#     except Exception as e:
#         print(f"GitHub Models API failed: {e}")
#         # The Fallback: If the API fails, return safe, generic text so the PDF still builds
#         return {
#             "overview": f"This project provides a spatial overview of {location} to demonstrate GIS mapping techniques.",
#             "data_description": "Data was sourced via high-resolution satellite imagery and processed for spatial clarity.",
#             "methodology": "The methodology involved capturing coordinate-referenced imagery and overlaying it within a QGIS workspace.",
#             "discussion": "The visual results indicate clear delineations in land use and structural density across the study area.",
#             "conclusion": "The project successfully achieved the integration of geospatial visualization and remote sensing interpretation."
#         }
        
        
# def generate_dynamic_sections(location: str, department: str) -> dict[str, str]:
#     # The upgraded prompt forces length, technical depth, and specific GIS terminology
#     prompt = (
#         f"You are a senior academic assistant helping a {department} student write a comprehensive GIS report for {location}. "
#         "The report must be highly technical, lengthy, and strictly academic. "
#         "Ensure the text reflects rigorous spatial database methodology, suitable for university-level engineering or geomatics standards. "
#         "You MUST include specific technical terminology where appropriate (e.g., WGS 84, UTM coordinate systems, Ground Control Points, vector layer topologies, digitization scales, and snapping tolerances). "
#         "Each section must be detailed and substantial (at least 100 words per section). "
#         "Return the response in strict JSON format with these exact keys: "
#         "'overview', 'data_description', 'methodology', 'discussion', 'conclusion'."
#     )

#     try:
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[
#                 {"role": "system", "content": "You are a GIS assistant that outputs strict JSON."},
#                 {"role": "user", "content": prompt}
#             ],
#             response_format={ "type": "json_object" },
#             temperature=0.7, # Keeps the writing structured but allows for creative vocabulary
#             timeout=15
#         )
        
#         raw_text = response.choices[0].message.content
#         return json.loads(raw_text)

#     except Exception as e:
#         print(f"GitHub Models API failed: {e}")
#         # Safe fallback with slightly longer generic text
#         return {
#             "overview": f"This project focuses on building a highly precise, georeferenced 2D vector GIS database for {location}. As the area expands with new infrastructure, traditional static maps can no longer keep up with spatial planning needs. This project solves that limitation by converting high-resolution satellite imagery into a dynamic, organized spatial database.",
#             "data_description": "The dataset utilizes high-resolution satellite imagery as its primary raster base map. To ensure real-world accuracy for distance and area measurements, all layers are projected to a localized UTM coordinate system. The spatial data is structured into primary vector layers including polygons for footprints, lines for transit networks, and points for utilities.",
#             "methodology": "Prominent, permanent landmarks were identified to serve as Ground Control Points (GCPs). The raw satellite imagery was aligned using a Polynomial transformation with a Nearest Neighbor resampling method. During digitization, advanced snapping options were enabled to eliminate spatial gaps and overlapping boundaries, capturing features at a sharp scale.",
#             "discussion": "The final output is a topologically sound, fully queryable GIS database. The dataset reveals distinct spatial patterns, dense core structures, and a hierarchical road network. Visual differentiation suggests zones of residential concentration and transportation corridors. All spatial vectors are directly linked to their corresponding descriptive data.",
#             "conclusion": "The digitization and spatial analysis were successfully completed using open-source GIS software. By linking physical geography with detailed descriptive attributes, the project transitions spatial records from static imagery into an intelligent database, providing reliable educational outputs for academic submissions."
#         }
        
# def generate_dynamic_sections(location: str, department: str) -> dict[str, str]:
#     # The Mega-Prompt: Forces the AI to write exhaustive, lengthy, highly technical content
#     prompt = (
#         f"You are a senior academic assistant helping a {department} student write an exhaustive, highly technical GIS report for {location}. "
#         "Your primary directive is LENGTH and DEPTH. You must write at least 300 to 400 words for EVERY SINGLE SECTION to ensure it fills an entire A4 page. "
#         "Expand heavily on theoretical backgrounds, practical implications, civil engineering considerations, and geomatics methodologies. "
#         "In the 'overview', discuss the history of urbanization and infrastructure sprawl in the area. "
#         "In 'data_description', thoroughly detail raster resolution, coordinate systems (WGS 84, UTM Zone 31N), and database schema topologies. "
#         "In 'methodology', explain the exact step-by-step algorithms for georeferencing, Polynomial 1 transformations, Nearest Neighbor resampling, and advanced digitizing topology rules (snapping tolerances, avoiding dangles). "
#         "In 'discussion', extensively analyze spatial patterns, road network hierarchies, and land-use distribution. "
#         "Return the response in strict JSON format with these exact keys: "
#         "'overview', 'data_description', 'methodology', 'discussion', 'conclusion'."
#     )

#     try:
#         response = client.chat.completions.create(
#             model="gpt-4o",
#             messages=[
#                 {"role": "system", "content": "You are a senior GIS academic writer that outputs strict JSON. You prioritize long, exhaustive, highly detailed paragraph generation."},
#                 {"role": "user", "content": prompt}
#             ],
#             response_format={ "type": "json_object" },
#             temperature=0.7, 
#             timeout=30 # Increased timeout since it is generating much more text!
#         )
        
#         raw_text = response.choices[0].message.content
#         return json.loads(raw_text)

#     except Exception as e:
#         print(f"GitHub Models API failed: {e}")
#         # Make sure your fallback text is also longer just in case!
#         return {
#             "overview": f"This project focuses on building a highly precise, georeferenced 2D vector GIS database for {location}. As the area expands with new infrastructure, traditional static maps can no longer keep up with spatial planning needs. This project solves that limitation by converting high-resolution satellite imagery into a dynamic, organized spatial database.",
#             "data_description": "The dataset utilizes high-resolution satellite imagery as its primary raster base map. To ensure real-world accuracy for distance and area measurements, all layers are projected to a localized UTM coordinate system. The spatial data is structured into primary vector layers including polygons for footprints, lines for transit networks, and points for utilities.",
#             "methodology": "Prominent, permanent landmarks were identified to serve as Ground Control Points (GCPs). The raw satellite imagery was aligned using a Polynomial transformation with a Nearest Neighbor resampling method. During digitization, advanced snapping options were enabled to eliminate spatial gaps and overlapping boundaries, capturing features at a sharp scale.",
#             "discussion": "The final output is a topologically sound, fully queryable GIS database. The dataset reveals distinct spatial patterns, dense core structures, and a hierarchical road network. Visual differentiation suggests zones of residential concentration and transportation corridors. All spatial vectors are directly linked to their corresponding descriptive data.",
#             "conclusion": "The digitization and spatial analysis were successfully completed using open-source GIS software. By linking physical geography with detailed descriptive attributes, the project transitions spatial records from static imagery into an intelligent database, providing reliable educational outputs for academic submissions."
#         }
        

# GitHub Copilot — using GPT-5 mini

# Apply this replacement for generate_dynamic_sections to add logging, retries, robust parsing and clear fallbacks.


# # ...existing code...
# def generate_dynamic_sections(location: str, department: str) -> dict[str, str]:
#     model_name = os.getenv("MODEL_NAME", "gpt-4o")
#     token = os.getenv("GITHUB_TOKEN") or os.getenv("OPENAI_API_KEY")
#     if not token:
#         logger.error("Model token not set (GITHUB_TOKEN/OPENAI_API_KEY)")
#         return {
#             "overview": f"Fallback overview for {location}.",
#             "data_description": "Fallback data description.",
#             "methodology": "Fallback methodology.",
#             "discussion": "Fallback discussion.",
#             "conclusion": "Fallback conclusion.",
#         }

#     prompt = (
#         f"You are a senior academic assistant helping a {department} student write a GIS report for {location}. "
#         "Return a JSON object with keys: 'overview','data_description','methodology','discussion','conclusion'."
#     )

#     last_exc = None
#     for attempt in range(1, 4):
#         try:
#             logger.info("Model call attempt=%d model=%s location=%s", attempt, model_name, location)
#             response = client.chat.completions.create(
#                 model=model_name,
#                 messages=[
#                     {"role": "system", "content": "You are a GIS assistant that outputs strict JSON."},
#                     {"role": "user", "content": prompt},
#                 ],
#                 response_format={"type": "json_object"},
#                 temperature=0.7,
#                 timeout=30,
#             )

#             # Defensive extraction of returned content
#             content = None
#             try:
#                 content = response.choices[0].message.content
#             except Exception:
#                 try:
#                     content = getattr(response.choices[0].message, "content", None)
#                 except Exception:
#                     content = None

#             # fallback extraction variants
#             if not content:
#                 try:
#                     content = getattr(response.choices[0], "text", None)
#                 except Exception:
#                     content = None

#             if isinstance(content, dict):
#                 return content

#             if isinstance(content, str) and content.strip():
#                 try:
#                     parsed = json.loads(content)
#                     if isinstance(parsed, dict):
#                         return parsed
#                 except json.JSONDecodeError:
#                     logger.warning("Model returned non-JSON text on attempt %d: %s", attempt, content[:200])

#             # As a last try, if the client has a dict representation with usable output:
#             try:
#                 as_dict = response.to_dict() if hasattr(response, "to_dict") else None
#                 if as_dict:
#                     # look for common shapes
#                     for key in ("output", "message", "choices"):
#                         if key in as_dict and isinstance(as_dict[key], dict):
#                             return as_dict[key]
#             except Exception:
#                 pass

#             raise ValueError("No valid JSON content from model")

#         except Exception as exc:
#             last_exc = exc
#             logger.exception("Model call failed (attempt %d): %s", attempt, exc)
#             time.sleep(2 ** (attempt - 1))

#     logger.error("All model attempts failed: %s", last_exc)
#     return {
#         "overview": f"Fallback overview for {location}.",
#         "data_description": "Fallback data description.",
#         "methodology": "Fallback methodology.",
#         "discussion": "Fallback discussion.",
#         "conclusion": "Fallback conclusion.",
#     }
# # ...existing code...
# ```

# If this still falls back, paste the last exception lines from your app logs (the logger.exception output) and I’ll analyze them.


import os
import json
import logging
from openai import OpenAI

# # 1. Initialize the Groq Client (using the OpenAI SDK)
# GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# client = OpenAI(
#     base_url="https://api.groq.com/openai/v1",
#     api_key=GROQ_API_KEY
# )

# def generate_dynamic_sections(location: str, department: str) -> dict[str, str]:
#     """
#     Generates dynamic, highly technical GIS report sections using Groq.
#     Forces extreme length (90+ words per section) for massive PDFs.
#     """
    
#     if not GROQ_API_KEY:
#         logging.error("GROQ_API_KEY is missing. Falling back to default text.")
#         return _get_fallback_text(location)

#     # The Mega-Prompt: Cranked up to force 90 to 100+ words per section
#     prompt = (
#         f"You are a senior academic assistant helping a {department} student write an exhaustive, highly technical GIS report for {location}. "
#         "Your primary directive is EXTREME LENGTH and DEPTH. You MUST write at least 200 words for EVERY SINGLE SECTION. Do not write short summaries. "
#         "Expand heavily on theoretical backgrounds, practical implications, civil engineering considerations, and geomatics methodologies. "
#         "In the 'overview', discuss the extensive history of urbanization, infrastructure sprawl, and spatial planning challenges in the area. "
#         "In 'data_description', thoroughly detail raster resolution, coordinate systems (WGS 84, UTM Zone 31N), and complex database schema topologies. "
#         "In 'methodology', explain the exact step-by-step algorithms for georeferencing, Polynomial 1 transformations, Nearest Neighbor resampling, and advanced digitizing topology rules (snapping tolerances, avoiding dangles). "
#         "In 'discussion', extensively analyze spatial patterns, road network hierarchies, and land-use distribution over multiple long paragraphs. "
#         "Return the response in strict JSON format with exactly these 5 keys: "
#         "'overview', 'data_description', 'methodology', 'discussion', 'conclusion'."
#     )
#     # List your models in order of preference
#     models_to_try = [
#         "llama-3.3-70b-versatile", # 1st Choice: Smartest
#         "llama-3.1-8b-instant"     # 2nd Choice: Massive daily limits, great fallback
#     ]

#     for model_name in models_to_try:
#         try:
#             logging.info(f"Generating report for {location} using Groq model: {model_name}...")
            
#             response = client.chat.completions.create(
#                 model=model_name,
#                 messages=[
#                     {"role": "system", "content": "You are a senior GIS academic writer that outputs strict JSON. You prioritize long, exhaustive paragraph generation."},
#                     {"role": "user", "content": prompt}
#                 ],
#                 response_format={ "type": "json_object" },
#                 temperature=0.7, 
#                 timeout=60, 
#                 max_tokens=4096
#             )
            
#             raw_text = response.choices[0].message.content
#             return json.loads(raw_text)

#         except Exception as e:
#             # If a model fails, log a warning and let the loop try the next one in the list
#             logging.warning(f"Groq API failed with {model_name}: {e}. Switching to next model...")
            
#     # If the loop finishes and ALL models failed, use the hardcoded text
#     logging.error("All Groq models failed. Falling back to default text.")
#     return _get_fallback_text(location)


import os
import json
import logging
import time
import random
from openai import OpenAI

# 1. Initialize the Groq Client
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)

# 2. Initialize the Fallback Client (GitHub Models)
# This handles the scenario where the entire Groq API is unresponsive
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
fallback_client = OpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=GITHUB_TOKEN
)

# def generate_dynamic_sections(location: str, department: str) -> dict[str, str]:
#     """
#     Generates dynamic, highly technical GIS report sections using Groq.
#     Falls back to GitHub Models if Groq fails, then to default text.
#     Forces extreme length (90+ words per section) for massive PDFs.
#     """
    
#     if not GROQ_API_KEY and not GITHUB_TOKEN:
#         logging.error("No API keys found. Falling back to default text.")
#         return _get_fallback_text(location)

#     # The Mega-Prompt
#     prompt = (
#         f"You are a senior academic assistant helping a {department} student write an exhaustive, highly technical GIS report for {location}. "
#         "Your primary directive is EXTREME LENGTH and DEPTH. You MUST write at least 200 words for EVERY SINGLE SECTION. Do not write short summaries. "
#         "Expand heavily on theoretical backgrounds, practical implications, civil engineering considerations, and geomatics methodologies. "
#         "In the 'overview', discuss the extensive history of urbanization, infrastructure sprawl, and spatial planning challenges in the area. "
#         "In 'data_description', thoroughly detail raster resolution, coordinate systems (WGS 84, UTM Zone 31N), and complex database schema topologies. "
#         "In 'methodology', explain the exact step-by-step algorithms for georeferencing, Polynomial 1 transformations, Nearest Neighbor resampling, and advanced digitizing topology rules (snapping tolerances, avoiding dangles). "
#         "In 'discussion', extensively analyze spatial patterns, road network hierarchies, and land-use distribution over multiple long paragraphs. "
#         "Return the response in strict JSON format with exactly these 5 keys: "
#         "'overview', 'data_description', 'methodology', 'discussion', 'conclusion'."
#     )

#     # List your models in order of preference: (provider_name, model_name, client_instance)
#     models_to_try = [
#         ("Groq", "llama-3.3-70b-versatile", groq_client), # 1st Choice: Smartest
#         ("Groq", "llama-3.1-8b-instant", groq_client),    # 2nd Choice: Massive daily limits
#         ("GitHub", "gpt-4o", fallback_client)             # 3rd Choice: Ultimate fallback provider
#     ]

#     max_retries = 2
#     base_delay = 1.0

#     for provider, model_name, current_client in models_to_try:
#         # Skip if the required token for this specific provider is missing
#         if provider == "Groq" and not GROQ_API_KEY:
#             continue
#         if provider == "GitHub" and not GITHUB_TOKEN:
#             continue

#         for attempt in range(max_retries):
#             try:
#                 logging.info(f"Attempt {attempt + 1} for {location} using {provider} model: {model_name}...")
                
#                 response = current_client.chat.completions.create(
#                     model=model_name,
#                     messages=[
#                         {"role": "system", "content": "You are a senior GIS academic writer that outputs strict JSON. You prioritize long, exhaustive paragraph generation."},
#                         {"role": "user", "content": prompt}
#                     ],
#                     response_format={ "type": "json_object" },
#                     temperature=0.7, 
#                     timeout=60, 
#                     max_tokens=4096
#                 )
                
#                 raw_text = response.choices[0].message.content
#                 return json.loads(raw_text)

#             except Exception as e:
#                 logging.warning(f"Error with {provider} ({model_name}) on attempt {attempt + 1}: {e}")
                
#                 if attempt < max_retries - 1:
#                     # Exponential backoff with jitter
#                     sleep_time = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
#                     logging.info(f"Backing off for {sleep_time:.2f}s before next attempt...")
#                     time.sleep(sleep_time)
        
#         logging.warning(f"Exhausted all retries for {model_name}. Switching to next model in queue...")

#     # If the loop finishes and ALL models/providers failed
#     logging.error("CRITICAL: All AI models and fallback providers failed. Falling back to default text.")
#     return _get_fallback_text(location)


import os
import json
import logging
import time
import random
import cohere
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# 1. Initialize the Groq Client
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
groq_client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)

# 2. Initialize the Fallback Client (Cohere)
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
cohere_client = cohere.ClientV2(COHERE_API_KEY) if COHERE_API_KEY else None

def generate_dynamic_sections(location: str, department: str) -> dict[str, str]:
    """
    Generates dynamic, highly technical GIS report sections using Groq.
    Falls back to Cohere if Groq fails, then to default text.
    Forces extreme length (90+ words per section) for massive PDFs.
    """
    
    if not GROQ_API_KEY and not COHERE_API_KEY:
        logging.error("No API keys found. Falling back to default text.")
        return _get_fallback_text(location)

    # The Mega-Prompt
    prompt = (
        f"You are a senior academic assistant helping a {department} student write an exhaustive, highly technical GIS report for {location}. "
        "Your primary directive is EXTREME LENGTH and DEPTH. You MUST write at least 100 words and no more than 200 words for EVERY SINGLE SECTION. Do not write short summaries. "
        "Do not write less than 90 words under any circumstances. Keep the content dense and highly technical, consisting of exactly 4 to 6 long sentences per section, focusing on theoretical backgrounds and geomatics methodologies without unnecessary filler. "

        "Expand heavily on theoretical backgrounds, practical implications, civil engineering considerations, and geomatics methodologies. "
        "In the 'overview', discuss the extensive history of urbanization, infrastructure sprawl, and spatial planning challenges in the area. "
        "In 'data_description', thoroughly detail raster resolution, coordinate systems (WGS 84, UTM Zone 31N), and complex database schema topologies. "
        "In 'methodology', explain the exact step-by-step algorithms for georeferencing, Polynomial 1 transformations, Nearest Neighbor resampling, and advanced digitizing topology rules (snapping tolerances, avoiding dangles). "
        "In 'discussion', extensively analyze spatial patterns, road network hierarchies, and land-use distribution over multiple long paragraphs. "
        "Return the response in strict JSON format with exactly these 5 keys: "
        "'overview', 'data_description', 'methodology', 'discussion', 'conclusion'."
    )

    max_retries = 3
    base_delay = 1.0

    # --- PRIMARY ATTEMPT: GROQ ---
    if GROQ_API_KEY:
        groq_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
        
        for model_name in groq_models:
            for attempt in range(max_retries):
                try:
                    logging.info(f"Attempt {attempt + 1} for {location} using Groq model: {model_name}...")
                    
                    response = groq_client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": "You are a senior GIS academic writer that outputs strict JSON. You prioritize long, exhaustive paragraph generation."},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={ "type": "json_object" },
                        temperature=0.7, 
                        timeout=60, 
                        max_tokens=4096
                    )
                    
                    raw_text = response.choices[0].message.content
                    return json.loads(raw_text)

                except Exception as e:
                    logging.warning(f"Error with Groq ({model_name}) on attempt {attempt + 1}: {e}")
                    
                    if attempt < max_retries - 1:
                        # Exponential backoff with jitter
                        sleep_time = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
                        logging.info(f"Backing off for {sleep_time:.2f}s before next attempt...")
                        time.sleep(sleep_time)
            
            logging.warning(f"Exhausted all retries for {model_name}. Switching to next Groq model...")

    # --- FALLBACK ATTEMPT: COHERE ---
    if COHERE_API_KEY and cohere_client:
        logging.info("Switching to Ultimate Fallback: Cohere (command-r-plus)...")
        try:
            # Cohere V2 SDK usage
            response = cohere_client.chat(
                model="command-r-plus-08-2024", # Cohere's flagship model
                messages=[
                    {
                        "role": "user", 
                        "content": prompt + "\n\nCRITICAL: You must wrap your entire response in valid JSON format."
                    }
                ],
                temperature=0.7
            )
            
            # Cohere V2 returns text inside response.message.content[0].text
            raw_text = response.message.content[0].text
            
            # Clean up potential markdown formatting (```json ... ```)
            if raw_text.startswith("```json"):
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1].split("```")[0].strip()
                
            return json.loads(raw_text)
            
        except Exception as e:
            logging.error(f"Cohere fallback also failed: {e}")

    # If all models/providers failed
    logging.error("CRITICAL: All AI models failed. Falling back to default text.")
    return _get_fallback_text(location)





def _get_fallback_text(location: str) -> dict[str, str]:
    """Helper function to keep the main function clean if Groq fails."""
    return {
        "overview": f"This project focuses on building a highly precise, georeferenced 2D vector GIS database for {location}. As the area expands with new infrastructure, traditional static maps can no longer keep up with spatial planning needs. This project solves that limitation by converting high-resolution satellite imagery into a dynamic, organized spatial database.",
        "data_description": "The dataset utilizes high-resolution satellite imagery as its primary raster base map. To ensure real-world accuracy for distance and area measurements, all layers are projected to a localized UTM coordinate system. The spatial data is structured into primary vector layers including polygons for footprints, lines for transit networks, and points for utilities.",
        "methodology": "Prominent, permanent landmarks were identified to serve as Ground Control Points (GCPs). The raw satellite imagery was aligned using a Polynomial transformation with a Nearest Neighbor resampling method. During digitization, advanced snapping options were enabled to eliminate spatial gaps and overlapping boundaries, capturing features at a sharp scale.",
        "discussion": "The final output is a topologically sound, fully queryable GIS database. The dataset reveals distinct spatial patterns, dense core structures, and a hierarchical road network. Visual differentiation suggests zones of residential concentration and transportation corridors. All spatial vectors are directly linked to their corresponding descriptive data.",
        "conclusion": "The digitization and spatial analysis were successfully completed using open-source GIS software. By linking physical geography with detailed descriptive attributes, the project transitions spatial records from static imagery into an intelligent database, providing reliable educational outputs for academic submissions."
    }



      
import requests
import threading
def keep_alive():
    while True:
        try:
            url = "https://giscopo.onrender.com/"  # Replace with your actual Render URL
            res = requests.get(url)
            print(f"Pinged at {time.ctime()}: Status {res.status_code}")
        except Exception as e:
            print(f"Error pinging at {time.ctime()}: {e}")
        time.sleep(60 * 12)  # Ping every 14 minutes

# # Create and start the background thread
t = threading.Thread(target=keep_alive)
t.daemon = True
t.start()