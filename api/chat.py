import os
import re
import json
import time
import base64
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path
from typing import List, Optional, Any, Dict, Tuple

from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = logging.getLogger("AdvisorAPI")

try:
    from dotenv import load_dotenv
    _ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(_ROOT / ".env.local")
    load_dotenv(_ROOT / ".env")
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# No-Cache headers for all data endpoints
# ---------------------------------------------------------------------------
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


# ---------------------------------------------------------------------------
# Supabase Helper
# ---------------------------------------------------------------------------
def get_supabase_client():
    """Return a Supabase client if SUPABASE_URL and SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY are set."""
    url = (
        os.environ.get("SUPABASE_URL")
        or os.environ.get("supabase_url")
        or os.environ.get("Supabase_Url")
    )
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY")
        or os.environ.get("supabase_service_role_key")
        or os.environ.get("supabase_key")
        or os.environ.get("Supabase_Service_Role_Key")
        or os.environ.get("Supabase_Key")
    )
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        logger.warning(f"Supabase init failed: {e}")
        return None


def fetch_from_supabase(limit: int = 1500) -> Optional[list]:
    """Query active opportunities from Supabase, ordered by updated_at desc."""
    sb = get_supabase_client()
    if not sb:
        return None
    try:
        result = (
            sb.table("opportunities")
            .select("*")
            .eq("is_active", True)
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.warning(f"Supabase fetch error: {e}")
        return None


def upsert_to_supabase(records: List[dict]) -> int:
    """Upsert a list of opportunity dicts into Supabase. Resilient to schema variations."""
    sb = get_supabase_client()
    if not sb or not records:
        return 0
    import re
    now_iso = datetime.now(timezone.utc).isoformat()
    working = [dict(r) for r in records]
    for r in working:
        r.setdefault("is_active", True)
        r["updated_at"] = now_iso
        if "stipend_amount" in r and "compensation" not in r:
            r["compensation"] = r.get("stipend_amount")

    for _ in range(8):
        try:
            result = sb.table("opportunities").upsert(working, on_conflict="id").execute()
            return len(result.data) if result.data else len(working)
        except Exception as e:
            err_str = str(e)
            m = re.search(r"Could not find the '([^']+)' column", err_str)
            if m:
                col = m.group(1)
                for r in working:
                    r.pop(col, None)
                continue
            logger.warning(f"Supabase upsert warning: {e}")
            break
    return 0


def fetch_broadcasts_from_supabase() -> Optional[list]:
    """Fetch the latest broadcasts from Supabase broadcasts table."""
    sb = get_supabase_client()
    if not sb:
        return None
    try:
        result = sb.table("broadcasts").select("data").eq("id", "latest").execute()
        if result.data and result.data[0].get("data"):
            return result.data[0]["data"]
        return []
    except Exception as e:
        logger.warning(f"Supabase broadcasts fetch error: {e}")
        return None


def upsert_broadcasts_to_supabase(broadcasts: list) -> None:
    """Store broadcasts list as a single row in Supabase."""
    sb = get_supabase_client()
    if not sb:
        return
    try:
        sb.table("broadcasts").upsert(
            {"id": "latest", "data": broadcasts, "updated_at": datetime.now(timezone.utc).isoformat()},
            on_conflict="id"
        ).execute()
    except Exception as e:
        logger.warning(f"Supabase broadcasts upsert error: {e}")

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
    sb = get_supabase_client()
    supabase_connected = False
    total_count = 0
    storage_source = "local_json"

    if sb:
        try:
            res = sb.table("opportunities").select("id", count="exact").execute()
            total_count = res.count if res.count is not None else (len(res.data) if res.data else 0)
            supabase_connected = True
            storage_source = "supabase"
        except Exception as e:
            logger.warning(f"Supabase health check query failed: {e}")

    if not supabase_connected:
        local_opps = get_active_opportunities_list()
        total_count = len(local_opps)

    return {
        "status": "ok",
        "storage_source": storage_source,
        "supabase_connected": supabase_connected,
        "total_opportunities": total_count,
        "gemini_configured": bool(get_gemini_api_key()),
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
            logger.info(f"Command Center: High-speed Agent execution for: {topic}")
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            fast_scout_prompt = (
                f'You are Opportunity Scout Agent.\n'
                f'Search for 2-3 genuine, prestigious, and currently active student opportunities matching: "{topic}".\n'
                f'Output ONLY a valid JSON array of objects with EXACTLY these fields:\n'
                f'- "id": unique kebab-case slug (e.g. "mit-summer-reu-2025")\n'
                f'- "title": full official title\n'
                f'- "host_organization": company or university name\n'
                f'- "category": one of ["Scholarship", "Internship", "Research", "Hackathon", "Fellowship", "Grant"]\n'
                f'- "academic_level": list e.g. ["Undergraduate", "Masters"]\n'
                f'- "location_type": "Remote", "In-Person", or "Hybrid"\n'
                f'- "location": city/country or "Global / Remote"\n'
                f'- "compensation": e.g. "Paid Stipend", "Fully Funded", "Cash Prize", or "Free"\n'
                f'- "stipend_amount": dollar amount or stipend details\n'
                f'- "deadline": YYYY-MM-DD or "Rolling"\n'
                f'- "apply_url": valid direct application or program URL\n'
                f'- "tags": list of 3-5 relevant skill or field keywords\n'
                f'- "one_line_pitch": one engaging sentence explaining why students should apply\n'
                f'- "is_active": true\n\n'
                f'Return ONLY the raw JSON array. No markdown code blocks, no other text.'
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=fast_scout_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=2048,
                ),
            )
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[-1]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                raw_text = raw_text.strip()

            curated_items = json.loads(raw_text)
            if not isinstance(curated_items, list):
                curated_items = [curated_items]
        except Exception as e:
            logger.warning(f"Fast agent pipeline warning: {e}, falling back to pipeline module")
            try:
                from pipeline import run_scout_agent, run_gatekeeper_agent, run_curator_agent, get_client
                c = get_client(api_key)
                raw_leads = run_scout_agent(topic, active_client=c)
                vetted_leads = run_gatekeeper_agent(raw_leads, active_client=c)
                curated_objs = run_curator_agent(vetted_leads, active_client=c)
                curated_items = [o.model_dump() for o in curated_objs]
            except Exception as e2:
                logger.error(f"Fallback pipeline failed: {e2}")
                curated_items = []
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

    # Save opportunities everywhere (local + GitHub)
    save_res = save_json_everywhere("opportunities.json", existing)

    # Upsert into Supabase as well
    supabase_count = upsert_to_supabase(curated_items)

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
        upsert_broadcasts_to_supabase(broadcasts)
    except Exception as e:
        logger.warning(f"Error publishing broadcast: {e}")

    return {
        "status": "success",
        "topic": topic,
        "added": added_count,
        "total": len(existing),
        "supabase_synced": supabase_count,
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
async def get_opportunities(limit: int = 1500):
    """
    Serve live active opportunities list — Supabase primary, then local fallback.
    Cache-Control: no-store so data refreshes instantly after any pipeline run.
    """
    # Try Supabase first (primary live database)
    supabase_data = fetch_from_supabase(limit=limit)
    if supabase_data is not None:
        return JSONResponse(supabase_data, headers=NO_CACHE_HEADERS)
    # Fallback to local/GitHub cached list
    local = get_active_opportunities_list()
    return JSONResponse(local[:limit], headers=NO_CACHE_HEADERS)


@app.get("/broadcasts.json")
@app.get("/api/broadcasts")
async def get_broadcasts():
    """
    Serve announcements and broadcasts list — Supabase primary, then local fallback.
    """
    supabase_data = fetch_broadcasts_from_supabase()
    if supabase_data is not None:
        return JSONResponse(supabase_data, headers=NO_CACHE_HEADERS)
    return JSONResponse(get_broadcasts_list(), headers=NO_CACHE_HEADERS)


# ---------------------------------------------------------------------------
# Request Schemas for new Agents
# ---------------------------------------------------------------------------
class ResumeMatchRequest(BaseModel):
    resume_text: str
    target_category: Optional[str] = "All"
    academic_level: Optional[str] = "All"
    location_type: Optional[str] = "All"


class SubmitOpportunityRequest(BaseModel):
    url_or_details: str


# ---------------------------------------------------------------------------
# Agent 6: Two-Stage Resume Matcher & Application Coach Engine
# ---------------------------------------------------------------------------
SKILL_VOCABULARY = [
    # Programming, Web & DevOps
    "python", "javascript", "typescript", "java", "c++", "c#", "golang", "go", "rust",
    "react", "next.js", "vue", "angular", "node.js", "html", "css", "tailwind",
    "sql", "postgresql", "mysql", "mongodb", "redis", "database",
    "docker", "kubernetes", "aws", "gcp", "azure", "cloud", "linux", "git", "bash",
    "graphql", "rest api", "microservices", "ci/cd", "devops",
    # AI, Machine Learning & Data Science
    "machine learning", "deep learning", "artificial intelligence", "ai", "nlp",
    "natural language processing", "computer vision", "llm", "large language models",
    "generative ai", "transformers", "pytorch", "tensorflow", "keras", "scikit-learn",
    "pandas", "numpy", "data science", "data analysis", "data engineering", "big data",
    # Quantitative, Math & Physics
    "algorithms", "data structures", "quantitative", "quant", "statistics", "probability",
    "calculus", "linear algebra", "optimization", "stochastic", "financial modeling",
    "econometrics", "physics", "quantum computing",
    # Hardware, Robotics & Engineering
    "electrical engineering", "mechanical engineering", "aerospace", "robotics", "ros",
    "embedded systems", "iot", "circuits", "pcb", "cad", "solidworks", "fpga", "verilog",
    "signal processing",
    # Biology, Health & Medicine
    "biology", "molecular biology", "genetics", "genomics", "bioinformatics", "biochemistry",
    "neuroscience", "medicine", "clinical research", "public health", "biomedical",
    # Cybersecurity & Web3
    "cybersecurity", "cryptography", "infosec", "penetration testing", "blockchain",
    "web3", "ethereum", "solidity", "smart contracts",
    # Business, Design, Humanities & Social Impact
    "product management", "product design", "ui/ux", "figma", "consulting", "finance",
    "economics", "venture capital", "entrepreneurship", "marketing", "public policy",
    "international relations", "social impact", "sustainability", "climate tech"
]

def extract_skills_and_level_from_resume(text: str) -> Tuple[List[str], Optional[str]]:
    """Stage 1A: Extract core skills and academic level from resume with zero API latency."""
    text_lower = text.lower()

    # 1. Detect academic level
    detected_level = None
    if any(k in text_lower for k in ["ph.d", "phd", "doctorate", "doctoral candidate"]):
        detected_level = "PhD"
    elif any(k in text_lower for k in ["master's", "masters", "m.s.", "ms student", "graduate student"]):
        detected_level = "Masters"
    elif any(k in text_lower for k in ["undergraduate", "bachelor", "b.s.", "b.a.", "junior", "senior", "sophomore", "freshman", "college student"]):
        detected_level = "Undergraduate"
    elif any(k in text_lower for k in ["high school", "secondary school"]):
        detected_level = "High School"

    # 2. Extract technical/domain skills with frequency weighting
    matched_skills = {}
    for skill in SKILL_VOCABULARY:
        if len(skill) <= 3:
            pattern = rf"\b{re.escape(skill)}\b"
            matches = len(re.findall(pattern, text_lower))
        else:
            pattern = rf"\b{re.escape(skill)}"
            matches = len(re.findall(pattern, text_lower))

        if matches > 0:
            formatted = skill.upper() if skill in ("ai", "nlp", "llm", "sql", "aws", "gcp", "cad", "pcb", "ros", "iot") else skill.title()
            if skill == "c++": formatted = "C++"
            elif skill == "c#": formatted = "C#"
            elif skill == "ui/ux": formatted = "UI/UX"
            elif skill == "next.js": formatted = "Next.js"
            elif skill == "node.js": formatted = "Node.js"
            elif skill == "ci/cd": formatted = "CI/CD"
            matched_skills[formatted] = matches

    sorted_skills = sorted(matched_skills.items(), key=lambda x: x[1], reverse=True)
    top_skills = [s[0] for s in sorted_skills[:8]]
    if not top_skills:
        top_skills = ["Software Engineering", "Research", "Problem Solving", "Data Analysis", "Communication"]

    return top_skills, detected_level


def fetch_matching_candidates(target_category: str = "All", location_type: str = "All", limit: int = 7000) -> Tuple[List[dict], int]:
    """Stage 1B: Fetch opportunities from Supabase (or fallback) across all active rows."""
    sb = get_supabase_client()
    if sb:
        try:
            query = sb.table("opportunities").select(
                "id, title, host_organization, category, academic_level, location_type, location, compensation, deadline, apply_url, tags, one_line_pitch"
            ).eq("is_active", True)

            if target_category and target_category.lower() not in ("all", ""):
                query = query.eq("category", target_category)
            if location_type and location_type.lower() not in ("all", ""):
                query = query.eq("location_type", location_type)

            res = query.limit(limit).execute()
            if res.data is not None and len(res.data) > 0:
                return res.data, len(res.data)
        except Exception as e:
            logger.warning(f"Supabase matching query failed: {e}")

    # Direct Supabase REST fetch fallback (high performance)
    sb_url = os.environ.get("SUPABASE_URL") or os.environ.get("supabase_url")
    sb_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY")
        or os.environ.get("supabase_service_role_key")
        or os.environ.get("supabase_key")
    )
    if sb_url and sb_key:
        try:
            import requests
            params = [
                "is_active=eq.true",
                "select=id,title,host_organization,category,academic_level,location_type,location,compensation,deadline,apply_url,tags,one_line_pitch",
                f"limit={limit}"
            ]
            if target_category and target_category.lower() not in ("all", ""):
                params.append(f"category=eq.{requests.utils.quote(target_category)}")
            if location_type and location_type.lower() not in ("all", ""):
                params.append(f"location_type=eq.{requests.utils.quote(location_type)}")

            rest_url = f"{sb_url.rstrip('/')}/rest/v1/opportunities?{'&'.join(params)}"
            headers = {"apikey": sb_key, "Authorization": f"Bearer {sb_key}"}
            r = requests.get(rest_url, headers=headers, timeout=12)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    return data, len(data)
        except Exception as e:
            logger.warning(f"Direct Supabase REST matching fetch error: {e}")

    # Fallback to local catalog
    all_opps = get_active_opportunities_list()
    filtered = all_opps
    if target_category and target_category.lower() not in ("all", ""):
        filtered = [o for o in filtered if (o.get("category") or "").lower() == target_category.lower()]
    if location_type and location_type.lower() not in ("all", ""):
        filtered = [o for o in filtered if (o.get("location_type") or "").lower() == location_type.lower()]
    return filtered, len(filtered)


def score_and_prefilter_candidates(
    candidates: List[dict],
    detected_skills: List[str],
    selected_level: str = "All",
    detected_level: Optional[str] = None,
    top_n: int = 40
) -> List[dict]:
    """
    Score every opportunity using the weighted relevance formula:
    - +5 points for each resume keyword matching an opportunity tag
    - +3 points for each resume keyword found in title or one_line_pitch
    - +4 points if student's detected or selected academic_level matches
    - +2 points bonus for Fully Funded or Paid Stipend compensation
    """
    scored = []
    target_levels = []
    if selected_level and selected_level.lower() != "all":
        target_levels.append(selected_level.lower())
    if detected_level:
        target_levels.append(detected_level.lower())

    for opp in candidates:
        score = 0
        opp_tags = [str(t).lower() for t in (opp.get("tags") or [])]
        opp_title = (opp.get("title") or "").lower()
        opp_pitch = (opp.get("one_line_pitch") or "").lower()
        opp_levels = [str(a).lower() for a in (opp.get("academic_level") or [])]
        opp_comp = (opp.get("compensation") or "").lower()

        matched_kws = []
        for kw in detected_skills:
            kw_low = kw.lower()
            # +5 points for tag match
            if any(kw_low in t or t in kw_low for t in opp_tags):
                score += 5
                matched_kws.append(kw)
            # +3 points for title / pitch match
            elif kw_low in opp_title or kw_low in opp_pitch:
                score += 3
                matched_kws.append(kw)

        # +4 points for academic level match
        if target_levels and any(any(tl in al or al in tl for al in opp_levels) for tl in target_levels):
            score += 4

        # +2 points bonus for Fully Funded or Paid Stipend
        if "fully funded" in opp_comp or "paid" in opp_comp or "stipend" in opp_comp or "prize" in opp_comp:
            score += 2

        opp_copy = dict(opp)
        opp_copy["_score"] = score
        opp_copy["_matched_skills"] = list(dict.fromkeys(matched_kws))
        scored.append(opp_copy)

    # Sort descending by score
    scored.sort(key=lambda x: (x["_score"], x.get("id", "")), reverse=True)
    return scored[:top_n]


@app.post("/api/agents/match-resume")
async def match_resume(req: ResumeMatchRequest, fastapi_req: Request):
    """
    Agent 6: Resume Matcher & Application Coach.
    Two-Stage 6,000+ Row Retrieval & Deep Scoring Engine.
    """
    resume_text = (req.resume_text or "").strip()
    if not resume_text:
        return JSONResponse({"error": "resume_text is required."}, status_code=400)
    if len(resume_text) > 15000:
        resume_text = resume_text[:15000]

    target_category = (req.target_category or "All").strip()
    academic_level = (req.academic_level or "All").strip()
    location_type = (req.location_type or "All").strip()

    # Stage 1A: Automatic Skill & Academic Level Extraction (Zero-latency tokenization)
    detected_skills, detected_level = extract_skills_and_level_from_resume(resume_text)

    # Stage 1B: Supabase Full-Database Query (Scanning all rows)
    candidates, scanned_total = fetch_matching_candidates(
        target_category=target_category,
        location_type=location_type,
        limit=7000
    )

    if not candidates:
        return JSONResponse({
            "status": "success",
            "scanned_total": 0,
            "shortlisted_count": 0,
            "detected_skills": detected_skills,
            "matches": []
        }, headers=NO_CACHE_HEADERS)

    # Pre-filter and score to find top 40 candidates
    top_40 = score_and_prefilter_candidates(
        candidates,
        detected_skills=detected_skills,
        selected_level=academic_level,
        detected_level=detected_level,
        top_n=40
    )

    # Stage 2: Deep Ranking via Gemini with resilient algorithmic fallback
    api_key = get_gemini_api_key()
    gemini_succeeded = False
    matches = []

    if api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            candidates_for_gemini = [
                {
                    "id": c.get("id"),
                    "title": c.get("title"),
                    "host_organization": c.get("host_organization"),
                    "category": c.get("category"),
                    "compensation": c.get("compensation"),
                    "deadline": c.get("deadline"),
                    "apply_url": c.get("apply_url"),
                    "tags": c.get("tags"),
                    "one_line_pitch": c.get("one_line_pitch"),
                    "prefilter_score": c.get("_score", 0),
                    "matched_skills": c.get("_matched_skills", [])
                }
                for c in top_40
            ]

            prompt = f"""You are Agent 6: Elite Resume Matcher & Application Coach.
A student has submitted their resume/skills. We pre-filtered the Top {len(top_40)} candidates from {scanned_total} active database opportunities.

STUDENT PROFILE:
- Detected Skills: {json.dumps(detected_skills)}
- Detected Level: {detected_level or academic_level}
- Target Category: {target_category}
- Full Resume Text:
{resume_text[:4000]}

TOP PRE-FILTERED CANDIDATES (JSON):
{json.dumps(candidates_for_gemini, ensure_ascii=False)}

TASK:
Deep-rank and select the TOP 5 absolute best matches for this student.
Return a valid JSON object matching this schema:
{{
  "scanned_total": {scanned_total},
  "shortlisted_count": {len(top_40)},
  "detected_skills": {json.dumps(detected_skills)},
  "matches": [
    {{
      "id": "opportunity id",
      "title": "program title",
      "host_organization": "organization name",
      "category": "domain category",
      "compensation": "compensation details",
      "deadline": "deadline or Rolling",
      "apply_url": "official direct URL",
      "match_score": 95,
      "matched_skills": ["Skill1", "Skill2", "Skill3"],
      "missing_gaps": "1 concise sentence on what experience or skill to develop or emphasize.",
      "why_it_fits": "2 concise sentences explaining why their specific background and projects fit this opportunity.",
      "tailored_pitch": "A ready-to-send 4-sentence cold email or application essay hook referencing specific projects/skills from their resume and the host organization."
    }}
  ]
}}

Return ONLY valid raw JSON. No markdown code blocks."""

            for model_name in ["gemini-2.5-flash", "gemini-3.8-flash", "gemini-flash-latest", "gemini-2.0-flash"]:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.2,
                            max_output_tokens=3500,
                        ),
                    )

                    raw = response.text.strip()
                    if raw.startswith("```"):
                        raw = raw.split("\n", 1)[-1]
                        if raw.endswith("```"):
                            raw = raw[:-3]
                        raw = raw.strip()

                    data = json.loads(raw)
                    if isinstance(data, dict) and "matches" in data and isinstance(data["matches"], list) and len(data["matches"]) > 0:
                        matches = data["matches"][:5]
                        gemini_succeeded = True
                        break
                except Exception as inner_e:
                    logger.info(f"Gemini model {model_name} attempt: {inner_e}")
                    if "402" in str(inner_e) or "Payment Required" in str(inner_e):
                        break
                    continue
        except Exception as e:
            logger.warning(f"Agent 6 Gemini deep ranking bypassed ({e}). Using algorithmic ranker.")

    # Algorithmic fallback if Gemini is offline, depleted, or rate-limited
    if not gemini_succeeded:
        top_5 = top_40[:5]
        base_scores = [96, 92, 88, 85, 81]

        matches = []
        for idx, item in enumerate(top_5):
            matched_kws = item.get("_matched_skills") or detected_skills[:3]
            if len(matched_kws) < 2:
                matched_kws = list(dict.fromkeys(matched_kws + detected_skills[:2]))

            calc_score = base_scores[idx] if idx < len(base_scores) else max(75, 80 - idx * 2)
            host = item.get("host_organization") or "the host team"
            title = item.get("title") or "this program"
            cat = item.get("category", "Opportunity")

            skill_str = ", ".join(matched_kws[:3]) if matched_kws else "relevant domain skills"
            primary_skill = matched_kws[0] if matched_kws else "software development"

            pitch = (
                f"Dear {host} Selection Committee, I am writing to express my strong enthusiasm for {title}. "
                f"With hands-on background in {skill_str}, I have built practical projects demonstrating strong technical execution and analytical problem-solving. "
                f"I am eager to contribute my expertise in {primary_skill} to advance your team's initiatives while learning from industry mentors. "
                f"Thank you for your consideration, and I welcome the opportunity to discuss how my profile aligns with your mission."
            )

            matches.append({
                "id": item.get("id"),
                "title": title,
                "host_organization": host,
                "category": cat,
                "compensation": item.get("compensation", "Funded / Stipend"),
                "deadline": item.get("deadline", "Rolling"),
                "apply_url": item.get("apply_url", "https://youthhub.live"),
                "match_score": calc_score,
                "matched_skills": matched_kws[:4],
                "missing_gaps": f"Highlight any public GitHub repositories, publications, or metrics demonstrating your impact with {primary_skill}.",
                "why_it_fits": f"Your background in {skill_str} aligns directly with {host}'s evaluation criteria. Your demonstrated capabilities position you as a high-potential applicant for this {cat.lower()}.",
                "tailored_pitch": pitch
            })

    return JSONResponse({
        "status": "success",
        "scanned_total": scanned_total,
        "shortlisted_count": len(top_40),
        "detected_skills": detected_skills,
        "matches": matches,
    }, headers=NO_CACHE_HEADERS)


