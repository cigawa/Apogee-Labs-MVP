"""
Human feedback capture (the RLHF data loop).

Stores each generation + the engineer's edits and feedback as a JSONL record.
This is the seed of the proprietary dataset described in the business plan:
every reviewed generation becomes a training example (preference pair: original
AI output vs. engineer-corrected output, plus a usefulness rating and rationale).

MVP storage: local JSONL file. Production: swap for a database (SQL/cloud) by
replacing save_feedback(); the record schema stays the same.
"""

import json
import os
import time
import uuid
from typing import Optional

FEEDBACK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "feedback_data")
FEEDBACK_FILE = os.path.join(FEEDBACK_DIR, "feedback_log.jsonl")


def save_feedback(record: dict) -> dict:
    """Append a feedback record. Returns {"ok": bool, "id": str, "error": str?}."""
    try:
        os.makedirs(FEEDBACK_DIR, exist_ok=True)
        record = dict(record)
        record.setdefault("id", str(uuid.uuid4()))
        record.setdefault("timestamp", time.time())
        record.setdefault("timestamp_iso",
                          time.strftime("%Y-%m-%dT%H:%M:%S",
                                        time.localtime(record["timestamp"])))
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {"ok": True, "id": record["id"], "error": None}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "id": None, "error": str(e)}


def load_feedback() -> list[dict]:
    """Load all feedback records (for a simple in-app review/metrics view)."""
    if not os.path.exists(FEEDBACK_FILE):
        return []
    out = []
    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def feedback_stats() -> dict:
    """Quick aggregate metrics for the demo / grant package."""
    records = load_feedback()
    if not records:
        return {"count": 0, "avg_usefulness": None, "edited_fraction": None}
    ratings = [r.get("usefulness") for r in records
               if isinstance(r.get("usefulness"), (int, float))]
    edited = [r for r in records if r.get("was_edited")]
    return {
        "count": len(records),
        "avg_usefulness": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "edited_fraction": round(len(edited) / len(records), 2),
    }
