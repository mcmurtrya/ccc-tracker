from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from citycouncil.constants import PGVECTOR_EMBEDDING_DIMENSION


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CITYCOUNCIL_", env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://citycouncil:citycouncil@localhost:5433/citycouncil",
        description="Async SQLAlchemy URL (postgresql+asyncpg://...)",
    )

    elms_api_base: str = Field(
        default="https://api.chicityclerkelms.chicago.gov",
        description="Base URL for the public eLMS API (no trailing slash)",
    )

    elms_poll_top: int = Field(
        default=100,
        ge=1,
        le=5000,
        description="Page size for GET /meeting ($top)",
    )
    elms_poll_skip: int = Field(
        default=0,
        ge=0,
        description="Offset for GET /meeting ($skip), for paging through results",
    )

    elms_enrich_detail: bool = Field(
        default=False,
        description="If true (and not using fixture), fetch agenda/matters/votes per meeting after list poll",
    )
    elms_enrich_max_meetings: int = Field(
        default=3,
        ge=1,
        le=500,
        description="Max meetings from the list poll to enrich per run (avoids huge HTTP fan-out)",
    )
    elms_enrich_max_agenda_items: int = Field(
        default=50,
        ge=1,
        le=5000,
        description="Max agenda lines per meeting to load (matters + roll calls)",
    )
    elms_enrich_concurrency: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Parallel ELMS detail requests (matters, votes, persons)",
    )

    poller_use_fixture: bool = Field(
        default=False,
        description="If true, load JSON from poller_fixture_path instead of HTTP",
    )
    poller_fixture_path: str = Field(
        default="fixtures/sample_elms_response.json",
    )

    poller_timeout_seconds: float = Field(
        default=60.0,
        description="HTTP timeout for ELMS poller requests (seconds)",
    )
    poller_max_retries: int = Field(
        default=3,
        ge=0,
        le=20,
        description="Retries for transient ELMS poller failures",
    )

    documents_sync_max_meetings: int = Field(
        default=50,
        ge=1,
        le=2000,
        description="Max meetings (by recency) to scan for ELMS files per sync-documents run",
    )
    documents_max_bytes: int = Field(
        default=52_428_800,
        ge=1024,
        description="Max download size per file (default 50 MiB)",
    )
    documents_http_timeout: float = Field(
        default=120.0,
        ge=5.0,
        description="HTTP client timeout for document downloads (seconds)",
    )
    documents_sync_pdf_only: bool = Field(
        default=True,
        description="If true, only download files whose URL/name looks like a PDF",
    )
    documents_local_dir: str | None = Field(
        default=None,
        description="If set, write each downloaded PDF to {dir}/{sha256}.pdf and set local_path (DOC-004)",
    )

    extract_max_documents: int = Field(
        default=25,
        ge=1,
        le=5000,
        description="Max document_artifacts rows to extract per extract-documents run (pending only)",
    )
    extract_max_chars_per_chunk: int = Field(
        default=4000,
        ge=256,
        le=100_000,
        description="Max characters per document_chunks.body slice (TXT-101)",
    )
    embedding_dimensions: int = Field(
        default=PGVECTOR_EMBEDDING_DIMENSION,
        ge=8,
        le=8192,
        description=(
            "Must match the Hugging Face model output dimension and "
            f"``constants.PGVECTOR_EMBEDDING_DIMENSION`` ({PGVECTOR_EMBEDDING_DIMENSION} for all-MiniLM-L6-v2)"
        ),
    )
    huggingface_token: SecretStr | None = Field(
        default=None,
        description="Hugging Face API token with Inference Providers access (CITYCOUNCIL_HUGGINGFACE_TOKEN)",
    )
    huggingface_embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Hub model id for feature-extraction / embeddings",
    )
    huggingface_inference_base_url: str = Field(
        default="https://router.huggingface.co/hf-inference",
        description="Base URL for HF Inference router (override for proxies or self-hosted TEI)",
    )
    huggingface_normalize_embeddings: bool = Field(
        default=True,
        description="Pass normalize=true to HF feature-extraction when supported",
    )
    huggingface_prompt_name: str | None = Field(
        default=None,
        description="Optional sentence-transformers prompt_name for HF feature-extraction (chunk indexing)",
    )
    huggingface_search_prompt_name: str | None = Field(
        default=None,
        description="Optional prompt_name for query embedding in /search/chunks (e.g. query vs document)",
    )
    huggingface_chat_router_url: str = Field(
        default="https://router.huggingface.co/v1/chat/completions",
        description="OpenAI-compatible HF Inference chat URL",
    )
    huggingface_chat_model: str = Field(
        default="HuggingFaceTB/SmolLM2-360M-Instruct",
        description="Chat model id for ordinance summarize (HF router)",
    )
    huggingface_chat_timeout: float = Field(
        default=120.0,
        ge=10.0,
        le=600.0,
        description="HTTP timeout for HF chat (ordinance summarize)",
    )
    huggingface_chat_max_tokens: int = Field(
        default=512,
        ge=64,
        le=4096,
        description="max_tokens for HF chat completions (ordinance summarize)",
    )
    llm_summarize_prompt_version: str = Field(
        default="1",
        min_length=1,
        max_length=64,
        description="Bumped when ordinance summarize system prompt changes (stored on ordinances row)",
    )
    search_default_limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Default result count for GET /search/chunks (clamped to search_max_limit)",
    )
    search_max_limit: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Upper bound when clamping /search/chunks limit",
    )
    search_chunk_preview_chars: int = Field(
        default=400,
        ge=80,
        le=12_000,
        description="Max characters for body_preview on /search/chunks (full body still returned as body)",
    )
    search_trust_disclaimer: str = Field(
        default=(
            "Results are ranked by semantic similarity to your query; they are not legal advice. "
            "Verify important facts against the linked source documents."
        ),
        description="Shown on GET /search/chunks alongside citations",
    )
    activity_default_limit: int = Field(default=50, ge=1, le=500)
    activity_max_limit: int = Field(default=200, ge=1, le=1000)
    activity_default_since_days: int = Field(
        default=7,
        ge=1,
        le=3650,
        description="When GET /activity has no since=, use UTC now minus this many days",
    )
    activity_q_max_chars: int = Field(
        default=500,
        ge=16,
        le=10_000,
        description="Max characters for GET /activity?q= (longer values are truncated)",
    )
    public_base_url: str = Field(
        default="http://127.0.0.1:8000",
        description="Canonical site URL for RSS item links (no trailing slash required)",
    )
    extract_ocr_enabled: bool = Field(
        default=True,
        description="If true, run Tesseract OCR when PyMuPDF extracts no text (requires tesseract binary)",
    )
    extract_ocr_dpi: int = Field(default=150, ge=72, le=400, description="Render DPI for OCR rasterization")
    embed_enqueue_limit: int = Field(
        default=100,
        ge=1,
        le=50_000,
        description="Max new llm_jobs rows to create per embed-run enqueue phase",
    )
    embed_process_limit: int = Field(
        default=50,
        ge=1,
        le=10_000,
        description="Max pending embed_chunk jobs to process per embed-run",
    )
    embed_batch_size: int = Field(
        default=16,
        ge=1,
        le=128,
        description="Chunks per Hugging Face feature-extraction call (keep modest for serverless limits)",
    )
    embed_input_max_chars: int = Field(
        default=12_000,
        ge=1000,
        le=100_000,
        description="Truncate chunk body to this many characters before embedding",
    )

    admin_api_key: SecretStr | None = Field(
        default=None,
        description="If set, required for /admin/* (X-Admin-Key or Authorization: Bearer). If unset, admin routes return 503.",
    )

    @field_validator("huggingface_token", "admin_api_key", mode="before")
    @classmethod
    def _empty_secret_env_to_none(cls, v: object) -> object:
        """Treat empty env as unset so tests can override a non-empty .env entry."""
        if v == "" or v is None:
            return None
        return v

    @model_validator(mode="after")
    def _search_and_activity_limits_ordered(self) -> Self:
        if self.search_max_limit < self.search_default_limit:
            raise ValueError("search_max_limit must be >= search_default_limit")
        if self.activity_max_limit < self.activity_default_limit:
            raise ValueError("activity_max_limit must be >= activity_default_limit")
        return self

    def huggingface_token_value(self) -> str | None:
        """Plain HF token for Authorization headers, or None if unset/empty."""
        tok = self.huggingface_token
        if tok is None:
            return None
        if isinstance(tok, SecretStr):
            s = tok.get_secret_value()
        else:
            s = str(tok)
        return s if s else None

    def admin_api_key_value(self) -> str | None:
        """Plain admin API key for comparison, or None if unset/empty."""
        key = self.admin_api_key
        if key is None:
            return None
        if isinstance(key, SecretStr):
            s = key.get_secret_value()
        else:
            s = str(key)
        return s if s else None


def database_url_sync(url: str) -> str:
    """Alembic / sync tools: asyncpg -> psycopg2."""
    if url.startswith("postgresql+asyncpg"):
        return url.replace("postgresql+asyncpg", "postgresql+psycopg2", 1)
    return url


def get_settings() -> Settings:
    """Load settings from environment and optional ``.env``.

    Returns a new ``Settings`` instance each call (no process-wide cache): caching breaks
    tests and local overrides when combined with FastAPI lifespan and ``TestClient`` env
    monkeypatching. Cost is one pydantic parse per dependency resolution.
    """
    return Settings()
