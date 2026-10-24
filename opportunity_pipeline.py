"""
Opportunity Pipeline Runner — Full Orchestration with Supabase
Discovers, verifies, and syncs curated opportunities to:
  1. Supabase PostgreSQL (primary live database, 1,000+ scale)
  2. Local opportunities.json + public/opportunities.json (fallback)
Also runs janitor: marks past-deadline opportunities as is_active=False.
"""
import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Load .env for local development
try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env.local")
    load_dotenv(_ROOT / ".env")
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OpportunityPipeline")

from pipeline import run_daily_pipeline, run_topic_pipeline, update_opportunities_database, Opportunity

# ---------------------------------------------------------------------------
# Supabase Helper
# ---------------------------------------------------------------------------
def get_supabase_client():
    """Return a Supabase client if credentials are configured, else None."""
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


def upsert_opportunities_to_supabase(opportunities: List[dict]) -> int:
    """
    Bulk upsert opportunities into Supabase public.opportunities table.
    Returns count of rows upserted, or 0 on failure.
    """
    sb = get_supabase_client()
    if not sb:
        logger.info("Supabase not configured — skipping upsert.")
        return 0
    if not opportunities:
        return 0

    import re
    now_iso = datetime.now(timezone.utc).isoformat()
    working = []
    for opp in opportunities:
        r = dict(opp)
        r.setdefault("is_active", True)
        r["updated_at"] = now_iso
        if "stipend_amount" in r and "compensation" not in r:
            r["compensation"] = r.get("stipend_amount")
        working.append(r)

    for _ in range(8):
        try:
            result = sb.table("opportunities").upsert(working, on_conflict="id").execute()
            count = len(result.data) if result.data else len(working)
            logger.info(f"Supabase upsert: {count} opportunities synced.")
            return count
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


def migrate_json_to_supabase():
    """
    One-time migration: read existing opportunities.json and upsert into Supabase
    so we never start with an empty database.
    """
    sb = get_supabase_client()
    if not sb:
        return

    json_paths = [
        _ROOT / "opportunities.json",
        _ROOT / "public" / "opportunities.json",
    ]

    existing = []
    for p in json_paths:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    existing = data
                    logger.info(f"Migration source: {p} ({len(data)} items)")
                    break
            except Exception:
                continue

    if not existing:
        logger.info("No local opportunities.json to migrate.")
        return

    # Only migrate items not already in Supabase
    try:
        result = sb.table("opportunities").select("id").execute()
        existing_ids = {row["id"] for row in (result.data or [])}
        to_migrate = [o for o in existing if o.get("id") not in existing_ids]
        if to_migrate:
            upsert_opportunities_to_supabase(to_migrate)
            logger.info(f"Migrated {len(to_migrate)} items from local JSON to Supabase.")
        else:
            logger.info("All local items already exist in Supabase — no migration needed.")
    except Exception as e:
        logger.warning(f"Migration check failed: {e}")


def upsert_broadcasts_to_supabase(broadcasts: list):
    """Store the latest broadcasts list as a single row in public.broadcasts."""
    sb = get_supabase_client()
    if not sb:
        return
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        sb.table("broadcasts").upsert(
            {"id": "latest", "data": broadcasts, "updated_at": now_iso},
            on_conflict="id"
        ).execute()
        logger.info("Broadcasts synced to Supabase.")
    except Exception as e:
        logger.warning(f"Supabase broadcasts upsert error: {e}")


