import time
from datetime import UTC, datetime


def iso_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def elapsed_ms(start: float) -> int:
    """Return elapsed milliseconds since start (from time.perf_counter())."""
    return int((time.perf_counter() - start) * 1000)
