import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# Load variables from .env if present, overriding any cached terminal variables
load_dotenv(override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("❌ ERROR: GROQ_API_KEY is missing. Check your .env file.")
    exit(1)

print(f"✅ Groq key found! It starts with: {GROQ_API_KEY[:8]}...")

# Initialize the OpenAI client pointing to the Groq API base URL
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY
)

def test_groq_inference():
    print("Connecting to Groq using Llama 3.3 70B...")
    
    prompt = (
        "You are a senior academic assistant helping an Urban Planning student write a short GIS report for Lagos, Nigeria. "
        "Return the response in strict JSON format with these exact keys: 'overview', 'methodology', 'conclusion'."
    )
    
    try:
        response = client.chat.completions.create(
            # Using Llama 3.3 70B for high quality and speed
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a senior GIS academic writer that outputs strict JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7, 
            timeout=30 
        )
        
        raw_text = response.choices[0].message.content
        data = json.loads(raw_text)
        
        print("\n🎉 SUCCESS! Groq API is working perfectly. Here is the JSON output:\n")
        print(json.dumps(data, indent=4))

    except Exception as e:
        print(f"\n❌ Groq API failed: {e}")

if __name__ == "__main__":
    test_groq_inference()