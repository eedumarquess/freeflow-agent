from __future__ import annotations

from datetime import datetime
import secrets


def generate_run_id(now: datetime | None = None) -> str:
    timestamp = (now or datetime.utcnow()).strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(2)
    return f"{timestamp}_{suffix}"
