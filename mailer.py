
import base64
import os
import time
import random
import logging
from dataclasses import dataclass
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

class MailerError(RuntimeError):
    pass

@dataclass(slots=True)
class EmailPayload:
    recipient: str
    subject: str
    body: str
    attachment_filename: str
    attachment_bytes: bytes

#yh
def _send_with_sendgrid(payload: EmailPayload) -> None:
    api_key = os.getenv("SENDGRID_API_KEY", "").strip()
   
    from_email = os.getenv("SENDGRID_FROM_EMAIL", "reports@giscopo.ossaiku.tech") 
    
    if not api_key:
        raise MailerError("SENDGRID_API_KEY is not configured")

    encoded_attachment = base64.b64encode(payload.attachment_bytes).decode("utf-8")
    body = {
        "personalizations": [{"to": [{"email": payload.recipient}]}],
        "from": {"email": from_email},
        "subject": payload.subject,
        "content": [{"type": "text/plain", "value": payload.body}],
        "attachments": [
            {
                "content": encoded_attachment,
                "type": "application/pdf",
                "filename": payload.attachment_filename,
                "disposition": "attachment",
            }
        ],
    }
    headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}

    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        json=body,
        headers=headers,
        timeout=90,
    )
    if response.status_code >= 300:
        try:
            error_details = response.json()
        except Exception:
            error_details = response.text
        raise MailerError(f"SendGrid failed with status code {response.status_code}: {error_details}")

def _send_with_resend(payload: EmailPayload, max_retries: int = 3) -> None:
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    
    from_email = "reports@giscopo.ossaiku.tech"
    
    if not api_key:
        raise MailerError("RESEND_API_KEY is not configured")

    attachments = [
        {
            "filename": payload.attachment_filename,
            "content": base64.b64encode(payload.attachment_bytes).decode("utf-8"),
        }
    ]

    headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}
    json_payload = {
        "from": from_email,
        
        # Note to self IN SANDBOX MODE: payload.recipient MUST be the email you used to register for Resend!
        "to": [payload.recipient], 
        "subject": payload.subject,
        "text": payload.body,
        "attachments": attachments,
    }

    base_delay = 2.0

    for attempt in range(max_retries):
        try:
            response = requests.post(
                "https://api.resend.com/emails",
                headers=headers,
                json=json_payload,
                timeout=120, # Generous 2-minute timeout for massive PDFs
            )
            
            # If successful, exit the function immediately
            if response.status_code < 300:
                logging.info("Email sent successfully via Resend.")
                return 
                
            # If Resend complains about bad data, bad API key, or bad email (400-403), do NOT retry.
            if 400 <= response.status_code < 500 and response.status_code != 408:
                try:
                    error_msg = response.json()
                except Exception:
                    error_msg = response.text
                raise MailerError(f"Resend failed with status code {response.status_code}. Details: {error_msg}")
                
                
            
            if response.status_code >= 300:
                try:
                    error_msg = response.json()
                except Exception:
                    error_msg = response.text
                    # Log the FULL error so you can see it in Render logs
                    logging.error("RESEND ERROR: status=%s body=%s", response.status_code, error_msg)
                    
                    raise MailerError(f"Resend failed: {error_msg}")
            # If it's a 408 (Timeout) or 500+ (Server Error), raise an error to trigger the retry block
            response.raise_for_status()

        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            logging.warning(f"Resend attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                # Exponential backoff: 2s, 4s... plus a tiny bit of random jitter
                sleep_time = (base_delay * (2 ** attempt)) + random.uniform(0, 1)
                logging.info(f"Retrying Resend upload in {sleep_time:.2f}s...")
                time.sleep(sleep_time)
            else:
                # Give up after max_retries tries and crash gracefully
                raise MailerError(f"Resend failed after {max_retries} attempts. Last error: {e}") from e
            
        except Exception:
            error_msg = response.text
            # Log the FULL error so you can see it in Render logs
            logging.error("RESEND ERROR: status=%s body=%s", response.status_code, error_msg)
            raise MailerError(f"Resend failed: {error_msg}")

def send_report_email(payload: EmailPayload) -> None:
    provider = os.getenv("MAIL_PROVIDER", "sendgrid").strip().lower()
    logging.info("Preparing to send email using provider=%s to=%s", provider, payload.recipient)

    # Quick sanity checks to make diagnosing production failures easier
    if provider == "resend":
        if not os.getenv("RESEND_API_KEY"):
            logging.error("RESEND_API_KEY not set while MAIL_PROVIDER=resend")
            raise MailerError("Resend provider selected but RESEND_API_KEY is not configured")
    else:
        # default to SendGrid
        if not os.getenv("SENDGRID_API_KEY"):
            logging.error("SENDGRID_API_KEY not set while MAIL_PROVIDER=%s", provider)
            raise MailerError("SendGrid provider selected but SENDGRID_API_KEY is not configured")

    try:
        if provider == "resend":
            _send_with_resend(payload)
            return
        _send_with_sendgrid(payload)
    except MailerError:
        # Re-raise our domain-specific error
        raise
    except requests.RequestException as exc:
        logging.exception("Network error while sending email to %s", payload.recipient)
        raise MailerError("Email provider unavailable") from exc
    except Exception as exc:
        logging.exception("Unexpected error while sending email to %s", payload.recipient)
        raise MailerError(str(exc)) from exc
