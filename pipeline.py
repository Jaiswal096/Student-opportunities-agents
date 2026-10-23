import os
import json
import logging
from typing import List
from datetime import datetime
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OpportunityPipeline")

def get_gemini_api_key() -> str:
    return (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("Gemini_Api_Key")
        or os.getenv("gemini_api_key")
        or os.getenv("GEMINI_KEY")
    )

API_KEY = get_gemini_api_key()
MODEL_NAME = "gemini-2.0-flash"
DB_FILE = "opportunities.json"

def get_client(api_key: str = None) -> genai.Client:
    key = api_key or get_gemini_api_key()
    if not key:
        raise ValueError("GEMINI_API_KEY environment variable is missing.")
    return genai.Client(api_key=key)

client = None
if API_KEY:
    try:
        client = get_client(API_KEY)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Pydantic Schema for Agent 3 (Curator)
# ---------------------------------------------------------------------------
class Opportunity(BaseModel):
    id: str = Field(description="Unique slug identifier (e.g. 'mit-summer-reu-2026')")
    title: str = Field(description="Official title of the opportunity")
    host_organization: str = Field(description="Organization, university, or company name")
    category: str = Field(description="One of: Scholarship, Internship, Research, Hackathon, Grant, Fellowship")
    academic_level: List[str] = Field(description="Target levels, e.g., ['Undergraduate', 'Graduate']")
    location_type: str = Field(description="One of: Remote, Hybrid, On-site")
    location: str = Field(description="City/Country or 'Global'")
    compensation: str = Field(description="One of: Fully Funded, Paid Stipend, Unpaid, Cash Prize, N/A")
    deadline: str = Field(description="YYYY-MM-DD format, or 'Rolling'")
    apply_url: str = Field(description="Direct official link to application or program")
    tags: List[str] = Field(description="3 to 5 domain tags, e.g. ['AI', 'Data Science', 'Python']")
    one_line_pitch: str = Field(description="Concise sentence under 20 words on why this is high-value")


# ---------------------------------------------------------------------------
# Agent 1: The Scout (Web & Feed Discovery)
# ---------------------------------------------------------------------------
SCOUT_PROMPT = """
You are an autonomous Scout Agent specialized in discovering newly posted, active student opportunities.
Your target areas:
1. Academic Research Programs & Summer Fellowships (REUs, lab positions)
2. Technology & Engineering Internships
3. Need-based & Merit Scholarships
4. Hackathons & Open Innovation Challenges

Rules:
- Focus on listings open for applications right now.
- Extract: Title, Host Organization, Program Type, Target Academic Level, Application/Info URL, and Deadline.
- Output raw structured bullet points for each discovered lead. Do not add conversational commentary.
"""

def run_scout_agent(search_query: str, active_client: genai.Client = None) -> str:
    c = active_client or client or get_client()
    logger.info("Executing Agent 1 (Scout)...")
    response = c.models.generate_content(
        model=MODEL_NAME,
        contents=f"Find the newest active student opportunities for: {search_query}",
        config=types.GenerateContentConfig(
            system_instruction=SCOUT_PROMPT,
            tools=[{"google_search": {}}],
            temperature=0.3,
        ),
    )
    logger.info("Agent 1 discovery complete.")
    return response.text


# ---------------------------------------------------------------------------
# Agent 2: The Gatekeeper (Verification & Anti-Scam)
# ---------------------------------------------------------------------------
GATEKEEPER_PROMPT = """
You are an objective auditor responsible for vetting student opportunities.
Audit Rules:
1. DEADLINE CHECK: Verify that the deadline is in the future. Discard any expired listing.
2. SCAM DETECTION: Reject listings requiring mandatory application fees for internships/scholarships, unofficial WhatsApp/Telegram signup links, or unverified schemes.
3. OFFICIAL SOURCES: Ensure the destination link belongs to an authentic organization or recognized platform.
4. ACTIONABILITY: Discard vague listings that lack clear eligibility requirements.

Return ONLY vetted entries that passed all checks:
- Status: APPROVED
- Title: [Official Name]
- Host: [Organization]
- Verified Application URL: [URL]
- Verified Deadline: [Date or 'Rolling']
- Eligibility Summary: [Short bullet points]
"""

def run_gatekeeper_agent(raw_leads: str, active_client: genai.Client = None) -> str:
    c = active_client or client or get_client()
    logger.info("Executing Agent 2 (Gatekeeper)...")
    prompt = f"Audit the following raw student leads against all quality and safety rules:\n\n{raw_leads}"
    response = c.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=GATEKEEPER_PROMPT,
            temperature=0.1,
        ),
    )
    logger.info("Agent 2 verification complete.")
    return response.text


