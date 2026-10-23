"""
Opportunity Pipeline Runner
Discovers, verifies, and syncs curated opportunities to both root opportunities.json and public/opportunities.json.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pipeline import run_daily_pipeline, update_opportunities_database, Opportunity

if __name__ == "__main__":
    daily_topics = [
        "Undergraduate Summer Research Fellowships in Computer Science and AI 2026",
        "Global Student Open Source Grants and Tech Fellowships 2026",
        "STEM Undergraduate Scholarships with upcoming deadlines"
    ]
    run_daily_pipeline(daily_topics)
