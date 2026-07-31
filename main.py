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


def _process_report(job_id: str, request: ReportRequest) -> None:
    _set_job_state(job_id, "processing", "Generating screenshots")

    try:
        with tempfile.TemporaryDirectory(prefix="giscopo-") as temp_dir:
            images = generate_report_images(request.location, temp_dir)

            _set_job_state(job_id, "processing", "Compiling PDF report")
            with open(images["satellite"], "rb") as sat_file, open(images["qgis"], "rb") as qgis_file:
                sat_b64 = base64.b64encode(sat_file.read()).decode("utf-8")
                qgis_b64 = base64.b64encode(qgis_file.read()).decode("utf-8")

            pdf_bytes = build_report_pdf(
                {
                    "full_name": request.full_name,
                    "student_id": request.student_id,
                    "department": request.department,
                    "email": request.email,
                    "location": request.location,
                    "generated_date": datetime.now(timezone.utc).strftime("%d %B %Y"),
                    "satellite_image_b64": sat_b64,
                    "qgis_image_b64": qgis_b64,
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


@app.post("/api/generate-report")
def generate_report(payload: ReportRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
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
