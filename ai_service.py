# ai_service.py
"""
Robust AI service wrapper for Google Generative AI.
- Lazy-imports google.generativeai
- Uses GOOGLE_API_KEY env var if present
- Exposes is_real_client_available() to let UI show whether model calls are live
"""

import os
import json
from typing import Dict

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # set this in Streamlit Secrets

def _stub_response(review: str, rating: int) -> Dict[str, str]:
    s = (review or "").strip()
    summary = s[:400]
    actions = []
    if rating <= 2:
        actions = ["Investigate issue", "Contact user for more details"]
    elif rating == 3:
        actions = ["Collect more examples", "Consider UX improvements"]
    else:
        actions = ["Thank the user", "Consider promoting positive feedback"]
    return {"response": "[stub]", "summary": summary, "actions": " • ".join(actions)}

# detect availability without importing at module import time
def is_real_client_available() -> bool:
    try:
        import google.generativeai  # type: ignore
        return True
    except Exception:
        return False

def generate_ai_feedback(review: str, rating: int) -> Dict[str, str]:
    review = (review or "").strip()
    if not review:
        return {"response": "", "summary": "", "actions": ""}

    # If Google client not available, return stub
    try:
        import google.generativeai as genai  # type: ignore

        # configure with API key if provided
        if GOOGLE_API_KEY:
            genai.configure(api_key=GOOGLE_API_KEY)

        prompt = (
            f"Summarize the user review in 1-2 short sentences and suggest 2 concise actions.\n\n"
            f"Rating: {rating}\nReview: {review}\n\n"
            "Return a JSON object with keys: summary, actions (actions as a single string separated by ' | ')."
        )

        model = "models/text-bison-001"  # change if you prefer another model
        resp = genai.generate_text(model=model, input=prompt)

        text = ""
        if resp and hasattr(resp, "candidates") and len(resp.candidates) > 0:
            text = resp.candidates[0].content

        # Try to parse JSON output; fallback to line-splitting
        try:
            parsed = json.loads(text)
            summary = parsed.get("summary", "") if isinstance(parsed, dict) else text
            actions = parsed.get("actions", "") if isinstance(parsed, dict) else ""
        except Exception:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            summary = lines[0] if lines else text
            actions = " | ".join(lines[1:3]) if len(lines) > 1 else ""

        return {"response": text, "summary": summary, "actions": actions}

    except ModuleNotFoundError:
        return _stub_response(review, rating)
    except Exception as e:
        stub = _stub_response(review, rating)
        stub["response"] = f"[fallback due to error] {str(e)}"
        return stub
