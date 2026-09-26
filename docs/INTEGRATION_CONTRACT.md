# Identifier — Milestone 1 Integration Contract

Date: 2026-09-25

**Status: Historical Milestone 1 integration contract; retained for the working MVP.**

## Current application checkpoint

For downstream applications, use the versioned
[downstream export contract](DOWNSTREAM_EXPORT.md):
`GET /api/sessions/{session_id}/export`. Future pricing and market systems should
consume this export rather than call Langflow directly. The historical transport
details below describe Identifier's internal recognition integration, not the
downstream interface.

FastAPI and the React/TypeScript UI now implement the application layer described
in [ARCHITECTURE.md](ARCHITECTURE.md). The transport recipe below remains in use:
Desktop cookies plus a temporary per-attempt key, normalized JPEG upload,
`input_request`, selected final output and same-item history continuity. Runtime
constants are still in `scripts/integration_run.py`; configuration and fresh-import
limitations are in [SETUP_WINDOWS.md](SETUP_WINDOWS.md).

The reference stack is Gemma 4 26B A4B QAT **Q4_0**, LM Studio and Langflow 1.12.2.
The current app adds strict labeled-output parsing, three recognition states,
separate execution/user-decision state and the existing naming guard. Statements
below about code not yet built and scenarios not exercised describe Milestone 1
only. MILESTONE_2_REVIEW.md records later live UI checks. None of those historical
runs was repeated for documentation preparation.

All `data/` evidence paths below are private local records excluded from Git. A
fresh checkout deliberately does not contain their photos, traces or session
captures. Ordinary backend tests now use synthetic text fixtures; historical
live verifiers still depend on those private records. Flow/session UUIDs here
are historical identifiers, not authentication credentials.


This contract records behavior observed against the local running instance in
four recognition calls. It does not establish recognition accuracy beyond these
examples or guarantee behavior under concurrency, restart, or long histories.

## 1. Running service and access

| Item | Verified value / behavior |
| --- | --- |
| Langflow origin | `http://127.0.0.1:7860` |
| Running version | `1.12.2`, returned by `GET /api/v1/version` |
| Live schema | `GET /openapi.json` returned HTTP 200 |
| Deployed flow ID | `88f6a048-d942-421a-af54-d297e8033806` |
| Deployed flow name | `Identifier - LM Studio - Gamma` |
| Input component | `ChatInput-TKjnK` |
| Final output component | `ChatOutput-KxTA8` |
| Model observed in actual inference traces | `google/gemma-4-26b-a4b-qat` |
| LM Studio URL in the deployed model component | `http://localhost:1234/v1` |

The LM Studio URL is not the Langflow application API address.

The version and OpenAPI endpoints accepted unauthenticated GET requests.
Unauthenticated flow reads, file listing, and an empty-body request to the run
endpoint returned HTTP 403. The run endpoint explicitly required a valid API key.
No authentication-bypass setting was changed.

The instance's existing `GET /api/v1/auto_login` route returned a session token
and cookies. Those cookies allowed reading the deployed flow. For each recognition
check, a one-hour test API key was created through the authenticated local API,
kept only in script memory, and supplied in the `x-api-key` header. All four keys
were revoked in cleanup and their absence was verified through the live key list.
No reusable application API key was left configured.
The test client's cookie jar also retained the Desktop login cookies. The verified
successful recipe therefore carried both those cookies and `x-api-key`; a separate
key-only client was not exercised. Credentials were omitted from saved requests.

Langflow Desktop was initially closed. Early probes received Windows connection
refused errors. The installed Desktop application was reopened with its existing
configuration; startup eventually completed. The successful service inspection is
recorded in `data/integration/20260925T165945122775Z/`, including `version.json`,
`openapi.json`, `deployed-flow.json`, and `access-checks.json`.

## 2. Flow preservation

The deployed component IDs, component code, Agent Instructions, recognition
parameter values, and structured edge connections matched the frozen export.
The graph JSON was not byte-identical: editor metadata differed, including two
`_frontend_node_flow_id` values in tool components. Those differences were not
changed. The historical Qwen selector was also left unchanged; actual model traces
identified Gemma in every recorded model call.

The graph read before and after every recognition run was unchanged. A final live
read also matched the initial live graph. The original export and its preserved
copy at `reference/langflow/Identifier_LM Studio_Gamma.json` have the same SHA-256:

```text
9cb629b672f9b63dc454be4b9b25fd83032b7be156944894d62363e3216a2006
```

No flow, Agent Instructions, model configuration, or search-tool configuration was
edited. No package was installed.

## 3. Image preparation and upload

The checks reused existing prototype photos from Langflow's local cache:

```text
%APPDATA%\com.LangflowDesktop\cache\16d25458-4005-4444-af4d-480ebb238789\
  L_511Y_1 (1).jpg   — Levi's overview
  L_511YTag.jpg      — Levi's back patch
  GF-SS2.png        — white shoes
```

