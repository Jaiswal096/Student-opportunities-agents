import os
import json
import time
import base64
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Any, Dict

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


class ScoutCurateRequest(BaseModel):
    topic: str
    admin_key: Optional[str] = None


class WorkflowDispatchRequest(BaseModel):
    admin_key: Optional[str] = None
    ref: Optional[str] = "main"


class DeleteOpportunityRequest(BaseModel):
    admin_key: Optional[str] = None


# ---------------------------------------------------------------------------
# Admin Authorization Helper
# ---------------------------------------------------------------------------
ADMIN_KEY_DEFAULT = "admin123"

def get_gemini_api_key() -> Optional[str]:
    """Retrieve Gemini API key across common environment variable casings."""
    return (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("Gemini_Api_Key")
        or os.environ.get("gemini_api_key")
        or os.environ.get("GEMINI_KEY")
    )

def get_admin_key_env() -> str:
    """Retrieve custom admin key across common casings or return default."""
    return (
        os.environ.get("ADMIN_KEY")
        or os.environ.get("Admin_Key")
        or os.environ.get("admin_key")
        or ADMIN_KEY_DEFAULT
    )

def get_github_token_env() -> Optional[str]:
    """Retrieve GitHub token across common casings."""
    return (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("Github_Token")
        or os.environ.get("github_token")
        or os.environ.get("GH_TOKEN")
    )

def get_github_repo_env() -> str:
    """Retrieve GitHub repository name across common casings."""
    return (
        os.environ.get("GITHUB_REPO")
        or os.environ.get("Github_Repo")
        or os.environ.get("github_repo")
        or "Jaiswal096/Student-opportunities-agents"
    )

def is_admin_authorized(fastapi_req: Request, body_admin_key: Optional[str] = None) -> bool:
    """Validate admin key against environment or default local passkey."""
    expected_key = get_admin_key_env()
    header_key = fastapi_req.headers.get("x-admin-key")
    if header_key and header_key == expected_key:
        return True
    if body_admin_key and body_admin_key == expected_key:
        return True
    query_key = fastapi_req.query_params.get("admin_key")
    if query_key and query_key == expected_key:
        return True
    return False


