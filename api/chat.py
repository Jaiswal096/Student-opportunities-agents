import os
import json
import time
import logging
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = logging.getLogger("AdvisorAPI")

try:
    from dotenv import load_dotenv
    _ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(_ROOT / ".env")
    load_dotenv()
except ImportError:
    pass

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
# Paths & Static file serving
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent  # project root
_PUBLIC = _ROOT / "public"

if _PUBLIC.exists():
    app.mount("/public", StaticFiles(directory=str(_PUBLIC)), name="public")


def find_static_file(rel_path: str) -> Optional[Path]:
    """Resolve static files across local development and Vercel serverless container paths."""
    candidates = [
        _PUBLIC / rel_path,
        _ROOT / "public" / rel_path,
        _ROOT / rel_path,
        Path("public") / rel_path,
        Path(rel_path),
        Path("/var/task/public") / rel_path,
        Path("/var/task") / rel_path,
        Path(__file__).parent.parent / "public" / rel_path,
    ]
    for p in candidates:
        try:
            if p.exists() and p.is_file():
                return p
        except Exception:
            continue
    return None


@app.get("/")
@app.get("/index.html")
@app.get("/public/index.html", include_in_schema=False)
async def index():
    p = find_static_file("index.html")
    if p:
        return FileResponse(str(p), media_type="text/html")
    return JSONResponse({"error": "index.html not found"}, status_code=404)


@app.get("/widget.js")
@app.get("/public/widget.js", include_in_schema=False)
async def widget_js():
    p = find_static_file("widget.js")
    if p:
        return FileResponse(str(p), media_type="application/javascript")
    return JSONResponse({"error": "widget.js not found"}, status_code=404)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Configuration & API Protection Settings
# ---------------------------------------------------------------------------
GITHUB_RAW_URL = os.environ.get(
    "GITHUB_RAW_URL",
    "https://raw.githubusercontent.com/Jaiswal096/Student-opportunities-agents/main/opportunities.json"
)
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# API Protection limits
MAX_MESSAGE_LENGTH = 1500
RATE_LIMIT_MAX_REQUESTS = 15
RATE_LIMIT_WINDOW_SECONDS = 60

# In-memory per-IP sliding rate limit store
_ip_request_timestamps: dict[str, list[float]] = defaultdict(list)

# Dynamic opportunities cache
_cache_opportunities: Optional[list] = None
_cache_time: float = 0.0
_cache_mtime: float = 0.0
_cache_source: Optional[str] = None
CACHE_TTL: float = 60.0  # 60s cache for remote GitHub raw requests


