import time
import logfire
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.config import settings

BATCH_SIZE = 50
_GEMINI_DIM = 3072
_FALLBACK_DIM = 768  # all-mpnet-base-v2

_active_model = None
_model_type: str | None = None  # "gemini" or "fallback"


# ── Model initialisation ───────────────────────────────────────────────────────

def _probe_gemini():
    """Try one embed call to verify Gemini is reachable. Returns model or None."""
    if not settings.GEMINI_API_KEY:
        return None
    model = GoogleGenerativeAIEmbeddings(
        model=settings.GEMINI_EMBEDDING_MODEL or "models/gemini-embedding-2-preview",
        google_api_key=settings.GEMINI_API_KEY,
    )
    for attempt in range(4):
        try:
            model.embed_query("probe")
            logfire.info("Gemini embeddings ready (gemini-embedding-2-preview, 3072-dim).")
            return model
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ("429", "rate", "quota", "resource_exhausted")) and attempt < 3:
                time.sleep(5)
            else:
                logfire.warning(f"Gemini probe failed: {e}. Will use sentence-transformers fallback.")
                return None
    return None


def _load_fallback():
    from sentence_transformers import SentenceTransformer
    logfire.info("Loading sentence-transformers fallback (all-mpnet-base-v2, 768-dim).")
    return SentenceTransformer("all-mpnet-base-v2")


def _init():
    """Initialise embedding model once per process. Called lazily on first use."""
    global _active_model, _model_type
    if _active_model is not None:
        return

    gemini = _probe_gemini()
    if gemini:
        _active_model = gemini
        _model_type = "gemini"
    else:
        _active_model = _load_fallback()
        _model_type = "fallback"


# ── Public helpers ─────────────────────────────────────────────────────────────

def get_embedding_dim() -> int:
    """Return the vector dimension for the active model. Call after _init()."""
    _init()
    return _GEMINI_DIM if _model_type == "gemini" else _FALLBACK_DIM


# ── Batch embedding with retry ─────────────────────────────────────────────────

def _embed_batch(batch: list[str]) -> list[list[float]]:
    if _model_type == "gemini":
        # Adaptive backoff for Gemini free tier (15 requests/min):
        # 10s -> 20s -> 30s -> 60s
        for attempt in range(5):
            try:
                time.sleep(1.0)  # Gentle pacing between requests
                return _active_model.embed_documents(batch)
            except Exception as e:
                err = str(e).lower()
                is_rate_limit = any(x in err for x in ("429", "rate", "quota", "resource_exhausted"))
                if is_rate_limit and attempt < 4:
                    wait = 15 * (attempt + 1)
                    print(f" [Rate-Limit] Waiting {wait}s for Gemini quota window...", flush=True)
                    logfire.warning(
                        f"Gemini rate limit hit — retrying in {wait}s "
                        f"(attempt {attempt + 1}/5)."
                    )
                    time.sleep(wait)
                else:
                    logfire.error(f"Gemini embedding failed: {e}")
                    raise
        raise RuntimeError("Gemini rate limit persisted after attempts.")
    else:
        return _active_model.encode(batch, show_progress_bar=False).tolist()


# ── Public API (same signatures as before) ─────────────────────────────────────

def embed_query(query: str) -> list[float]:
    _init()
    if _model_type == "gemini":
        return _active_model.embed_query(query)
    return _active_model.encode([query])[0].tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    _init()
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        with logfire.span("Embed batch", model=_model_type, start=i, size=len(batch)):
            all_embeddings.extend(_embed_batch(batch))
    return all_embeddings