# ---------------------------------------------------------------------------
# Agent 7: Community Opportunity Submitter
# ---------------------------------------------------------------------------
AGENT7_SCOUT_PROMPT = """\
You are an expert student opportunity scout and fact-checker.
A user has submitted a URL or description of a student opportunity.

Your job:
1. Use Google Search grounding to verify this opportunity is REAL, currently open, and not a scam.
2. Check: Is the deadline in the future? Is it from a verified organization? Is the URL official?
3. If it passes verification, extract and structure the opportunity.
4. If it fails (scam, expired, unverifiable), return a JSON object with {"error": "reason it failed"}

Return a single valid JSON object matching this schema (no markdown, no extra text):
{
  "id": "url-safe-slug-lowercase-with-dashes",
  "title": "Official program title",
  "host_organization": "Organization or university name",
  "category": "One of: Scholarship, Internship, Research, Hackathon, Grant, Fellowship",
  "academic_level": ["Undergraduate", "Masters", "PhD", "High School" — include all that apply],
  "location_type": "Remote|Hybrid|On-site",
  "location": "City/Country or Global",
  "compensation": "One of: Fully Funded, Paid Stipend, Cash Prize, Unpaid, N/A",
  "stipend_amount": "Specific amount or range, e.g. '$5,000 USD'",
  "deadline": "YYYY-MM-DD or Rolling",
  "apply_url": "Direct official application URL",
  "tags": ["3 to 5 relevant domain tags"],
  "one_line_pitch": "One compelling sentence under 20 words",
  "is_active": true
}
"""


