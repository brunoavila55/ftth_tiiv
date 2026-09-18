"""HEALTHCHECK do worker: falha (exit 1) se o heartbeat não existir ou estiver velho."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from app.core.config import get_settings


def main() -> int:
    settings = get_settings()
    heartbeat = Path(settings.WORKER_HEARTBEAT_FILE)
    try:
        age = time.time() - heartbeat.stat().st_mtime
    except OSError:
        print(f"heartbeat ausente: {heartbeat}", file=sys.stderr)
        return 1
    if age > settings.WORKER_HEARTBEAT_MAX_AGE_SECONDS:
        print(f"heartbeat velho: {age:.0f}s", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