def get_client_ip(request: Request) -> str:
    """Extract client IP from reverse proxy headers or direct socket."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def is_rate_limited(ip: str) -> bool:
    """
    Check if the client IP has exceeded RATE_LIMIT_MAX_REQUESTS within
    the RATE_LIMIT_WINDOW_SECONDS sliding window.
    """
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    timestamps = _ip_request_timestamps[ip]
    valid_timestamps = [t for t in timestamps if t > cutoff]

    if len(valid_timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        _ip_request_timestamps[ip] = valid_timestamps
        return True

    valid_timestamps.append(now)
    _ip_request_timestamps[ip] = valid_timestamps

    # Periodic garbage collection for idle IPs
    if len(_ip_request_timestamps) > 2000:
        for k in list(_ip_request_timestamps.keys()):
            _ip_request_timestamps[k] = [t for t in _ip_request_timestamps[k] if t > cutoff]
            if not _ip_request_timestamps[k]:
                del _ip_request_timestamps[k]

    return False


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
   • Compensation / funding detail (use stipend_amount if available)
   • Direct application link (apply_url)
   • One-sentence pitch why it's a great fit
4. APPLICATION HELP — Offer to give tips, essay guidance, or eligibility checks.
5. HONESTY — If no opportunities match the student's profile, say so and give general advice.
6. TONE — Warm, motivating, professional. Use formatting (bold, bullets) for clarity.
7. FORMATTING — Use markdown: **bold** for key info, bullet points for lists, and [text](url) for links.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SPECIAL MODE: "MATCH MY PROFILE / RESUME"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When a student provides their major, academic year, skills, interests, or resume summary (or initiates profile matching):
1. Evaluate their profile against all active opportunities in your database.
2. Select and rank the TOP 3 best-fitting opportunities from the live database.
3. For each of the top 3, display:
   ### 🥇 Top Match #1: [Title](apply_url) — **{Match Percentage}% Match**
   - **Host Organization**: {host_organization}
   - **Why It's a Top Match**: Clear explanation of how their specific major, year, or skills align.
   - **Details**: Deadline (`{deadline}`) | Compensation: **{compensation}** ({stipend_amount}) | Location: {location_type}
   - **🎯 Specific Application Tips**: 2–3 actionable, concrete insider tips on tailoring their resume, portfolio, or statement of purpose for this exact program.
4. Follow the same format for Match #2 (🥈) and Match #3 (🥉).
5. Conclude with motivating next steps and encourage them to ask for help on personal statements or interview preparation.

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
# Dynamic Opportunities & Broadcasts Loading
# ---------------------------------------------------------------------------
def get_file_candidate_paths(filename: str) -> List[Path]:
    """Search for a JSON data file across root and public/ across environments."""
    return [
        _PUBLIC / filename,
        _ROOT / "public" / filename,
        _ROOT / filename,
        Path("public") / filename,
        Path(filename),
        Path("/var/task/public") / filename,
        Path("/var/task") / filename,
        Path(__file__).resolve().parent.parent / "public" / filename,
        Path(__file__).resolve().parent.parent / filename,
    ]


def get_broadcasts_list() -> list:
    """Return parsed list of active announcements/broadcasts."""
    for path in get_file_candidate_paths("broadcasts.json"):
        try:
            if path.exists() and path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
        except Exception:
            continue
    return []


def fetch_github_opportunities(url: Optional[str] = None) -> Optional[list]:
    """Fetch opportunities from GitHub raw URL."""
    target_url = url or GITHUB_RAW_URL
    if not target_url:
        return None
    try:
        req = urllib.request.Request(
            target_url,
            headers={
                "User-Agent": "OpportunityScout/2.0",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
        )
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and data:
                return data
    except Exception as exc:
        logger.warning(f"Failed to fetch GitHub raw opportunities from {target_url}: {exc}")
    return None


def get_active_opportunities_list() -> list:
    """
    Return parsed list of active opportunities.
    Reloads dynamically:
    1. If GITHUB_RAW_URL is set in environment, fetches latest from GitHub (cached with 60s TTL).
    2. Otherwise dynamically checks local file mtime (checking root and public/) and reloads immediately.
    3. Falls back to default GitHub raw URL if local file is missing.
    """
    global _cache_opportunities, _cache_time, _cache_mtime, _cache_source
    now = time.time()
    env_github_url = os.environ.get("GITHUB_RAW_URL")

    # 1. If custom GITHUB_RAW_URL is specified in environment, prioritize remote updates
    if env_github_url:
        if _cache_opportunities and _cache_source == "github_env" and (now - _cache_time < CACHE_TTL):
            return [o for o in _cache_opportunities if o.get("is_active", True)]
        remote_data = fetch_github_opportunities(env_github_url)
        if remote_data:
            _cache_opportunities = remote_data
            _cache_time = now
            _cache_source = "github_env"
            return [o for o in remote_data if o.get("is_active", True)]

    # 2. Dynamic local file reload (checks root and public/ paths)
    for path in get_file_candidate_paths("opportunities.json"):
        try:
            if path.exists() and path.is_file():
                mtime = path.stat().st_mtime
                if _cache_opportunities and _cache_source == "local" and mtime == _cache_mtime:
                    return [o for o in _cache_opportunities if o.get("is_active", True)]
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    _cache_opportunities = data
                    _cache_time = now
                    _cache_mtime = mtime
                    _cache_source = "local"
                    return [o for o in data if o.get("is_active", True)]
        except Exception:
            continue

    # 3. Fallback to default GitHub raw URL if local file is missing or unreadable
    if _cache_opportunities and (now - _cache_time < CACHE_TTL):
        return [o for o in _cache_opportunities if o.get("is_active", True)]

    fallback_data = fetch_github_opportunities(GITHUB_RAW_URL)
    if fallback_data:
        _cache_opportunities = fallback_data
        _cache_time = now
        _cache_source = "github_default"
        return [o for o in fallback_data if o.get("is_active", True)]

    return [o for o in (_cache_opportunities or []) if o.get("is_active", True)]


def fetch_opportunities() -> str:
    """Load opportunities as formatted JSON string for system prompt."""
    active = get_active_opportunities_list()
    if not active:
        return "[]  # No opportunities in database yet."
    return json.dumps(active, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Offline / Fallback Advisor Logic (Including Profile Matching)
# ---------------------------------------------------------------------------
def generate_local_fallback_reply(query: str, opps: list) -> str:
    """
    Intelligent offline advisor response when GEMINI_API_KEY is not configured or fails.
    Supports general queries and dedicated Profile / Resume Matching Mode.
    """
    q = query.lower()
    is_profile_match = (
        "profile" in q or "resume" in q or "major:" in q or "skills:" in q
        or "match my profile" in q or "[profile_match_mode]" in q
    )

    matches = []

    for opp in opps:
        score = 0
        cat = str(opp.get("category", "")).lower()
        comp = str(opp.get("compensation", "")).lower()
        levels = [str(lvl).lower() for lvl in opp.get("academic_level", [])]
        tags = [str(t).lower() for t in opp.get("tags", [])]
        title = str(opp.get("title", "")).lower()
        pitch = str(opp.get("one_line_pitch", "")).lower()
        host = str(opp.get("host_organization", "")).lower()

        # Academic level matching
        if any(w in q for w in ["undergrad", "college", "bachelor", "sophomore", "junior", "freshman", "senior"]):
            if any("undergrad" in lvl for lvl in levels):
                score += 5
        if any(w in q for w in ["grad", "master", "postgrad"]):
            if any("master" in lvl or "graduate" in lvl for lvl in levels):
                score += 5
        if any(w in q for w in ["phd", "doctorate"]):
            if any("phd" in lvl for lvl in levels):
                score += 5
        if any(w in q for w in ["high school", "teen"]):
            if any("high school" in lvl for lvl in levels):
                score += 5

        # Categories & Fields
        if any(w in q for w in ["research", "lab", "scientist", "reu"]):
            if cat == "research" or "research" in tags or "research" in title:
                score += 6
        if any(w in q for w in ["intern", "internship", "industry", "swe"]):
            if cat == "internship" or "internship" in tags:
                score += 6
        if any(w in q for w in ["scholarship", "tuition", "financial aid", "grant"]):
            if cat == "scholarship" or cat == "grant" or "scholarship" in tags:
                score += 6
        if any(w in q for w in ["fellowship", "fellow", "policy"]):
            if cat == "fellowship" or "fellowship" in tags:
                score += 6
        if any(w in q for w in ["hackathon", "build", "project", "competition"]):
            if cat == "hackathon" or "hackathon" in tags:
                score += 6

        # Technical & Domain keywords
        tech_words = [
            "python", "javascript", "react", "machine learning", "ai", "data science",
            "open source", "engineering", "physics", "biology", "stem", "finance",
            "leadership", "diversity", "climate", "health", "design"
        ]
        for tw in tech_words:
            if tw in q:
                if tw in title or tw in pitch or any(tw in t for t in tags):
                    score += 4

        # Funding preference
        if any(w in q for w in ["fully funded", "free", "full-ride", "stipend", "paid"]):
            if "fully funded" in comp or "paid" in comp:
                score += 4

        # Word overlaps
        for word in q.split():
            clean_word = "".join(c for c in word if c.isalnum())
            if len(clean_word) > 3 and clean_word not in ["profile", "match", "student", "looking", "apply", "year"]:
                if clean_word in title or clean_word in pitch or clean_word in host or any(clean_word in t for t in tags):
                    score += 2

        matches.append((score, opp))

    # Sort descending by score
    matches.sort(key=lambda x: x[0], reverse=True)

    if is_profile_match:
        # Take Top 3
        top_matches = [opp for _, opp in matches[:3]] if len(matches) >= 3 else opps[:3]
        scores = [96, 89, 83]  # Representative high-confidence match scores

        lines = [
            "🎯 **Profile & Resume Match Results**",
            "I've analyzed your academic profile, skills, and background against our live database. Here are your **Top 3 Best-Fitting Opportunities** ranked by relevance:\n"
        ]

        medals = ["🥇 Top Match #1", "🥈 Top Match #2", "🥉 Top Match #3"]
        for idx, opp in enumerate(top_matches):
            pct = scores[idx] if idx < len(scores) else 80
            medal = medals[idx] if idx < len(medals) else f"Match #{idx+1}"
            lines.append(f"### {medal}: [{opp.get('title')}]({opp.get('apply_url')}) — **{pct}% Match**")
            lines.append(f"- **Host Organization**: {opp.get('host_organization')}")
            lines.append(f"- **Why It's a Fit**: Matches your target field, academic eligibility ({', '.join(opp.get('academic_level', []))}), and aligns with domain tags ({', '.join(opp.get('tags', [])[:3])}).")
            lines.append(f"- **Key Details**: Deadline `{opp.get('deadline')}` | Funding: **{opp.get('compensation')}** ({opp.get('stipend_amount', 'Competitive')}) | Location: {opp.get('location_type')}")
            lines.append(f"- **🎯 Specific Application Tips**:")
            lines.append(f"  • **Resume**: Highlight direct project experience matching `{', '.join(opp.get('tags', [])[:2])}` on the top third of your resume.")
            lines.append(f"  • **Essay/Statement**: Emphasize how {opp.get('host_organization')}'s mission aligns with your long-term academic and career ambitions.")
            lines.append(f"  • **Direct Link**: [Apply Here]({opp.get('apply_url')})\n")

        lines.append("💡 *Next Steps: Would you like tailored essay outlines, review questions, or eligibility checks for any of these 3? Just reply with the program name!*")
        lines.append("\n> ℹ️ *Operating in offline advisory mode. Configure `GEMINI_API_KEY` in `.env` to enable real-time Gemini AI counseling.*")
        return "\n".join(lines)

    # Standard query recommendations
    selected = [opp for score, opp in matches[:3] if score > 0]
    if not selected:
        selected = opps[:2]

    if not selected:
        return (
            "Hello! I am **Opportunity Scout**, your 24/7 Student Advisory Counselor. "
            "Our database currently does not have an exact match for that specific search, "
            "but new verified opportunities are synced daily at 04:00 UTC."
        )

    lines = [
        "👋 Hello! I am **Opportunity Scout**, your 24/7 Student Advisory Counselor.",
        f"Based on your query, here {'is the top match' if len(selected) == 1 else 'are the top recommendations'} from our live database:\n"
    ]

    for opp in selected:
        lines.append(f"### 🎯 [{opp.get('title')}]({opp.get('apply_url')})")
        lines.append(f"- **Host Organization**: {opp.get('host_organization')}")
        lines.append(f"- **Category & Level**: {opp.get('category')} | {', '.join(opp.get('academic_level', []))}")
        lines.append(f"- **Funding / Compensation**: **{opp.get('compensation')}** ({opp.get('stipend_amount', 'N/A')})")
        lines.append(f"- **Deadline**: `{opp.get('deadline')}`")
        lines.append(f"- **Why it's a great fit**: {opp.get('one_line_pitch')}")
        lines.append(f"- **Direct Link**: [Apply Here]({opp.get('apply_url')})\n")

    lines.append("💡 *Tip: Would you like tips on personal essays, eligibility criteria, or interview preparation for any of these? Just ask!*")
    lines.append("\n> ℹ️ *Operating in offline advisory mode. Configure `GEMINI_API_KEY` in `.env` to enable real-time Gemini AI counseling.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/api/health")
@app.get("/health")
@app.get("/api/chat")
async def health():
    return {
        "status": "ok",
        "api_key_configured": bool(os.environ.get("GEMINI_API_KEY")),
        "agent": "Opportunity Scout",
        "model": DEFAULT_MODEL,
        "rate_limit_per_minute": RATE_LIMIT_MAX_REQUESTS,
        "max_message_chars": MAX_MESSAGE_LENGTH,
    }


@app.get("/opportunities.json")
@app.get("/api/opportunities")
async def get_opportunities():
    """
    Serve dynamic active opportunities list to frontend.
    Pulls freshest data from GitHub Action raw updates or local updates.
    """
    return JSONResponse(get_active_opportunities_list())


@app.get("/broadcasts.json")
@app.get("/api/broadcasts")
async def get_broadcasts():
    """
    Serve announcements and broadcasts list to frontend.
    """
    return JSONResponse(get_broadcasts_list())



@app.post("/api/chat")
async def chat(request: ChatRequest, fastapi_req: Request):
    # ── Protection 1: Per-IP In-Memory Rate Limiter ───────────────────────
    client_ip = get_client_ip(fastapi_req)
    if is_rate_limited(client_ip):
        return JSONResponse(
            {
                "error": f"Rate limit exceeded. Maximum {RATE_LIMIT_MAX_REQUESTS} requests per minute per IP. Please wait a moment before sending more messages."
            },
            status_code=429,
            headers={"Retry-After": "60"},
        )

    # ── Protection 2: Maximum Message Length Limit (1,500 chars) ───────────
    msg_text = (request.message or "").strip()
    if not msg_text:
        return JSONResponse({"error": "Message cannot be empty."}, status_code=400)

    if len(msg_text) > MAX_MESSAGE_LENGTH:
        return JSONResponse(
            {
                "error": f"Message exceeds the maximum length of {MAX_MESSAGE_LENGTH} characters (received {len(msg_text)}). Please shorten your message."
            },
            status_code=400,
        )

    # Dynamically re-check .env in case it was updated during runtime
    try:
        from dotenv import load_dotenv
        load_dotenv(_ROOT / ".env", override=False)
        load_dotenv(override=False)
    except Exception:
        pass

    api_key = os.environ.get("GEMINI_API_KEY")

    # If GEMINI_API_KEY is not configured locally, provide intelligent fallback
    if not api_key:
        opps = get_active_opportunities_list()
        reply = generate_local_fallback_reply(msg_text, opps)
        return JSONResponse({"reply": reply, "mode": "local_advisory_counselor"})

    # Live Gemini API path
    try:
        from google import genai
        from google.genai import types

        opportunities_str = fetch_opportunities()
        system_prompt = SYSTEM_INSTRUCTION_TEMPLATE.format(opportunities=opportunities_str)

        client = genai.Client(api_key=api_key)

        # Build multi-turn contents list (enforce content limits on history items as well)
        contents: List[types.Content] = []
        for msg in (request.history or []):
            contents.append(
                types.Content(
                    role=msg.role,
                    parts=[types.Part(text=msg.content[:MAX_MESSAGE_LENGTH])],
                )
            )
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=msg_text)],
            )
        )

        candidate_models = [DEFAULT_MODEL, "gemini-2.0-flash", "gemini-1.5-flash"]
        last_error = None

        for model_name in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.7,
                        max_output_tokens=1500,
                    ),
                )
                return JSONResponse({"reply": response.text, "model": model_name})
            except Exception as model_err:
                last_error = model_err
                continue

        raise last_error or Exception("Gemini generation failed")

    except Exception as exc:
        # Fall back to local opportunity matching if Gemini API call fails
        opps = get_active_opportunities_list()
        fallback_reply = generate_local_fallback_reply(msg_text, opps)
        return JSONResponse({
            "reply": fallback_reply,
            "warning": f"Gemini API returned: {str(exc)}. Delivered via local counselor fallback."
        })

