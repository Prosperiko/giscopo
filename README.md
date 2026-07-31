# giscopo

GISCOPO is a FastAPI microservice that generates personalized academic GIS PDF reports after verified Paystack payments.

## Local run

```bash
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload
```

Open `http://localhost:8000`.

## Required environment variables

- `PAYSTACK_PUBLIC_KEY`
- `PAYSTACK_SECRET_KEY`
- `MAIL_PROVIDER` (`sendgrid` or `resend`)
- `MAIL_FROM`
- `SENDGRID_API_KEY` (when `MAIL_PROVIDER=sendgrid`)
- `RESEND_API_KEY` (when `MAIL_PROVIDER=resend`)
- `MAPBOX_ACCESS_TOKEN` (optional satellite imagery fallback)
