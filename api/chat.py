"""
Agent 4: The 24/7 Student Advisory Counselor
Vercel Python serverless function — served at /api/chat
"""

import os
import json
import urllib.request
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
app = FastAPI(title="Student Advisor API — Agent 4")

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
You are Opportunity Scout — a warm, expert 24/7 Student Advisory Counselor powered by AI.
You help students worldwide discover, evaluate, and successfully apply for academic and professional opportunities.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR LIVE OPPORTUNITY DATABASE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{opportunities}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ADVISORY RULES:
1. PERSONALIZE — Ask about the student's level, field, and goals if not stated.
2. RECOMMEND PRECISELY — Surface 2–4 best matches; never dump the entire list.
3. ALWAYS INCLUDE for each recommendation:
   • Exact deadline (or "Rolling")
   • Compensation / funding detail
   • Direct application link (apply_url)
   • One-sentence pitch why it's a great fit
4. APPLICATION HELP — Offer to give tips, essay guidance, or eligibility checks.
5. HONESTY — If no opportunities match the student's profile, say so and give general advice.
6. TONE — Warm, motivating, professional. Use formatting (bold, bullets) for clarity.

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
def fetch_opportunities() -> str:
    """Fetch the latest opportunities.json from the GitHub main branch."""
    try:
        req = urllib.request.Request(
            GITHUB_RAW_URL,
            headers={"User-Agent": "OpportunityScout/1.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data:
                return "[]  # No opportunities in database yet."
            return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as exc:
        return f"[Database temporarily unavailable: {exc}]"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/api/chat")
async def health():
    return {"status": "ok", "agent": "Opportunity Scout", "model": MODEL_NAME}


@app.get("/api/opportunities")
async def get_opportunities():
    """Proxy endpoint so the frontend avoids direct GitHub CORS complexity."""
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
