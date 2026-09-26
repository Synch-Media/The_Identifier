# Milestone 2 — First Usable Identifier App

Built and tested on 2026-09-25. Ready for hands-on review; no later milestone,
commit, push, deployment, or validated-flow change is included.

## What was built

- React / TypeScript / Vite browser interface with Identifier branding, drag/drop
  and standard file selection, previews and pending-photo removal.
- FastAPI / Pydantic backend with JPG/PNG/WebP normalization, local file sessions,
  the verified Langflow execution contract, and backend-only temporary authentication.
- Optional known-information fields; real identification and follow-up evidence.
- Resolved, Needs Evidence, and Unresolved displays with evidence, sources,
  candidates, missing information, and next steps. Earlier evidence remains
  available when a final Unresolved response omits it.
- Confirmation, manual correction, rejection, and explicit general acceptance.
  Corrections update Name as fields change and require no model call. Rejected
  identities remain flagged if the model proposes the same identity again.
- Separate execution/outcome/decision state, progress messaging, restart recovery,
  operational errors, and a collapsed technical panel containing final output only.
- Startup scripts, dependency locks, offline tests, browser tests, and this review record.

## Actual live browser results

These runs used the application UI, real image uploads, existing Langflow, and
`google/gemma-4-26b-a4b-qat`. No response substitution was used in these runs.
Times include backend authentication/upload/cleanup and are individual observations.

| Case | Input/action | Result | Seconds |
| --- | --- | --- | ---: |
| A, attempt 1 | Retained jeans overview JPG | Needs Evidence | 57.48 |
| A, attempt 2 | Tag JPG, same item | Resolved: Levi's 511 Jeans | 84.73 |
| B, attempt 1 | White shoes PNG, new item | Needs Evidence | 32.44 |
| B, attempt 2 | Manual brand Goodfellow & Co. | Resolved, with questionable Product Name | 91.42 |
| C, attempt 1 | Shoes WebP, separate item | Needs Evidence | 33.33 |
| C, attempt 2 | I Don't Have More Information | Unresolved | 49.03 |

Also exercised in the actual browser:

- Manual edit of the jeans to `Levi's 511 Slim Jeans`, with Product Name `511 Slim`;
  the attempt count stayed at 2, confirming no extra recognition call.
- Browser reload retained the correction and item session.
- Start New Item created an empty item and a different Langflow session.
- WebP drag-and-drop, removing that pending photo, and selecting it again.
- Accept General Identity saved `Shoes` with no brand/product name in case C.
- Collapsed/expanded technical details and screenshots of initial/results views.

Read-only verification inspected actual Langflow model-input traces. Every model
call contained exactly that session's accumulated image hashes and user turns.
The tag follow-up contained both jeans images; the text-only shoe follow-up kept
the shoe image. Different-product image sets were disjoint. Each session history
had exactly four messages for its two attempts. Local edits were not model turns.
The flow graph matched the before-test snapshot, the frozen export checksum was
unchanged, and the final key-ID set matched the original set: no temporary keys remained.

## Accuracy observations retained for review

The jeans tag result claimed an exact Product Name without a web-search call,
repeating the Milestone 1 instruction-compliance limitation.

The shoe brand follow-up performed a search but promoted `White Minimalist Low Top`
to Product Name from a Poshmark listing. The existing specification identifies the
test pair's known name as `Scout`. Treat this run as a successful integration and
correction-path test, **not a validated identification**. The application preserves
what the unchanged Agent returned and makes it editable; it does not silently
rewrite the Agent's recognition decisions or claim independent source verification.

## Automated checks

- 25 backend checks: retained-output parsing, invalid/duplicate/unknown fields,
  three image formats, corrupt files, pending/removal rules, session isolation,
  same-item photo and manual follow-ups, no-more-information, general acceptance,
  corrections, repeated rejection, operational failures, busy handling, interrupted
  job recovery, local-origin checks, credential redaction, and envelope mismatch.
- Three browser UI regression scenarios with an intercepted application API:
  evidence/manual/exhausted/general flow; correction/rejection with no extra call;
  operational failure distinct from Unresolved. These are explicitly offline UI
  tests, separate from the six live executions above.