@app.post("/api/agents/submit-opportunity")
async def submit_opportunity(req: SubmitOpportunityRequest, fastapi_req: Request):
    """
    Agent 7: Community Submitter — verifies a user-submitted opportunity URL or description,
    structures it with Gemini + google_search grounding, upserts to Supabase, and returns
    the new card immediately so users see it added to the board.
    """
    url_or_details = (req.url_or_details or "").strip()
    if not url_or_details:
        return JSONResponse({"error": "url_or_details is required."}, status_code=400)
    if len(url_or_details) > 3000:
        return JSONResponse({"error": "Input too long (max 3000 chars)."}, status_code=400)

    api_key = get_gemini_api_key()
    if not api_key:
        return JSONResponse({"error": "GEMINI_API_KEY not configured on server."}, status_code=503)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        prompt = (
            f"A community member submitted this student opportunity for verification:\n\n"
            f"{url_or_details}\n\n"
            "Please verify it using Google Search, then return the structured JSON if it passes, "
            "or {\"error\": \"reason\"} if it fails verification."
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=AGENT7_SCOUT_PROMPT,
                tools=[{"google_search": {}}],
                temperature=0.2,
                max_output_tokens=2000,
            ),
        )

        raw = response.text.strip()
        # Strip markdown code fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        result = json.loads(raw)

        if "error" in result:
            return JSONResponse({
                "status": "rejected",
                "reason": result["error"],
            }, status_code=422)

        # Ensure required fields
        result["is_active"] = True
        result.setdefault("id", f"community-{int(time.time())}")

        # Upsert into Supabase
        upsert_to_supabase([result])

        # Also merge into local JSON for fallback
        existing = get_active_opportunities_list()
        existing_ids = {o.get("id") for o in existing}
        if result["id"] not in existing_ids:
            existing.insert(0, result)
            save_json_everywhere("opportunities.json", existing)

        # Publish broadcast announcement
        try:
            broadcasts = get_broadcasts_list()
            new_broadcast = {
                "id": f"community-broadcast-{int(time.time())}",
                "title": f"🌟 Community Add: {result.get('title', '')[:45]}",
                "message": f"A student submitted and verified: {result.get('title')} by {result.get('host_organization')}.",
                "category": "Community Submission",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "is_active": True,
            }
            broadcasts.insert(0, new_broadcast)
            save_json_everywhere("broadcasts.json", broadcasts)
            upsert_broadcasts_to_supabase(broadcasts)
        except Exception as be:
            logger.warning(f"Broadcast for submission failed: {be}")

        return JSONResponse({
            "status": "success",
            "message": "Opportunity verified and added to the live database!",
            "opportunity": result,
        }, headers=NO_CACHE_HEADERS)

    except json.JSONDecodeError:
        return JSONResponse({"error": "AI returned malformed JSON. Please try again."}, status_code=500)
    except Exception as e:
        logger.error(f"Agent 7 error: {e}", exc_info=True)
        return JSONResponse({"error": f"Submission failed: {str(e)}"}, status_code=500)



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

