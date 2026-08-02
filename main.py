import base64
import io
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from typing import Any

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
import time

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


def _set_job_state(job_id: str, status: str, message: str) -> None:
    JOB_STATE[job_id] = JobStatus(
        status=status,
        message=message,
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


def verify_paystack_payment(reference: str, expected_email: str) -> None:
    if not PAYSTACK_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Paystack secret is not configured")

    headers = {"Authorization": "Bearer " + PAYSTACK_SECRET_KEY}
    try:
        response = requests.get(
            PAYSTACK_VERIFY_URL.format(reference=reference),
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        logger.exception("Paystack verification failed")
        raise HTTPException(status_code=502, detail="Payment provider unavailable") from exc

    data: dict[str, Any] = payload.get("data") or {}
    paid_email = ((data.get("customer") or {}).get("email") or "").strip().lower()
    status = (data.get("status") or "").strip().lower()

    if status != "success":
        raise HTTPException(status_code=402, detail="Payment not successful")
    if paid_email and paid_email != expected_email.lower():
        raise HTTPException(status_code=400, detail="Payment record does not match provided email")
    
    amount = data.get("amount")

    if status != "success":
        raise HTTPException(status_code=402, detail="Payment not successful")
    if paid_email and paid_email != expected_email.lower():
        raise HTTPException(status_code=400, detail="Payment record does not match provided email")
    # Lock the price to exactly ₦2490 (which is 249000 kobo)
    if amount != 249000:
        raise HTTPException(status_code=400, detail="Incorrect payment amount")


# def _process_report(job_id: str, request: ReportRequest) -> None:
#     _set_job_state(job_id, "processing", "Generating screenshots")

#     try:
#         with tempfile.TemporaryDirectory(prefix="giscopo-") as temp_dir:
#             images = generate_report_images(request.location, temp_dir)

#             _set_job_state(job_id, "processing", "Compiling PDF report")
#             with open(images["satellite"], "rb") as sat_file, open(images["qgis"], "rb") as qgis_file:
#                 sat_b64 = base64.b64encode(sat_file.read()).decode("utf-8")
#                 qgis_b64 = base64.b64encode(qgis_file.read()).decode("utf-8")

                
#                 # Unpack all 3 images
#                 sat_b64, qgis_b64, final_layout_b64 = generate_report_images(request.location, temp_dir)
            

#             # 1. Generate the unique, personalized text via GitHub Models
#             _set_job_state(job_id, "processing", "AI generating academic content...")
#             dynamic_text = generate_dynamic_sections(request.location, request.department)

            
#             # 2. Build the PDF, injecting both the images and the new AI text
#             _set_job_state(job_id, "processing", "Compiling PDF report...")
#             pdf_bytes = build_report_pdf(
#                 {
#                     "full_name": request.full_name,
#                     "student_id": request.student_id,
#                     "department": request.department,
#                     "location": request.location,
#                     "generated_date": datetime.now(timezone.utc).strftime("%d %B %Y"),
#                     "satellite_image_b64": sat_b64,
#                     "qgis_image_b64": qgis_b64,
#                     "final_layout_b64": final_layout_b64,
#                     # INJECT THE DYNAMIC AI SECTIONS HERE:
#                     "overview": dynamic_text.get("overview", ""),
#                     "data_description": dynamic_text.get("data_description", ""),
#                     "methodology": dynamic_text.get("methodology", ""),
#                     "discussion": dynamic_text.get("discussion", ""),
#                     "conclusion": dynamic_text.get("conclusion", ""),
#                 }
#             )

#             # pdf_bytes = build_report_pdf(
#             #     {
#             #         "full_name": request.full_name,
#             #         "student_id": request.student_id,
#             #         "department": request.department,
#             #         "email": request.email,
#             #         "location": request.location,
#             #         "generated_date": datetime.now(timezone.utc).strftime("%d %B %Y"),
#             #         "satellite_image_b64": sat_b64,
#             #         "qgis_image_b64": qgis_b64,
#             #     }
#             # )

#             _set_job_state(job_id, "processing", "Sending report email")
#             send_report_email(
#                 EmailPayload(
#                     recipient=request.email,
#                     subject=f"Your GIS Academic Report - {request.location}",
#                     body=(
#                         f"Hello {request.full_name},\n\n"
#                         "Attached is your personalized GIS report in PDF format.\n\n"
#                         "Regards,\nGISCOPO Team"
#                     ),
#                     attachment_filename="gis_report.pdf",
#                     attachment_bytes=pdf_bytes,
#                 )
#             )
#     except (ScreenshotEngineError, PDFGenerationError, MailerError) as exc:
#         logger.exception("Pipeline failed for job %s", job_id)
#         _set_job_state(job_id, "failed", str(exc))
#         return
#     except Exception as exc:  # pragma: no cover - fallback handler
#         logger.exception("Unexpected pipeline failure for job %s", job_id)
#         _set_job_state(job_id, "failed", "Unexpected error occurred")
#         return

#     _set_job_state(job_id, "completed", "Report generated and delivered")


def _process_report(job_id: str, request: ReportRequest) -> None:
    _set_job_state(job_id, "processing", "Generating screenshots")

    try:
        with tempfile.TemporaryDirectory(prefix="giscopo-") as temp_dir:
            # ONLY CALL THIS ONCE
            # Since the updated function already handles the base64 conversion, 
            # we just unpack the three strings directly!
            sat_b64, qgis_b64, final_layout_b64 = generate_report_images(request.location, temp_dir)

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

@app.post("/api/generate-report")
def generate_report(payload: ReportRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    
    # Bypass Paystack during local backend testing
    if payload.payment_reference != "test_bypass":
        verify_paystack_payment(payload.payment_reference, payload.email)

    job_id = str(uuid.uuid4())
    _set_job_state(job_id, "queued", "Report request accepted")
    background_tasks.add_task(_process_report, job_id, payload)

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Payment verified. Your report is being prepared and will be sent via email shortly.",
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
#         "Each section must be detailed and substantial (at least 100 to 150 words per section). "
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
        
def generate_dynamic_sections(location: str, department: str) -> dict[str, str]:
    # The Mega-Prompt: Forces the AI to write exhaustive, lengthy, highly technical content
    prompt = (
        f"You are a senior academic assistant helping a {department} student write an exhaustive, highly technical GIS report for {location}. "
        "Your primary directive is LENGTH and DEPTH. You must write at least 300 to 400 words for EVERY SINGLE SECTION to ensure it fills an entire A4 page. "
        "Expand heavily on theoretical backgrounds, practical implications, civil engineering considerations, and geomatics methodologies. "
        "In the 'overview', discuss the history of urbanization and infrastructure sprawl in the area. "
        "In 'data_description', thoroughly detail raster resolution, coordinate systems (WGS 84, UTM Zone 31N), and database schema topologies. "
        "In 'methodology', explain the exact step-by-step algorithms for georeferencing, Polynomial 1 transformations, Nearest Neighbor resampling, and advanced digitizing topology rules (snapping tolerances, avoiding dangles). "
        "In 'discussion', extensively analyze spatial patterns, road network hierarchies, and land-use distribution. "
        "Return the response in strict JSON format with these exact keys: "
        "'overview', 'data_description', 'methodology', 'discussion', 'conclusion'."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a senior GIS academic writer that outputs strict JSON. You prioritize long, exhaustive, highly detailed paragraph generation."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" },
            temperature=0.7, 
            timeout=30 # Increased timeout since it is generating much more text!
        )
        
        raw_text = response.choices[0].message.content
        return json.loads(raw_text)

    except Exception as e:
        print(f"GitHub Models API failed: {e}")
        # Make sure your fallback text is also longer just in case!
        return {
            "overview": f"This project focuses on building a highly precise, georeferenced 2D vector GIS database for {location}. As the area expands with new infrastructure, traditional static maps can no longer keep up with spatial planning needs. This project solves that limitation by converting high-resolution satellite imagery into a dynamic, organized spatial database.",
            "data_description": "The dataset utilizes high-resolution satellite imagery as its primary raster base map. To ensure real-world accuracy for distance and area measurements, all layers are projected to a localized UTM coordinate system. The spatial data is structured into primary vector layers including polygons for footprints, lines for transit networks, and points for utilities.",
            "methodology": "Prominent, permanent landmarks were identified to serve as Ground Control Points (GCPs). The raw satellite imagery was aligned using a Polynomial transformation with a Nearest Neighbor resampling method. During digitization, advanced snapping options were enabled to eliminate spatial gaps and overlapping boundaries, capturing features at a sharp scale.",
            "discussion": "The final output is a topologically sound, fully queryable GIS database. The dataset reveals distinct spatial patterns, dense core structures, and a hierarchical road network. Visual differentiation suggests zones of residential concentration and transportation corridors. All spatial vectors are directly linked to their corresponding descriptive data.",
            "conclusion": "The digitization and spatial analysis were successfully completed using open-source GIS software. By linking physical geography with detailed descriptive attributes, the project transitions spatial records from static imagery into an intelligent database, providing reliable educational outputs for academic submissions."
        }      


def keep_alive():
    while True:
        try:
            url = "https://fincom.onrender.com/"  # Replace with your actual Render URL
            res = requests.get(url)
            print(f"Pinged at {time.ctime()}: Status {res.status_code}")
        except Exception as e:
            print(f"Error pinging at {time.ctime()}: {e}")
        time.sleep(60 * 12)  # Ping every 14 minutes

# # Create and start the background thread
t = threading.Thread(target=keep_alive)
t.daemon = True
t.start()