def run_janitor():
    """
    Mark opportunities with past YYYY-MM-DD deadlines as is_active=False
    in both Supabase and local JSON files.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info(f"Janitor running — today is {today}")

    # --- Supabase janitor ---
    sb = get_supabase_client()
    if sb:
        try:
            result = (
                sb.table("opportunities")
                .update({"is_active": False, "updated_at": datetime.now(timezone.utc).isoformat()})
                .lt("deadline", today)
                .neq("deadline", "Rolling")
                .eq("is_active", True)
                .execute()
            )
            deactivated = len(result.data) if result.data else 0
            logger.info(f"Janitor: marked {deactivated} expired opportunities inactive in Supabase.")
        except Exception as e:
            logger.warning(f"Supabase janitor error: {e}")

    # --- Local JSON janitor ---
    json_paths = [
        _ROOT / "opportunities.json",
        _ROOT / "public" / "opportunities.json",
    ]
    for p in json_paths:
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                continue
            changed = False
            for item in data:
                dl = item.get("deadline", "")
                if dl and dl != "Rolling" and dl < today and item.get("is_active", True):
                    item["is_active"] = False
                    changed = True
            if changed:
                p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                logger.info(f"Janitor: updated local {p}")
        except Exception as e:
            logger.warning(f"Janitor error for {p}: {e}")


# ---------------------------------------------------------------------------
# 12 Diverse Global Student Opportunity Topics
# ---------------------------------------------------------------------------
DAILY_TOPICS = [
    # CS / AI / ML
    "Undergraduate and Graduate AI Machine Learning Research Internships and Fellowships 2026-2027",
    # Engineering / Hardware
    "Global Undergraduate Engineering Hardware Robotics and Aerospace Internships 2026-2027",
    # Quantitative Finance / Math
    "Quantitative Finance Trading and Data Science Student Programs 2026-2027",
    # Biomedical / Life Sciences
    "Biomedical Neuroscience Pre-Med and Life Sciences Research REU Programs 2026-2027",
    # Humanities / Social Sciences / Policy
    "Humanities Social Sciences Public Policy and Law Fellowships for Students 2026-2027",
    # High School Programs
    "High School Summer Research Enrichment STEM Programs and Scholarships 2026-2027",
    # Global Scholarships (international)
    "Fully Funded Global International Scholarships for Undergraduate and Graduate Students 2026-2027",
    # Hackathons
    "Global Student Hackathons Innovation Competitions and Tech Challenges 2026-2027",
    # Open Source / Developer Grants
    "Open Source Developer Grants Fellowships and Paid Contributor Programs 2026-2027",
    # Diversity / Equity Fellowships
    "Diversity Equity Inclusion STEM Fellowships and Scholarships for Underrepresented Students 2026-2027",
    # Research REUs (NSF-style)
    "NSF REU and University Summer Undergraduate Research Experience Programs 2026-2027",
    # Startup / Entrepreneurship Grants
    "Student Startup Entrepreneurship Grants Accelerators and Venture Fellowships 2026-2027",
]


if __name__ == "__main__":
    logger.info("=== Starting Full Opportunity Pipeline ===")

    # Step 0: Migrate existing local JSON → Supabase (safe no-op if already done)
    logger.info("Step 0: Migrating local JSON to Supabase...")
    migrate_json_to_supabase()

    # Step 1: Janitor — expire past deadlines
    logger.info("Step 1: Running deadline janitor...")
    run_janitor()

    # Step 2: Run AI pipeline across all 12 topics
    logger.info(f"Step 2: Running pipeline across {len(DAILY_TOPICS)} topics...")
    all_curated: List[Opportunity] = []
    for topic in DAILY_TOPICS:
        logger.info(f"  Processing: {topic}")
        try:
            results = run_topic_pipeline(topic)
            all_curated.extend(results)
            logger.info(f"  → {len(results)} opportunities found")
        except Exception as e:
            logger.error(f"  Error on topic '{topic[:60]}...': {e}", exc_info=True)

    logger.info(f"Pipeline complete. Total curated: {len(all_curated)}")

    # Step 3: Save to local JSON files (root + public/)
    if all_curated:
        update_opportunities_database(all_curated)

    # Step 4: Upsert all to Supabase
    if all_curated:
        records = [o.model_dump() for o in all_curated]
        upserted = upsert_opportunities_to_supabase(records)
        logger.info(f"Supabase: {upserted} records synced.")

    logger.info("=== Pipeline finished successfully ===")
