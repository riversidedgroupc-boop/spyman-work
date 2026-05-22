"""Small helpers for stable database identifiers."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4


def generate_id(prefix: str) -> str:
    """Return a human-readable ID that is also safe for rapid batch inserts."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{prefix}_{timestamp}_{uuid4().hex[:8]}"
