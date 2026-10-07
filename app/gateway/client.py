import logfire
from portkey_ai import Portkey, createHeaders, PORTKEY_GATEWAY_URL
from langchain_openai import ChatOpenAI

from app.config import settings


# Check if a valid Portkey config and key are present
USE_PORTKEY = bool(
    settings.PORTKEY_API_KEY
    and settings.PORTKEY_CONFIG
    and not settings.PORTKEY_API_KEY.startswith("pk-dummy")
)

if USE_PORTKEY:
    from portkey_ai import Portkey, createHeaders, PORTKEY_GATEWAY_URL
    portkey_client = Portkey(
        api_key=settings.PORTKEY_API_KEY,
        config=settings.PORTKEY_CONFIG
    )
else:
    from openai import OpenAI
    portkey_client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=settings.GROQ_API_KEY or "dummy"
    )


def get_langchain_llm(feature: str = "rag") -> ChatOpenAI:
    """
    Returns a Portkey-backed or direct Groq ChatOpenAI instance for LangChain nodes.
    """
    if USE_PORTKEY:
        from portkey_ai import createHeaders, PORTKEY_GATEWAY_URL
        return ChatOpenAI(
            api_key=settings.PORTKEY_API_KEY,
            base_url=PORTKEY_GATEWAY_URL,
            model=settings.GROQ_MODEL,
            temperature=0,
            default_headers=createHeaders(
                config=settings.PORTKEY_CONFIG,
                metadata={
                    "feature": feature,
                    "_user": "nexus-rag-system",
                    "environment": "production"
                }
            )
        )
    else:
        return ChatOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            model=settings.GROQ_MODEL,
            temperature=0
        )


def extract_cache_status(response) -> str:
    """
    Pull x-portkey-cache-status from the Portkey native client response headers.
    Tries multiple attribute paths defensively — returns 'MISS' if not found.
    """
    if not USE_PORTKEY:
        return "MISS"
    for attr in ("_raw_response", "_response", "_http_response"):
        raw = getattr(response, attr, None)
        if raw is not None:
            status = getattr(raw, "headers", {}).get("x-portkey-cache-status", "")
            if status:
                return status.upper()
    return "MISS"