Python application code copied each original into the project's local evidence
directory. Original copies were byte-checked against their sources. Pillow 12.3.0
from an existing bundled Python runtime decoded each file, applied EXIF orientation,
flattened transparency onto white, and saved an RGB JPEG at quality 95 with no
chroma subsampling. Dimensions were retained: 1800×2400, 3024×4032, and 576×669.
The resulting JPEG files were decoded and validated again during verification.

All three uploads used:

```http
POST /api/v1/files/upload/88f6a048-d942-421a-af54-d297e8033806
x-api-key: <in-memory test key>
Cookie: <in-memory Desktop session cookies>
Content-Type: multipart/form-data; boundary=<generated boundary>
```

The multipart field was `file`, with a generated `.jpg` filename and MIME type
`image/jpeg`. Each upload returned HTTP **201** with these exact response keys:

```json
{
  "flowId": "88f6a048-d942-421a-af54-d297e8033806",
  "file_path": "88f6a048-d942-421a-af54-d297e8033806/2026-09-25_13-05-21_identifier-m1-0518b8f8f05f49af82b3807405d47a63.jpg"
}
```

This example is the actual first-upload response. The returned relative file path
was used unchanged in the subsequent run request. Browser file paths were not used.
JPG and PNG source normalization were exercised; WebP input was not live-tested.

## 4. Exact successful execution request

All four recognition requests used:

```http
POST /api/v1/run/88f6a048-d942-421a-af54-d297e8033806?stream=false
x-api-key: <in-memory test key>
Cookie: <in-memory Desktop session cookies>
Content-Type: application/json
```

The following is the complete first request body:

```json
{
  "input_request": {
    "input_value": "Identify this product according to the Identifier workflow.",
    "input_type": "chat",
    "output_type": "chat",
    "output_component": "ChatOutput-KxTA8",
    "session_id": "identifier-m1-a-20260925-7f5db1",
    "tweaks": {
      "ChatInput-TKjnK": {
        "files": [
          "88f6a048-d942-421a-af54-d297e8033806/2026-09-25_13-05-21_identifier-m1-0518b8f8f05f49af82b3807405d47a63.jpg"
        ]
      }
    }
  }
}
```

The `input_request` wrapper agrees with the live OpenAPI schema and worked in all
four calls. An unwrapped body was not tested. Only Chat Input file evidence was
passed through `tweaks`; no recognition settings were overridden.

The image follow-up used the same session ID, a new uploaded tag-image reference,
and this input text:

> Here is the requested back-patch image of the same item. Reassess using this additional evidence and the original photo.

Only the new tag image was attached to that request. The original image was not
reuploaded or attached again.

The shoe follow-up used its separate session ID, `files: []`, and this input text:

> Manual evidence for this same pair of white shoes: Brand: Goodfellow & Co. Product Name: Unknown. Reassess the item using this evidence and the original photo.

That brand evidence came from the accepted prototype specification. The model
returned the supplied brand in its supported Brand field.

## 5. Exact response envelope and final-output extraction

All four run calls returned HTTP **200**. The top-level JSON keys were `session_id`
and `outputs`. Each member of the outer `outputs` array contained `inputs` and an
inner `outputs` array. The selected component result contained:

```text
results, artifacts, outputs, logs, messages, timedelta, duration,
component_display_name, component_id, used_frozen_result, token_usage
```

The verified final-text location was:

```text
response.outputs[*].outputs[*]
  select component_id == "ChatOutput-KxTA8"
  .results.message.text
```

The extractor checks that exactly one matching component exists; the response and
message session IDs match the requested session; sender is `Machine`; `error` is
false; `properties.state` is `complete`; and final text is nonempty. It does not
select intermediate Agent/tool content or assume that an arbitrary first message
is the final result.

The final text is a labeled string, not a JSON recognition object. Observed labels
included `Status`, `Name`, `Brand`, `Product Name`, `Style Accent`, `Item Type`,
`Candidate`, `Evidence`, `Missing Evidence`, `Next Action`, and `Sources`.
The final shoe response omitted `Sources`. Its absence therefore cannot be treated
as proof that no search ran. The duplicated `messages[].message` display text had
different blank-line formatting; extraction used `results.message.text` instead.

Only envelope extraction was implemented in this milestone. A complete labeled-
text-to-application-state parser was not built, and no application recognition
state was invented from an error or malformed result.

## 6. Observed recognition runs

Runs were deliberately interleaved between products.

