"""
Agent 4: The 24/7 Student Advisory Counselor
Vercel Python serverless function - served at /api/chat
"""

import os
import json
import urllib.request
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="Student Advisor API - Agent 4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GITHUB_RAW_URL = (
    "https://raw.githubusercontent.com/"
    "Jaiswal096/Student-opportunities-agents/main/opportunities.json"
)
MODEL_NAME = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# Agent 4 System Instruction
# ---------------------------------------------------------------------------
SYSTEM_INSTRUCTION_TEMPLATE = """\
You are Opportunity Scout - a warm, expert 24/7 Student Advisory Counselor powered by AI.
You help students worldwide discover, evaluate, and successfully apply for academic and professional opportunities.

???????????????????????????????
YOUR LIVE OPPORTUNITY DATABASE
???????????????????????????????
{opportunities}
???????????????????????????????

ADVISORY RULES:
1. PERSONALIZE - Ask about the student's level, field, and goals if not stated.
2. RECOMMEND PRECISELY - Surface 2-4 best matches; never dump the entire list.
3. ALWAYS INCLUDE for each recommendation:
   . Exact deadline (or "Rolling")
   . Compensation / funding detail (use stipend_amount if available)
   . Direct application link (apply_url)
   . One-sentence pitch why it's a great fit
4. APPLICATION HELP - Offer to give tips, essay guidance, or eligibility checks.
5. HONESTY - If no opportunities match the student's profile, say so and give general advice.
6. TONE - Warm, motivating, professional. Use formatting (bold, bullets) for clarity.
7. FORMATTING - Use markdown: **bold** for key info, bullet points for lists, and [text](url) for links.

If the database is empty, tell the student the daily pipeline hasn't run yet and offer general career advice instead.\
"""

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class Message(BaseModel):
    role: str    # "user" or "model"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = []

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_local_opportunities() -> list | None:
    """Try to load opportunities.json from project root (multiple candidate paths)."""
    # Search relative to this file, and common Vercel deployment paths
    candidates = [
        Path(__file__).parent.parent / "opportunities.json",   # repo root
        Path("/var/task/opportunities.json"),                    # Vercel serverless root
        Path("opportunities.json"),                              # cwd
    ]
    for path in candidates:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    return data
        except Exception:
            continue
    return None


def fetch_github_opportunities() -> list | None:
    """Fetch opportunities from the GitHub raw URL as a fallback."""
    try:
        req = urllib.request.Request(
            GITHUB_RAW_URL,
            headers={"User-Agent": "OpportunityScout/2.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and data:
                return data
    except Exception:
        pass
    return None


def fetch_opportunities() -> str:
    """Load opportunities: local file first, then GitHub, then empty."""
    data = load_local_opportunities() or fetch_github_opportunities()
    if not data:
        return "[]  # No opportunities in database yet."
    # Only include active opportunities
    active = [o for o in data if o.get("is_active", True)]
    return json.dumps(active, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/api/chat")
async def health():
    return {"status": "ok", "agent": "Opportunity Scout", "model": MODEL_NAME}


@app.get("/api/opportunities")
async def get_opportunities():
    """Proxy endpoint so the frontend avoids CORS complexity."""
    raw = fetch_opportunities()
    try:
        return JSONResponse(json.loads(raw))
    except Exception:
        return JSONResponse([])


@app.post("/api/chat")
async def chat(request: ChatRequest):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return JSONResponse(
            {"error": "GEMINI_API_KEY is not configured on this server."},
            status_code=500,
        )

    # Inject live opportunity data into system prompt
    opportunities = fetch_opportunities()
    system_prompt = SYSTEM_INSTRUCTION_TEMPLATE.format(opportunities=opportunities)

    client = genai.Client(api_key=api_key)

    # Build multi-turn contents list
    contents: List[types.Content] = []
    for msg in (request.history or []):
        contents.append(
            types.Content(
                role=msg.role,
                parts=[types.Part(text=msg.content)],
            )
        )
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part(text=request.message)],
        )
    )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
                max_output_tokens=1500,
            ),
        )
        return JSONResponse({"reply": response.text})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