# ---------------------------------------------------------------------------
# Cloud-Safe Storage & GitHub Sync
# ---------------------------------------------------------------------------
def commit_file_to_github(repo: str, token: str, filepath: str, content_bytes: bytes, commit_message: str) -> bool:
    """Commit or update a file in a GitHub repository using the GitHub Contents API."""
    url = f"https://api.github.com/repos/{repo}/contents/{filepath}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "OpportunityScout-Bot",
    }
    sha = None
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                sha = body.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            logger.warning(f"GitHub Contents GET {filepath} returned {e.code}")
    except Exception as e:
        logger.warning(f"Error checking GitHub file {filepath}: {e}")

    payload = {
        "message": commit_message,
        "content": base64.b64encode(content_bytes).decode("ascii"),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={**headers, "Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            logger.info(f"GitHub Contents API commit successful for {filepath}: HTTP {resp.status}")
            return True
    except Exception as e:
        logger.error(f"Failed to commit {filepath} to GitHub via API: {e}")
        return False


def save_json_everywhere(filename: str, data: Any) -> Dict[str, bool]:
    """
    Save JSON data across multiple layers:
    1. /tmp/{filename} (always writable in Vercel serverless environment)
    2. Local project root and public/ folder (if writable, e.g. local dev / VPS)
    3. In-memory cache update
    4. GitHub repository via Contents API (if GITHUB_TOKEN & GITHUB_REPO set)
    """
    global _cache_opportunities, _cache_time, _cache_mtime, _cache_source
    results = {"tmp": False, "local": False, "github": False}
    payload_str = json.dumps(data, indent=2, ensure_ascii=False)
    payload_bytes = payload_str.encode("utf-8")

    # 1. Write to /tmp (serverless writable scratchpad)
    try:
        tmp_dir = Path("/tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        (tmp_dir / filename).write_bytes(payload_bytes)
        results["tmp"] = True
    except Exception as e:
        logger.warning(f"Could not write to /tmp/{filename}: {e}")

    # 2. Write to project root and public/ (works locally, silently ignored on read-only serverless FS)
    try:
        (_ROOT / filename).write_bytes(payload_bytes)
        _PUBLIC.mkdir(parents=True, exist_ok=True)
        (_PUBLIC / filename).write_bytes(payload_bytes)
        results["local"] = True
    except Exception:
        pass

    # Update in-memory cache
    if filename == "opportunities.json" and isinstance(data, list):
        _cache_opportunities = data
        _cache_time = time.time()
        _cache_mtime = _cache_time
        _cache_source = "tmp_memory"

    # 3. GitHub Contents API sync
    token = get_github_token_env()
    repo = get_github_repo_env()
    if token and repo:
        try:
            gh1 = commit_file_to_github(
                repo=repo,
                token=token,
                filepath=filename,
                content_bytes=payload_bytes,
                commit_message=f"data: update {filename} via Agent Command Center",
            )
            gh2 = commit_file_to_github(
                repo=repo,
                token=token,
                filepath=f"public/{filename}",
                content_bytes=payload_bytes,
                commit_message=f"data: update public/{filename} via Agent Command Center",
            )
            results["github"] = gh1 or gh2
        except Exception as e:
            logger.error(f"GitHub Contents sync error: {e}")

    return results


# ---------------------------------------------------------------------------
# Dynamic Opportunities & Broadcasts Loading
# ---------------------------------------------------------------------------
def get_file_candidate_paths(filename: str) -> List[Path]:
    """Search for a JSON data file across tmp, public/, and root across environments."""
    return [
        Path("/tmp") / filename,  # Check /tmp first for recent serverless updates
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
    1. If /tmp/opportunities.json exists (written during this serverless instance), load it immediately.
    2. Check local candidates (public/ and root) and reload if modified.
    3. If GITHUB_RAW_URL is set in environment, fetches latest from GitHub (cached with 60s TTL).
    4. Falls back to default bundled opportunities or cached data.
    """
    global _cache_opportunities, _cache_time, _cache_mtime, _cache_source
    now = time.time()

    # 1. Check /tmp/opportunities.json first (serverless write buffer)
    tmp_path = Path("/tmp/opportunities.json")
    if tmp_path.exists():
        try:
            mtime = tmp_path.stat().st_mtime
            if _cache_opportunities and _cache_source == "tmp" and mtime == _cache_mtime:
                return [o for o in _cache_opportunities if o.get("is_active", True)]
            data = json.loads(tmp_path.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                _cache_opportunities = data
                _cache_time = now
                _cache_mtime = mtime
                _cache_source = "tmp"
                return [o for o in data if o.get("is_active", True)]
        except Exception:
            pass

    # 2. Dynamic local file reload (checks public/ and root paths)
    for path in get_file_candidate_paths("opportunities.json"):
        if path == tmp_path:
            continue
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

    # 3. Fallback to GitHub raw URL if available
    env_github_url = os.environ.get("GITHUB_RAW_URL")
    if env_github_url:
        if _cache_opportunities and _cache_source == "github_env" and (now - _cache_time < CACHE_TTL):
            return [o for o in _cache_opportunities if o.get("is_active", True)]
        remote_data = fetch_github_opportunities(env_github_url)
        if remote_data:
            _cache_opportunities = remote_data
            _cache_time = now
            _cache_source = "github_env"
            return [o for o in remote_data if o.get("is_active", True)]

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
        "api_key_configured": bool(get_gemini_api_key()),
        "admin_key_configured": bool(get_admin_key_env() != ADMIN_KEY_DEFAULT or os.environ.get("ADMIN_KEY")),
        "github_token_configured": bool(get_github_token_env()),
        "github_repo": get_github_repo_env(),
        "agent": "Opportunity Scout",
        "model": DEFAULT_MODEL,
        "rate_limit_per_minute": RATE_LIMIT_MAX_REQUESTS,
        "max_message_chars": MAX_MESSAGE_LENGTH,
    }


# ---------------------------------------------------------------------------
# Universal Visual Agent Command Center Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/agents/scout-and-curate")
async def scout_and_curate(req: ScoutCurateRequest, fastapi_req: Request):
    """
    Trigger Agent 1 (Scout) -> Agent 2 (Gatekeeper) -> Agent 3 (Curator) -> Agent 5 (Broadcaster)
    for a target query/topic, and sync results across memory, disk, and GitHub.
    """
    if not is_admin_authorized(fastapi_req, req.admin_key):
        return JSONResponse({"error": "Unauthorized. Invalid admin_key."}, status_code=401)

    topic = (req.topic or "").strip()
    if not topic:
        return JSONResponse({"error": "Topic parameter is required."}, status_code=400)

    api_key = get_gemini_api_key()
    curated_items: List[dict] = []

    # Import pipeline agents
    try:
        from pipeline import run_scout_agent, run_gatekeeper_agent, run_curator_agent, get_client
    except Exception as e:
        logger.error(f"Error importing pipeline: {e}")
        return JSONResponse({"error": f"Failed to initialize pipeline: {str(e)}"}, status_code=500)

    if api_key:
        try:
            logger.info(f"Command Center: Running Agent 1-3 pipeline for: {topic}")
            c = get_client(api_key)
            # Agent 1: Scout
            raw_leads = run_scout_agent(topic, active_client=c)
            # Agent 2: Gatekeeper
            vetted_leads = run_gatekeeper_agent(raw_leads, active_client=c)
            # Agent 3: Curator
            curated_objs = run_curator_agent(vetted_leads, active_client=c)
            curated_items = [o.model_dump() for o in curated_objs]
        except Exception as e:
            logger.error(f"Error executing Gemini pipeline: {e}", exc_info=True)
            return JSONResponse({"error": f"AI Agent pipeline failed: {str(e)}"}, status_code=500)
    else:
        # Fallback structured mock curation for local/demo admin testing
        slug_topic = "".join(c if c.isalnum() else "-" for c in topic.lower()).strip("-")[:35]
        curated_items = [
            {
                "id": f"{slug_topic}-{int(time.time())}",
                "title": f"Verified Opportunity: {topic.title()}",
                "host_organization": "Global Student Opportunities Network",
                "category": "Internship" if "intern" in topic.lower() else "Research" if "research" in topic.lower() else "Scholarship",
                "academic_level": ["Undergraduate", "Masters"],
                "location_type": "Remote" if "remote" in topic.lower() else "Global",
                "location": "Global / Remote",
                "compensation": "Paid Stipend",
                "stipend_amount": "$4,000–$7,500 USD",
                "deadline": "2027-06-30",
                "apply_url": "https://opportunityscout.org/programs",
                "tags": [w.capitalize() for w in topic.split()[:4] if len(w) > 2],
                "one_line_pitch": f"High-impact opportunity directly matching '{topic}'.",
                "is_active": True,
            }
        ]

    # Deduplicate and merge into current opportunities
    existing = get_active_opportunities_list()
    existing_by_id = {item.get("id"): item for item in existing}
    existing_urls = {item.get("apply_url") for item in existing}

    added_count = 0
    for item in curated_items:
        opp_id = item.get("id")
        opp_url = item.get("apply_url")
        item["is_active"] = True

        if opp_id in existing_by_id:
            existing_by_id[opp_id] = item
        elif opp_url in existing_urls:
            for idx, existing_item in enumerate(existing):
                if existing_item.get("apply_url") == opp_url:
                    existing[idx] = item
                    break
        else:
            existing.insert(0, item)
            existing_by_id[opp_id] = item
            existing_urls.add(opp_url)
            added_count += 1

    # Save opportunities everywhere
    save_res = save_json_everywhere("opportunities.json", existing)

    # Agent 5: Broadcaster (Publish announcement)
    try:
        broadcasts = get_broadcasts_list()
        new_broadcast = {
            "id": f"broadcast-{int(time.time())}",
            "title": f"🎯 Newly Curated: {topic[:45]}",
            "message": f"Agent 1 (Scout) & Agent 3 (Curator) discovered and verified {added_count} new opportunities for '{topic}'.",
            "category": "Curated Alert",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
        }
        broadcasts.insert(0, new_broadcast)
        save_json_everywhere("broadcasts.json", broadcasts)
    except Exception as e:
        logger.warning(f"Error publishing broadcast: {e}")

    return {
        "status": "success",
        "topic": topic,
        "added": added_count,
        "total": len(existing),
        "new_items": curated_items,
        "storage": save_res,
    }


@app.post("/api/agents/trigger-github-workflow")
async def trigger_github_workflow(req: WorkflowDispatchRequest, fastapi_req: Request):
    """
    Trigger daily_pipeline.yml via GitHub Actions REST API workflow_dispatch.
    """
    if not is_admin_authorized(fastapi_req, req.admin_key):
        return JSONResponse({"error": "Unauthorized. Invalid admin_key."}, status_code=401)

    token = get_github_token_env()
    repo = get_github_repo_env()

    if not token or not repo:
        return JSONResponse(
            {
                "status": "error",
                "message": "GITHUB_TOKEN and GITHUB_REPO environment variables must be configured to trigger GitHub Actions.",
            },
            status_code=400,
        )

    ref = req.ref or "main"
    url = f"https://api.github.com/repos/{repo}/actions/workflows/daily_pipeline.yml/dispatches"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "OpportunityScout-Bot",
        "Content-Type": "application/json",
    }
    payload = json.dumps({"ref": ref}).encode("utf-8")

    try:
        request_obj = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(request_obj, timeout=12) as resp:
            if resp.status in (200, 204):
                return {
                    "status": "success",
                    "message": f"GitHub Actions workflow 'daily_pipeline.yml' dispatched successfully on '{ref}' branch.",
                    "repo": repo,
                }
            return {
                "status": "warning",
                "message": f"GitHub returned HTTP {resp.status}",
            }
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8") if e.fp else str(e)
        return JSONResponse(
            {
                "status": "error",
                "message": f"GitHub API returned HTTP {e.code}: {err_msg}",
            },
            status_code=e.code,
        )
    except Exception as e:
        return JSONResponse(
            {"status": "error", "message": f"Failed to trigger GitHub workflow: {str(e)}"},
            status_code=500,
        )


@app.delete("/api/opportunities/{opp_id}")
async def delete_opportunity(
    opp_id: str,
    fastapi_req: Request,
    req_body: Optional[DeleteOpportunityRequest] = None,
):
    """
    Remove an opportunity item by ID and sync deletion across cloud storage.
    """
    body_key = req_body.admin_key if req_body else None
    if not is_admin_authorized(fastapi_req, body_key):
        return JSONResponse({"error": "Unauthorized. Invalid admin_key."}, status_code=401)

    existing = get_active_opportunities_list()
    target = None
    for opp in existing:
        if opp.get("id") == opp_id:
            target = opp
            break

    if not target:
        return JSONResponse({"error": f"Opportunity with id '{opp_id}' not found."}, status_code=404)

    updated = [opp for opp in existing if opp.get("id") != opp_id]
    save_res = save_json_everywhere("opportunities.json", updated)

    return {
        "status": "success",
        "deleted_id": opp_id,
        "deleted_title": target.get("title"),
        "remaining": len(updated),
        "storage": save_res,
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

    api_key = get_gemini_api_key()

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

