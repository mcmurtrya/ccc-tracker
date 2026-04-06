# Implementation tickets (PDF / LLM / queues)

Status: **open** | **in progress** | **done** (update as you ship).

---

## Phase A — Document capture (PDF bytes in Postgres metadata)

| ID | Ticket | Acceptance criteria | Status |
|----|--------|----------------------|--------|
| **DOC-001** | Extend `document_artifacts` for ELMS metadata | Migration adds `source_url`, `file_name`, `attachment_type`, `bytes_size`, `raw_json`; ORM updated | **done** |
| **DOC-002** | Extract `files[]` from stored meeting `raw_json` (`elms.files` / list rows) | Pure function + unit tests | **done** |
| **DOC-003** | `sync-documents` CLI: download by URL, SHA-256, dedupe per `(meeting_id, source_url)` | CLI runs; skips duplicates; caps meetings + file size | **done** |
| **DOC-004** | Optional: persist raw bytes to disk/S3 + set `uri` to storage key | Config `CITYCOUNCIL_DOCUMENTS_LOCAL_DIR`; `local_path` on artifact | **done** |
| **DOC-005** | Admin or metrics: count artifacts by `parse_status` | `GET /admin/documents/stats` | **done** |

## Phase B — Text extraction (OCR / pdfminer)

| ID | Ticket | Acceptance criteria | Status |
|----|--------|----------------------|--------|
| **TXT-101** | Worker: PyMuPDF/pdfminer → full text per artifact | Updates `parse_status` ok/failed; stores text (new table or column) | **done** |
| **TXT-102** | Chunk table: `document_chunks` (artifact_id, ord, text, page, meeting_id FK) | Alembic + ORM | **done** |
| **TXT-103** | OCR fallback for scanned pages (Tesseract or one cloud OCR) | PyMuPDF render + `pytesseract` when extract empty (`extract_ocr_enabled`); still `needs_review` if OCR yields nothing | **done** |
| **TXT-104** | Low-confidence review queue | `needs_review` + stats; OCR/queue next | **in progress** |

## Phase C — LLM & embeddings

| ID | Ticket | Acceptance criteria | Status |
|----|--------|----------------------|--------|
| **LLM-201** | Job table or reuse `ingest_state` for LLM jobs | `llm_jobs` table + ORM | **done** |
| **LLM-202** | Prompt-versioned JSON extract (tags/summary) via chosen API | `ordinances.llm_summary` + `llm_tags`; `POST /admin/ordinances/{id}/summarize` (HF chat) | **done** |
| **LLM-203** | pgvector extension + embedding column on chunks | `embedding` REAL[] + `embedding_vector vector(384)` + **`GET /search/chunks`** RAG; **`citycouncil embed-run`** (HF). HNSW index optional (add manually at scale) | **done** |
| **LLM-204** | Rate limits + cost fields per job | Config + logging | open |

## Phase D — Plumbing

| ID | Ticket | Acceptance criteria | Status |
|----|--------|----------------------|--------|
| **PLM-301** | Queue abstraction (Redis Streams / SQS / DB queue) | One consumer loop template | open |
| **PLM-302** | Observability: structured logs + job timing | Shared middleware or structlog | open |

---

## Order to implement (recommended)

1. DOC-001 → DOC-003 (vertical slice: metadata + download + hash)  
2. TXT-101 → TXT-102 (searchable text)  
3. LLM-203 → LLM-202 → LLM-201 (vectors then structured LLM then job orchestration)  
4. PLM-301 when async workers need to scale off the API process  

See also `plan.txt` (roadmap narrative).
