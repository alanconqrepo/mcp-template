import re


def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to max_length, appending suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def word_count(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def sanitize(text: str) -> str:
    """Strip leading/trailing whitespace and collapse multiple newlines."""
    return re.sub(r"\n{3,}", "\n\n", text.strip())
