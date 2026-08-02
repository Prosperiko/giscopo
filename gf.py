

import os
import json
import base64
import requests
import openai
import time
import logging

import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# 1. Force Python to read your .env file
# 1. Force Python to read your .env file
load_dotenv(override=True)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from openai import OpenAI

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
# client = OpenAI(
#     base_url="https://models.inference.ai.azure.com",
#     api_key=GITHUB_TOKEN
# )

from openai import OpenAI



GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)





# validate token early and fail with clear message
# API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("GITHUB_TOKEN") or os.getenv("AZURE_OPENAI_KEY", "")
# if not API_KEY:
#     logger.error("No API key found. Set OPENAI_API_KEY or AZURE_OPENAI_KEY.")
#     raise SystemExit(1)

# # common mistake: GitHub PATs start with ghp_ (not valid for OpenAI)
# if API_KEY.startswith("ghp_") or API_KEY.startswith("github_"):
#     logger.error("Detected a GitHub token. Use an OpenAI or Azure OpenAI key in OPENAI_API_KEY or AZURE_OPENAI_KEY.")
#     raise SystemExit(1)

# # For OpenAI hosted API:
# client = OpenAI(api_key=API_KEY)

# # If using Azure OpenAI, replace with:
# # client = OpenAI(api_key=API_KEY, base_url=os.getenv("AZURE_OPENAI_ENDPOINT"))
# # and set MODEL_NAME to your deployment name (not a standard model id)
# # ...existing code...


def generate_dynamic_sections(location: str, department: str) -> dict[str, str]:
    model_name = os.getenv("MODEL_NAME", "gpt-4o")
    token = os.getenv("GITHUB_TOKEN") or os.getenv("OPENAI_API_KEY")
    if not token:
        logger.error("Model token not set (GITHUB_TOKEN/OPENAI_API_KEY)")
        return {
            "overview": f"Fallback overview for {location}.",
            "data_description": "Fallback data description.",
            "methodology": "Fallback methodology.",
            "discussion": "Fallback discussion.",
            "conclusion": "Fallback conclusion.",
        }

    prompt = (
        f"You are a senior academic assistant helping a {department} student write a GIS report for {location}. "
        "Return a JSON object with keys: 'overview','data_description','methodology','discussion','conclusion'."
    )

    last_exc = None
    for attempt in range(1, 4):
        try:
            logger.info("Model call attempt=%d model=%s location=%s", attempt, model_name, location)
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a GIS assistant that outputs strict JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                timeout=30,
            )

            # Defensive extraction of returned content
            content = None
            try:
                content = response.choices[0].message.content
            except Exception:
                try:
                    content = getattr(response.choices[0].message, "content", None)
                except Exception:
                    content = None

            # fallback extraction variants
            if not content:
                try:
                    content = getattr(response.choices[0], "text", None)
                except Exception:
                    content = None

            if isinstance(content, dict):
                return content

            if isinstance(content, str) and content.strip():
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    logger.warning("Model returned non-JSON text on attempt %d: %s", attempt, content[:200])

            # As a last try, if the client has a dict representation with usable output:
            try:
                as_dict = response.to_dict() if hasattr(response, "to_dict") else None
                if as_dict:
                    # look for common shapes
                    for key in ("output", "message", "choices"):
                        if key in as_dict and isinstance(as_dict[key], dict):
                            return as_dict[key]
            except Exception:
                pass

            raise ValueError("No valid JSON content from model")

        except Exception as exc:
            last_exc = exc
            logger.exception("Model call failed (attempt %d): %s", attempt, exc)
            time.sleep(2 ** (attempt - 1))

    logger.error("All model attempts failed: %s", last_exc)
    return {
        "overview": f"Fallback overview for {location}.",
        "data_description": "Fallback data description.",
        "methodology": "Fallback methodology.",
        "discussion": "Fallback discussion.",
        "conclusion": "Fallback conclusion.",
    }
    
# generate_dynamic_sections("New York City", "Urban Planning")




import os
import json
from dotenv import load_dotenv
from openai import OpenAI



GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# 2. Check if the token actually loaded before trying to call the AI
if not GITHUB_TOKEN:
    print("❌ ERROR: GITHUB_TOKEN is empty. Python cannot find your .env file.")
    exit(1)
if not (GITHUB_TOKEN.startswith("ghp_") or GITHUB_TOKEN.startswith("github_pat_")):
    print("❌ ERROR: Your token doesn't look like a valid GitHub token.")
    exit(1)

print("✅ Token loaded successfully! Connecting to GitHub Models...")

# 3. Connect using the GitHub Models Azure endpoint
# client = OpenAI(
#     base_url="https://models.inference.ai.azure.com",
#     api_key=GITHUB_TOKEN
# )

def test_github_models():
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Using mini for a fast, cheap test
            messages=[
                {"role": "system", "content": "You output strict JSON."},
                {"role": "user", "content": "Return a JSON object with the key 'status' and value 'GitHub Models is working!'"}
            ],
            response_format={ "type": "json_object" },
            temperature=0.7,
            timeout=30
        )
        
        print("\n🎉 SUCCESS! Here is the response from the AI:")
        print(response.choices[0].message.content)

    except Exception as e:
        print(f"\n❌ GitHub Models API failed: {e}")

if __name__ == "__main__":
    test_github_models()