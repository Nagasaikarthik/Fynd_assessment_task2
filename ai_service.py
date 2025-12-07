import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load .env values
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not found in .env file.")

genai.configure(api_key=API_KEY)

MODEL = "gemini-2.5-pro"

def generate_ai_feedback(review, rating):
    prompt = f"""
    User rating: {rating}
    User review: {review}

    Tasks for AI:
    1. Generate a friendly response to the user.
    2. Provide a short summary of the review.
    3. Provide recommended next actions for the company.

    Return ONLY JSON:
    {{
        "response": "...",
        "summary": "...",
        "actions": "..."
    }}
    """

    model = genai.GenerativeModel(MODEL)
    result = model.generate_content(prompt)

    try:
        return eval(result.text)
    except Exception:
        return {
            "response": "Thank you for your feedback!",
            "summary": "General feedback summary.",
            "actions": "Needs internal review."
        }