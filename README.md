# Identifier — working local MVP

Identifier helps a reseller identify a product from photos and optional manual
information. It combines a local vision model with live web research and a human
review loop. This checkpoint contains the working FastAPI backend and
React/TypeScript browser application, not just a Langflow prototype.

## Reference stack

- **Gemma 4 26B A4B QAT, GGUF Q4_0**, served by **LM Studio**.
- **Langflow 1.12.2** with the preserved Identifier flow, Web Search and URL tools.
- **FastAPI / Pydantic / Pillow**, Python **3.12.14** in the tested environment.
- **React / TypeScript / Vite**, tested with Node **24.14.0**, npm **11.9.0**.
- Windows desktop, one local user and one recognition job at a time.

See [Windows setup](docs/SETUP_WINDOWS.md) for installation, exact configuration,
startup commands, tested LM Studio settings, and the fresh-machine integration
boundary. GPU offload and memory settings depend on hardware.

## Start an already configured installation

1. Load the reference Gemma model in LM Studio and start its local server on 1234.
2. Start the validated Langflow Desktop instance on 7860 with the reference flow.
3. From the project root, in separate PowerShell terminals:

   ```powershell
   .\scripts\start-backend.ps1
   ```

   ```powershell
   .\scripts\start-frontend.ps1
   ```

4. Open <http://127.0.0.1:5173>. Stop these terminals with Ctrl+C after recognition
   finishes. Do not start duplicates if those ports are already in use.

The backend binds to 127.0.0.1:8000 with one worker; Vite binds to 127.0.0.1:5173
and proxies `/api` to it. No `.env` file is read or required. Flow addresses and
component IDs are currently source constants, described in the setup guide.

## Use the application

Choose or drop photos, optionally expand **Add What I Know**, then click
**Identify**. The app supports image-only, manual-only, and mixed evidence; no
chat prompt is required. Uploading alone does not start recognition.

- **Resolved:** review the evidence and choose **Looks Right**, **Edit**, or
  **Not This Item**. Local confirmation/correction/rejection makes no model call.
- **Needs Evidence:** add a photo or manual information, then choose
  **Identify with Added Evidence**. **I Don't Have More Information** requests a
  real reassessment of the same item.
- **Unresolved:** review retained evidence and the reason; add new evidence to
  reassess. **Accept General Identity** is available when an item type is supported
  and an exact Product Name is absent. It saves a separate user decision.

**Start New Item** creates new application and Langflow session IDs. Prior session
files remain on disk. Submitted images stay in that item's Langflow conversation;
only pending images can be removed. Reload recovers the current item in that tab.

Recognition status, execution state, and user decisions remain separate. A user
correction does not overwrite original attempt outputs. Known catalog identifiers
(UPC/MPN/SKU/barcodes) stay evidence rather than being promoted to marketed Product
Name. Operational errors become `failed`, never an invented `Unresolved` result.

## Limits and data

JPG, PNG and WebP only: up to 8 photos, 20 MiB / 25 megapixels per photo and
12 attempts per item. Photos are EXIF-oriented, flattened onto white and converted
to RGB JPEG. Animated images, HEIC, camera capture, LAN and multi-user use are not
supported. There is no cancellation, automatic recognition retry, session-history
browser, encryption or retention cleanup.

`data/` holds private photos, sessions, attempts, screenshots and integration
captures. It is excluded from Git. Langflow also retains uploaded evidence and
history in its own external runtime storage. Backend credentials stay in memory;
a temporary key is created per attempt, revoked in cleanup, and expires within
one hour. This relies on the existing trusted local Desktop auto-login setup.

Inference is local; research is **not offline**. The existing flow sends searches
and page requests to public web services. Review submitted evidence accordingly.
A Resolved label is not independent verification: recorded runs include incorrect
identities and omitted research calls. Source access may fail. See the historical
[integration contract](docs/INTEGRATION_CONTRACT.md) and
[Milestone 2 review](docs/MILESTONE_2_REVIEW.md).

## Checks

From the project root:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
```

From `frontend`, with the Vite server running and Google Chrome installed:

```powershell
npm.cmd run build
npm.cmd test
```

Backend tests use synthetic text and generated images; browser regression tests
intercept `/api`. Neither invokes the model. The historical `test:live` script and
integration verifiers require excluded private fixtures and live services; they
are not part of clean-checkout validation. See [setup](docs/SETUP_WINDOWS.md).

## Repository guide

- [Windows setup](docs/SETUP_WINDOWS.md): dependencies, configuration and startup.
- [Architecture](docs/ARCHITECTURE.md): actual components, storage and contracts.
- [Troubleshooting](docs/TROUBLESHOOTING.md): service, image and result failures.
- [MVP specification](docs/IDENTIFIER_MVP_BACKEND_AND_UI_SPEC.md): product rules,
  current implementation reconciliation and unchanged Agent Instructions.
- [Checkpoint review](docs/REPOSITORY_CHECKPOINT.md): checks, exclusions and exact
  proposed first-commit file list.
- `reference/langflow/`: immutable validated export and SHA-256 record.
- `requirements.lock.txt` and `frontend/package-lock.json`: tested dependency pins.

Licensed under Apache 2.0. Model weights, external service runtimes,
credentials and private test evidence are not distributed with this checkpoint.
