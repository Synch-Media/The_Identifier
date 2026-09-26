# Troubleshooting the current MVP

| Symptom | Check / recovery |
| --- | --- |
| `.venv\Scripts\python.exe` missing | Complete the explicit Python 3.12 setup in SETUP_WINDOWS.md. The Python launcher was not registered for the reference interpreter. |
| PowerShell blocks `.ps1` | Use the direct Python / npm commands in SETUP_WINDOWS.md; no machine-wide execution-policy change is required. |
| npm is blocked as a PowerShell script | Use `npm.cmd`, as documented. |
| Package installation denied or unavailable | Check network/proxy/cache permissions and the exact locked package. Do not upgrade the working dependency set to hide an access error. |
| Port 5173 or 8000 already occupied | Check whether Identifier is already running. Reuse the running app or stop your own old terminal before starting another copy. |
| Browser opens but API fails | Check backend terminal and `http://127.0.0.1:8000/api/health`; Vite proxies `/api` to port 8000. Open the UI on port 5173. |
| Another item is being analyzed (409) | Wait for the current local job. One backend process/worker is required. |
| Langflow connection failure | Wait for Desktop startup; check `http://127.0.0.1:7860/api/v1/version` reports 1.12.2. |
| Langflow HTTP 401/403 | The current client requires the validated Desktop auto-login/cookie/key recipe. A dummy LM Studio key is not a Langflow key. Do not bypass server authentication. |
| Flow/component missing, HTTP 404 or import error | Compare installed flow/component IDs to SETUP_WINDOWS.md and ensure the existing LM Studio extension component resolves. A fresh import may assign a different flow ID. |
| LM Studio unavailable / wrong model | Check local server port 1234 and served ID `google/gemma-4-26b-a4b-qat`; load the Q4_0 reference model. Ignore the export's historical Qwen selector. |
| Model load fails / memory pressure | The 75% GPU offload reference used 16 GB VRAM and 128 GB RAM. Adjust hardware-dependent offload/batch/cache settings for available memory; the recorded hardware is not a minimum requirement claim. |
| Photo rejected | Use nonanimated JPG, PNG or WebP, at most 20 MiB and 25 megapixels. HEIC and camera capture are unsupported. At most eight photos per item. |
| Cannot remove a retained photo | Submitted evidence is already in Langflow history. Start New Item to exclude it from a new conversation. |
| Malformed final output / failed execution | Expand Debug / Technical Details. The parser refuses invalid status/duplicate fields/missing required output. No recognition result is fabricated. Check services, then start a new item. |
| Long wait / timeout / interrupted backend | Langflow may still be working after the client's 420-second run timeout. Check its activity before another run; there is no cancel endpoint or automatic retry. |
| Brand/type known but Product Name absent | Needs Evidence or Unresolved is expected. Catalog codes are evidence, not a marketed name. General acceptance is offered only for supported Unresolved general identities. |
| Resolved identity is wrong or lacks sources | Use Edit or Not This Item. Recorded runs show errors and missed research; Resolved does not prove independent verification. |
| Web research returns 403 / no useful page | Public sites can reject automated access; the frozen flow may return insufficient evidence. Do not invent supporting sources. |
| Temporary-key cleanup warning | A forced shutdown or failed revoke can leave the one-hour key until expiry. Check the trusted local Langflow instance; never paste tokens into issue reports. |
| Browser regression cannot launch | Install Google Chrome. The existing tests explicitly use `channel: 'chrome'`. Keep Vite running on 5173. |
| Live QA fails on missing image files | Historical live scripts use private, excluded data. This is expected in a clean checkout; ordinary tests use synthetic fixtures instead. |

The backend health endpoint does not test Langflow or model readiness. A successful
frontend build does not configure a production server. The app has no deletion UI
or automatic retention cleanup: Start New Item leaves older files in both the
application and Langflow stores.

For a useful issue report, describe the action, visible error and software versions.
Review any copied Debug output for private evidence first. Do not publish `data/`,
Langflow databases, `.env`, model/runtime directories, login cookies or API keys.
