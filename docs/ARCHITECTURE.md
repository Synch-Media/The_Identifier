# Current MVP architecture

```text
Browser: React / TypeScript (Vite, 127.0.0.1:5173)
  /api proxy -> FastAPI (127.0.0.1:8000, one worker)
    -> Langflow 1.12.2 (127.0.0.1:7860)
       -> LM Studio (localhost:1234/v1), Gemma 4 26B A4B QAT Q4_0
       -> existing Web Search and URL tools -> public internet
```

The browser never connects directly to Langflow or LM Studio. Recognition uses
the existing frozen flow; no new provider or model routing is introduced.

## Components

| File | Responsibility |
| --- | --- |
| `backend/main.py` | Local API, image validation/normalization, JSON storage, background tasks and user decisions |
| `backend/models.py` | Pydantic input, identity and recognition schemas |
| `backend/parser.py` | Strict labeled final-output parser |
| `backend/naming.py` | Existing catalog-identifier guard for active identities; preserves raw attempt evidence |
| `backend/langflow.py` | Desktop cookies, temporary keys, uploads, recognition call, secret redaction and key cleanup |
| `scripts/integration_run.py` | Runtime constants and final-envelope extractor reused by backend; also historical live CLI |
| `scripts/integration_probe.py` | No-redirect helper reused by runtime; historical read-only probe CLI |
| `frontend/src/` | Evidence UI, results, correction, polling, session reload recovery and technical details |
| `reference/langflow/` | Unchanged validated flow export and checksum |

Keep `scripts/` in the first commit: it is a runtime dependency, not merely an
optional diagnostics folder. The backend never executes those scripts' CLI
entrypoints when importing their constants/helpers.

## Request and evidence lifecycle

The application creates a UUID item session and a separate Langflow session ID.
Images are validated, EXIF-oriented, flattened onto white and stored as RGB JPEG
(quality 95, no chroma subsampling), with the original bytes retained separately.
The user explicitly clicks Identify. New image files are uploaded to Langflow;
manual evidence and earlier rejected identities are packaged into input text.

The request uses `input_request`, selected Chat Output, the item-specific session,
and Chat Input `files` tweaks. Same-item follow-ups send only new images. The
validated Langflow history supplies prior evidence; Start New Item uses new IDs.
The exact transport envelope and historical continuity verification are in
[INTEGRATION_CONTRACT.md](INTEGRATION_CONTRACT.md).

The extractor selects exactly one `ChatOutput-KxTA8` result and validates session,
sender, completion and nonempty text. The parser converts labeled text into
structured fields and fails closed on invalid or ambiguous output. Original raw
text and parsed attempts are retained; the naming guard separately prevents known
catalog identifiers being treated as a marketed Product Name or retained in Name.
It can downgrade an unsupported active Resolved identity to Needs Evidence or
Unresolved according to the existing evidence history. This does not change the
Agent Instructions or stored original recognition output.

## Three independent state concepts

| Concept | Values / behavior |
| --- | --- |
| Recognition | `Resolved`, `Needs Evidence`, `Unresolved` |
| Execution | `idle`, `processing`, `completed`, `failed` |
| User decision | `confirmed`, `corrected`, `rejected`, `accepted general identity` |

Resolved requires supported Name, Brand, Product Name and Item Type; Style Accent
is optional. Needs Evidence presents a specific request. Unresolved preserves
known evidence and why an exact identity remains unsupported. Parser checks do
not independently verify web sources or prove model accuracy.

Confirmation, correction, rejection and general acceptance are local decisions;
they do not invoke the model or overwrite its recorded result. General acceptance
requires Unresolved, a supported item type and no exact product name. A rejection
is included in later evidence prompts and a repeated matching result stays
visibly rejected. Execution failures never manufacture a recognition outcome.

## Storage and boundaries

`data/sessions/<UUID>/session.json` stores evidence metadata, attempts, results
and decisions. Original images (`.original`) and normalized JPEGs live alongside.
JSON replacement is atomic and process-local locks serialize access. Browser
`sessionStorage` stores only the current application session ID. Langflow has its
own external database, uploaded files and conversation histories.

One in-process engine lock permits one recognition job across all app sessions.
There is no durable queue or cancellation. The run HTTP timeout is 420 seconds;
other local client calls default to 30 seconds. Restart recovery marks interrupted
processing as failed. Langflow may still finish after a client timeout; start a
new item only after checking that the old call has stopped.

The services bind locally. FastAPI restricts host/origin and requires
`X-Identifier-Local: 1` for mutations. These checks do not constitute multi-user
authentication. Desktop cookies and one-hour per-attempt keys remain in memory;
known credential values are redacted before final-text storage/display. Raw
upstream error bodies and intermediate reasoning/tool traces are not exposed by
the app UI. A forced shutdown may leave a temporary key until expiry.

There is no encryption, account system, retention cleanup, session-history UI,
database server, or LAN/production deployment. Public web research is part of the
flow; local inference does not imply that research queries remain on the machine.