# ---------------------------------------------------------------------------
# Agent 3: The Curator (Structuring & Taxonomy)
# ---------------------------------------------------------------------------
CURATOR_PROMPT = """
You are a data structuring specialist. Transform the vetted student opportunities into 
a normalized list matching the required schema. Ensure IDs are URL-safe slugs, categories 
are normalized, and all dates follow YYYY-MM-DD or 'Rolling'.
"""

def run_curator_agent(vetted_leads: str, active_client: genai.Client = None) -> List[Opportunity]:
    c = active_client or client or get_client()
    logger.info("Executing Agent 3 (Curator)...")
    prompt = f"Convert these vetted opportunities into structured records:\n\n{vetted_leads}"
    
    response = c.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=CURATOR_PROMPT,
            response_mime_type="application/json",
            response_schema=list[Opportunity],
            temperature=0.1,
        ),
    )
    
    data = json.loads(response.text)
    curated = [Opportunity(**item) for item in data]
    logger.info(f"Agent 3 formatted {len(curated)} standardized records.")
    return curated


def run_topic_pipeline(topic: str, api_key: str = None) -> List[Opportunity]:
    """Execute Agent 1 -> Agent 2 -> Agent 3 for a specific target topic."""
    c = get_client(api_key)
    raw = run_scout_agent(topic, active_client=c)
    vetted = run_gatekeeper_agent(raw, active_client=c)
    curated = run_curator_agent(vetted, active_client=c)
    return curated


# ---------------------------------------------------------------------------
# Database Management: Atomic Upsert & Deduplication
# ---------------------------------------------------------------------------
def update_opportunities_database(new_opportunities: List[Opportunity], db_path: str = DB_FILE):
    logger.info(f"Updating database: {db_path}")
    existing_items = []
    
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                existing_items = json.load(f)
        except json.JSONDecodeError:
            logger.warning("Existing database was empty or corrupt. Initializing new list.")
            existing_items = []

    existing_by_id = {item.get("id"): item for item in existing_items}
    existing_urls = {item.get("apply_url") for item in existing_items}

    added_count = 0
    updated_count = 0

    for opp in new_opportunities:
        opp_dict = opp.model_dump()
        opp_id = opp_dict["id"]
        opp_url = opp_dict["apply_url"]

        if opp_id in existing_by_id:
            existing_by_id[opp_id] = opp_dict
            updated_count += 1
        elif opp_url in existing_urls:
            for idx, item in enumerate(existing_items):
                if item.get("apply_url") == opp_url:
                    existing_items[idx] = opp_dict
                    break
            updated_count += 1
        else:
            existing_items.append(opp_dict)
            existing_by_id[opp_id] = opp_dict
            existing_urls.add(opp_url)
            added_count += 1

    # Write to both root folder and public/ directory for CDN sync
    root_path = Path(__file__).resolve().parent / "opportunities.json"
    public_path = Path(__file__).resolve().parent / "public" / "opportunities.json"
    public_path.parent.mkdir(parents=True, exist_ok=True)

    with open(root_path, "w", encoding="utf-8") as f:
        json.dump(existing_items, f, indent=2, ensure_ascii=False)
    with open(public_path, "w", encoding="utf-8") as f:
        json.dump(existing_items, f, indent=2, ensure_ascii=False)

    logger.info(f"Database sync complete: {added_count} new entries added, {updated_count} existing records updated. Synced to both root and public/. Total records: {len(existing_items)}")


# ---------------------------------------------------------------------------
# Pipeline Orchestrator
# ---------------------------------------------------------------------------
def run_daily_pipeline(search_topics: List[str]):
    all_curated = []
    
    for topic in search_topics:
        logger.info(f"--- Processing Domain: {topic} ---")
        try:
            raw_leads = run_scout_agent(topic)
            vetted_leads = run_gatekeeper_agent(raw_leads)
            curated_entries = run_curator_agent(vetted_leads)
            all_curated.extend(curated_entries)
        except Exception as e:
            logger.error(f"Error processing topic '{topic}': {str(e)}", exc_info=True)

    if all_curated:
        update_opportunities_database(all_curated)
    else:
        logger.warning("No opportunities cleared the gatekeeper audit during this run.")


if __name__ == "__main__":
    daily_topics = [
        "Undergraduate Summer Research Fellowships in Computer Science and AI 2026",
        "Global Student Open Source Grants and Tech Fellowships 2026",
        "STEM Undergraduate Scholarships with upcoming deadlines"
    ]
    
    run_daily_pipeline(daily_topics)
