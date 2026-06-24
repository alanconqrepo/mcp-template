from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_translator = None


def get_deepl_translator():
    """Return a cached deepl.Translator. Raises RuntimeError if DEEPL_API_KEY is not set."""
    global _translator
    if _translator is not None:
        return _translator

    import deepl

    from mcp_server.config import get_settings

    settings = get_settings()
    if not settings.DEEPL_API_KEY:
        raise RuntimeError(
            "DEEPL_API_KEY is not configured. Set the DEEPL_API_KEY environment variable."
        )

    _translator = deepl.Translator(settings.DEEPL_API_KEY)
    logger.info("DeepL Translator initialized (free=%s)", settings.DEEPL_API_KEY.endswith(":fx"))
    return _translator