- TypeScript checking and Vite production build.
- Screenshots visually reviewed for initial, Resolved, and Unresolved layouts.
- A dependency deprecation warning appears in backend tests: Starlette recommends
  `httpx2` for a future test-client migration. Tests pass using the pinned versions.

## Evidence locations

- `data/milestone2/2026-09-25T19-18-36-345Z/`: browser screenshots, session snapshots,
  and report for cases A and B.
- `data/milestone2/exhausted/`: WebP/exhausted-evidence/general-acceptance screenshots
  and report for case C.
- `data/milestone2/verification.json`: actual model-input, history, flow, and key checks.
- `data/milestone2/flow-before.json`: pre-test local flow snapshot, retained locally only.
- `data/sessions/`: actual application session records and retained photos.

The final UI additionally exposes earlier evidence for Unresolved and automatically
updates a corrected Name; these were checked by the browser regression tests after
the six live runs. The backend's repeated-rejection safeguard was likewise checked
offline, then loaded in the restarted application. No extra inference was needed
for those local presentation/decision changes.

## What to try yourself

1. Start services using README.md, then open `http://127.0.0.1:5173`.
2. Upload a photo from your own files. Try both picker and drag/drop, then remove
   a pending preview. Expand Add What I Know and identify without typing a prompt.
3. On Needs Evidence, add a requested detail photo or manual identifier. Confirm
   the session IDs remain the same and previous photos remain visible.
4. Use Edit on a Resolved result. Change Product Name, review the updated Name,
   and save. The attempt number should not change. Reload to verify persistence.
5. Try Not This Item. The rejected proposal is retained for debugging and cannot
   silently be presented as accepted on a later matching result.
6. Use I Don't Have More Information after an evidence request. On Unresolved,
   inspect what was retained and accept a general identity only if appropriate.
7. Start New Item. Confirm empty evidence, no previous result, and new IDs.

## Limitations and scope

One local user and one recognition job at a time; eight photos and twelve attempts
per item. No cancellation, session browser, removal of already-submitted evidence,
automatic retries, or durable job queue. Failed/ambiguous executions require a new
item. The raw labeled-output format can still vary and be rejected by the strict
parser. Runtime, source availability, and recognition quality depend on the frozen
workflow. The six calls do not establish broader model accuracy.

Local Desktop auto-login plus a short-lived per-attempt key is temporary development
authentication. Keys/cookies stay server-side; a forcibly terminated process may
leave its key until its one-hour expiry. Existing search uses the public web.

No pricing, listings, inventory, marketplace integration, accounts, payments,
analytics, mobile/LAN, phone camera, HEIC, another model, or instruction changes.

## Files created or changed

Created:

- `backend/__init__.py`, `backend/main.py`, `backend/models.py`,
  `backend/parser.py`, `backend/langflow.py`
- `frontend/package.json`, `frontend/package-lock.json`, `frontend/index.html`,
  `frontend/tsconfig.json`, `frontend/vite.config.ts`
- `frontend/src/main.tsx`, `frontend/src/api.ts`, `frontend/src/types.ts`,
  `frontend/src/style.css`
- `frontend/tests/ui.test.mjs`, `frontend/tests/live-browser.mjs`,
  `frontend/tests/live-exhausted.mjs`
- `tests/test_application.py`
- `scripts/start-backend.ps1`, `scripts/start-frontend.ps1`, `scripts/milestone2_verify.py`
- `requirements.txt`, `requirements.lock.txt`, `docs/MILESTONE_2_REVIEW.md`

Changed:

- `README.md` (previously empty): exact setup/startup, behavior, limits, and tests.
- `.gitignore`: local environments and generated frontend files.
- `scripts/integration_run.py`: package-compatible import with direct-script fallback;
  its validated final extractor is reused by the backend.

Generated locally: `.venv`, `frontend/node_modules`, `frontend/dist`, caches,
`data/sessions`, and `data/milestone2`. They are excluded from source control.
The original specifications, Milestone 1 contract/evidence, frozen export, live
flow, Agent Instructions, Gemma configuration, and search configuration remain unchanged.
