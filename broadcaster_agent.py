"""
Broadcaster Agent
Curates and publishes student portal announcements and urgent deadlines.
Writes to both root broadcasts.json and public/broadcasts.json.
"""
import os
import json
import logging
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BroadcasterAgent")

_ROOT = Path(__file__).resolve().parent
_PUBLIC = _ROOT / "public"

ROOT_FILE = _ROOT / "broadcasts.json"
PUBLIC_FILE = _PUBLIC / "broadcasts.json"


def load_broadcasts() -> List[Dict[str, Any]]:
    for path in [ROOT_FILE, PUBLIC_FILE]:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
            except Exception:
                continue
    return []


def save_broadcasts(broadcasts: List[Dict[str, Any]]) -> None:
    _PUBLIC.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(broadcasts, indent=2, ensure_ascii=False)
    
    ROOT_FILE.write_text(payload, encoding="utf-8")
    PUBLIC_FILE.write_text(payload, encoding="utf-8")
    logger.info(f"Broadcasts synced to both {ROOT_FILE} and {PUBLIC_FILE} ({len(broadcasts)} items).")


def add_broadcast(title: str, message: str, category: str = "Announcement") -> Dict[str, Any]:
    broadcasts = load_broadcasts()
    new_item = {
        "id": f"broadcast-{len(broadcasts) + 1:03d}",
        "title": title,
        "message": message,
        "category": category,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "is_active": True
    }
    broadcasts.insert(0, new_item)
    save_broadcasts(broadcasts)
    return new_item


if __name__ == "__main__":
    items = load_broadcasts()
    if not items:
        add_broadcast(
            title="Welcome to Opportunity Scout Live!",
            message="AI-curated student opportunities updated daily at 04:00 UTC. Bookmark opportunities and match your profile directly with Agent 4!"
        )
    else:
        save_broadcasts(items)