| Order | Test | Langflow result | Run request time |
| --- | --- | --- | --- |
| 1 | A: Levi's overview | Needs Evidence; Brand Levi's, Item Type Jeans | 65.765 s |
| 2 | B: white shoes, PNG normalized to JPEG | Needs Evidence; Brand/Product Name unknown, Item Type Shoes | 33.500 s |
| 3 | A: new back-patch image, same session | Resolved; `Levi's 511 Green Logo Waistband Jeans` | 90.516 s |
| 4 | B: manual brand, no new image, same session | Needs Evidence; Brand Goodfellow & Co., Product Name unknown | 70.219 s |

These are individual observed runtimes, not controlled performance benchmarks.

Session A: `identifier-m1-a-20260925-7f5db1`

Session B: `identifier-m1-b-20260925-829ce4`

## 7. Image continuity and product isolation

Verification read the running instance's session histories and model-input traces
through authenticated monitor endpoints. It decoded the base64 images in the
actual recorded ChatOpenAI input spans and compared their SHA-256 values to the
normalized JPEG bytes. This establishes attachment continuity beyond the model's
verbal claim that it remembered an image.

| Run | Images actually recorded in each model call | User turns actually recorded |
| --- | --- | --- |
| A initial | A overview only | A initial only |
| B initial | B overview only | B initial only |
| A image follow-up | A overview plus A tag | A initial plus A follow-up |
| B manual follow-up | B overview only, in both model calls | B initial plus B manual evidence |

Every model call used Gemma. The image sets for A and B were disjoint, and each
model input contained exactly its own session's user turns. The final live history
for each session contained four messages: two user turns and two model results.
All stored image references still resolved to the expected JPEG bytes.

Therefore, for these runs, **prior images remained usable on both image and
text-only follow-ups without resending them**, and the two product sessions stayed
isolated. No restart, expiry, deleted-file, concurrent-call, or 100-message-limit
behavior was tested.

## 8. Discrepancies and limits found

1. **Research instruction was not always followed.** The Levi's tag follow-up
   returned Resolved with Product Name `511`, but its live trace contained one model
   call and no tool calls. Its Sources section named user-supplied images only.
   This conflicts with the frozen instruction requiring live Web Search before an
   exact Product Name. The application code preserved the result as received;
   neither the prompt nor the result was changed. Successful transport does not
   establish compliance with that research rule.
2. **Search worked, page access was limited.** The shoe manual-evidence follow-up
   invoked `perform_search` once and returned three search results. Their fetched
   eBay/Poshmark page contents reported HTTP 403. The model returned Needs Evidence.
   No separate URL-tool call occurred in these runs.
3. **Request wrapping matters.** The verified contract uses `input_request`, rather
   than assuming that a documentation example's unwrapped payload is interchangeable.
4. **Authentication is real.** The LM Studio dummy key is not the Langflow API key.
   Temporary local keys were required and successfully cleaned up.
5. **Stored file shape differs from upload shape.** Upload returned a relative
   `file_path`; the history API returned `files` as a JSON-encoded string containing
   absolute local cache paths. The verifier decoded that string before checking files.

These checks did not exercise Unresolved, no-more-evidence, user correction,
multiple images in a single initial upload, WebP input, HEIC, LAN access, or
production timeout recovery. They were outside this milestone's ten integration
checks. The scripts make no automatic recognition retries.

## 9. Evidence and checks

Recognition evidence directories under `data/integration/`:

```text
20260925T170521157291Z-a-initial/
20260925T170648308418Z-b-initial/
20260925T170750219579Z-a-tag-followup/
20260925T170953016781Z-b-manual-followup/
```

Each contains the exact run request, raw response, extracted final text, session
history, before/after flow snapshots, timing/cleanup summary, and applicable image
originals, normalized JPEG, and upload receipt.

The final verification report is:

```text
data/integration/20260925T171240694837Z-verification/verification.json
```

That directory also preserves live session histories and trace snapshots with
inline images replaced by their hashes and credential fields redacted.

Checks passed:

- Four live executions and final-output extractions.
- Three normalized JPEG uploads and byte-preserved originals.
- Exact model-input image and user-turn comparisons for both sessions.
- Final live history isolation.
- Seven negative envelope checks: wrong session, missing output, duplicate output,
  empty final text, wrong sender, error flag, and partial result all raised errors.
- All temporary API keys absent from the final live key list.
- Frozen flow preservation and unchanged export checksum.

The connection probe is standard-library-only. The historical execution and
verification scripts used an existing bundled Python/Pillow runtime. Current
application commands use the project-local `.venv` described in SETUP_WINDOWS.md.

No frontend, FastAPI application, production compatibility parser, job-management
system, or session-storage framework was created. Test sessions, uploaded test
images, and local evidence were retained. The Desktop application was left running.

All ten requested integration checks now have live evidence. There is no remaining
transport/session blocker. The observed research-instruction discrepancy remains
a recognition-policy issue for human review before treating every Resolved result
as externally verified. Work stops here for Milestone 1 review.
