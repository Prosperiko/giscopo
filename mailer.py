# import base64
# import os
# from dataclasses import dataclass

# import requests


# class MailerError(RuntimeError):
#     pass


# @dataclass(slots=True)
# class EmailPayload:
#     recipient: str
#     subject: str
#     body: str
#     attachment_filename: str
#     attachment_bytes: bytes


# def _send_with_sendgrid(payload: EmailPayload) -> None:
#     api_key = os.getenv("SENDGRID_API_KEY", "").strip()
#     from_email = "onboarding@resend.dev"
#     if not api_key:
#         raise MailerError("SENDGRID_API_KEY is not configured")

#     encoded_attachment = base64.b64encode(payload.attachment_bytes).decode("utf-8")
#     body = {
#         "personalizations": [{"to": [{"email": payload.recipient}]}],
#         "from": {"email": from_email},
#         "subject": payload.subject,
#         "content": [{"type": "text/plain", "value": payload.body}],
#         "attachments": [
#             {
#                 "content": encoded_attachment,
#                 "type": "application/pdf",
#                 "filename": payload.attachment_filename,
#                 "disposition": "attachment",
#             }
#         ],
#     }
#     headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}

#     response = requests.post(
#         "https://api.sendgrid.com/v3/mail/send",
#         json=body,
#         headers=headers,
#         timeout=30,
#     )
#     if response.status_code >= 300:
#         raise MailerError(f"SendGrid failed with status code {response.status_code}")


# def _send_with_resend(payload: EmailPayload) -> None:
#     api_key = os.getenv("RESEND_API_KEY", "").strip()
#     from_email = "onboarding@resend.dev"
#     if not api_key:
#         raise MailerError("RESEND_API_KEY is not configured")

#     attachments = [
#         {
#             "filename": payload.attachment_filename,
#             "content": base64.b64encode(payload.attachment_bytes).decode("utf-8"),
#         }
#     ]

#     response = requests.post(
#         "https://api.resend.com/emails",
#         headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
#         json={
#             "from": from_email,
#             "to": [payload.recipient],
#             "subject": payload.subject,
#             "text": payload.body,
#             "attachments": attachments,
#         },
#         timeout=120,
#     )
#     if response.status_code >= 300:
#         raise MailerError(f"Resend failed with status code {response.status_code}")


# def send_report_email(payload: EmailPayload) -> None:
#     provider = os.getenv("MAIL_PROVIDER", "sendgrid").strip().lower()
#     try:
#         if provider == "resend":
#             _send_with_resend(payload)
#             return
#         _send_with_sendgrid(payload)
#     except requests.RequestException as exc:
#         raise MailerError("Email provider unavailable") from exc










# import base64
# import os
# from dataclasses import dataclass
# import requests
# from dotenv import load_dotenv

# # 1. Force Python to read your .env file, overriding any stuck terminal variables
# load_dotenv(override=True)

# class MailerError(RuntimeError):
#     pass

# @dataclass(slots=True)
# class EmailPayload:
#     recipient: str
#     subject: str
#     body: str
#     attachment_filename: str
#     attachment_bytes: bytes

# #yh
# def _send_with_sendgrid(payload: EmailPayload) -> None:
#     api_key = os.getenv("SENDGRID_API_KEY", "").strip()
#     # Note: SendGrid needs a verified sender email, not the resend.dev one
#     from_email = os.getenv("SENDGRID_FROM_EMAIL", "reports@giscopo.ossaiku.tech") 
    
#     if not api_key:
#         raise MailerError("SENDGRID_API_KEY is not configured")

#     encoded_attachment = base64.b64encode(payload.attachment_bytes).decode("utf-8")
#     body = {
#         "personalizations": [{"to": [{"email": payload.recipient}]}],
#         "from": {"email": from_email},
#         "subject": payload.subject,
#         "content": [{"type": "text/plain", "value": payload.body}],
#         "attachments": [
#             {
#                 "content": encoded_attachment,
#                 "type": "application/pdf",
#                 "filename": payload.attachment_filename,
#                 "disposition": "attachment",
#             }
#         ],
#     }
#     headers = {"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}

#     response = requests.post(
#         "https://api.sendgrid.com/v3/mail/send",
#         json=body,
#         headers=headers,
#         timeout=90,
#     )
#     if response.status_code >= 300:
#         try:
#             error_details = response.json()
#         except Exception:
#             error_details = response.text
#         raise MailerError(f"SendGrid failed with status code {response.status_code}: {error_details}")

# def _send_with_resend(payload: EmailPayload) -> None:
#     api_key = os.getenv("RESEND_API_KEY", "").strip()
    
#     # Sandbox mode strictly requires this exact 'from' address
#     from_email = "reports@giscopo.ossaiku.tech"
    
#     if not api_key:
#         raise MailerError("RESEND_API_KEY is not configured")

#     attachments = [
#         {
#             "filename": payload.attachment_filename,
#             "content": base64.b64encode(payload.attachment_bytes).decode("utf-8"),
#         }
#     ]

#     response = requests.post(
#         "https://api.resend.com/emails",
#         headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
#         json={
#             "from": from_email,
            
#             # IN SANDBOX MODE: payload.recipient MUST be the email you used to register for Resend!
#             "to": [payload.recipient], 
#             "subject": payload.subject,
#             "text": payload.body,
#             "attachments": attachments,
#         },
#         timeout=120,
#     )
    
#     if response.status_code >= 300:
#         # Extract exactly why Resend is rejecting the request
#         try:
#             error_msg = response.json()
#         except Exception:
#             error_msg = response.text
#         raise MailerError(f"Resend failed with status code {response.status_code}. Details: {error_msg}")

# def send_report_email(payload: EmailPayload) -> None:
#     provider = os.getenv("MAIL_PROVIDER", "sendgrid").strip().lower()
#     try:
#         if provider == "resend":
#             _send_with_resend(payload)
#             return
#         _send_with_sendgrid(payload)
#     except requests.RequestException as exc:
#         raise MailerError("Email provider unavailable") from exc










import base64
import os
import time
import random
import logging
from dataclasses import dataclass
import requests
from dotenv import load_dotenv

# 1. Force Python to read your .env file, overriding any stuck terminal variables
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
    # Note: SendGrid needs a verified sender email, not the resend.dev one
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
    
    # Sandbox mode strictly requires this exact 'from' address
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
        
        # IN SANDBOX MODE: payload.recipient MUST be the email you used to register for Resend!
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

def send_report_email(payload: EmailPayload) -> None:
    provider = os.getenv("MAIL_PROVIDER", "sendgrid").strip().lower()
    try:
        if provider == "resend":
            _send_with_resend(payload)
            return
        _send_with_sendgrid(payload)
    except requests.RequestException as exc:
        raise MailerError("Email provider unavailable") from exc