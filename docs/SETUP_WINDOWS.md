# Windows setup and startup

This guide describes the current application. It does not install or upgrade the
external AI stack automatically. The application dependency commands were checked
in an isolated clean copy on the reference Windows machine; a second-machine
Langflow import and end-to-end recognition have not been validated.

## 1. Prerequisites

Use Windows with a Python 3.12 interpreter, Node.js and npm, LM Studio, and
Langflow Desktop running Langflow **1.12.2**. Reference versions are Python
**3.12.14**, Node **24.14.0**, npm **11.9.0**. The Vite dependency declares Node
20.19+ or 22.12+; those other versions were not tested here. Chrome is needed only
for the existing browser regression tests. Choose the exact reference versions
when reproducing this checkpoint. No global application Python install is needed.

Obtain the external tools through their official distribution channels. No
third-party installer command is claimed as tested here. The project does not
bundle LM Studio, Langflow, their runtime extensions, or model weights. The LM
Studio application/runtime build number was not captured in the original test
record; the tested runtime family is Vulkan llama.cpp for Windows.

Extract/copy this project to a writable folder. Open PowerShell in that folder
(the folder containing `README.md` and `requirements.lock.txt`). The original
location is `D:\LocalAI\Projects\Identifier_LocalAI_Lab`; that drive layout is
not required. Keep models and Langflow runtime storage outside the project.

## 2. Install the application dependencies

Set `$Python` to the actual full path of your Python 3.12 `python.exe`, then run
these commands from the project root. The placeholder path must be replaced.

```powershell
$Python = 'C:\path\to\Python312\python.exe'
& $Python --version
& $Python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip check
Set-Location frontend
npm.cmd ci --no-audit --no-fund
Set-Location ..
```

The reference host used its existing Python 3.12.14 interpreter to create an
isolated venv and successfully installed the unchanged lockfile. The `py -3.12`
launcher shortcut did **not** find that interpreter on this host, so it is not
the documented installation command. An explicit interpreter path avoids relying
on launcher registration or the Windows Store alias. Do not recreate the working
`.venv` just to check an existing installation.

`requirements.txt` declares supported direct dependency ranges;
`requirements.lock.txt` pins all 24 tested Python packages, including test tools.
Use the lockfile for reproduction. The frontend lockfile pins the full npm tree
and package integrity values; `npm ci` checks it against `package.json`. No
dependencies were upgraded for this checkpoint. Python pins do not include wheel
hashes; this is version reproducibility, not an archived or hashed supply chain.
Internet/package-cache access is needed for installation.

## 3. Configure LM Studio

Load **Gemma 4 26B A4B QAT**, **GGUF Q4_0**, approximately **15.63 GB**. Its served
identifier must be `google/gemma-4-26b-a4b-qat`. Keep the model's vision support
available. Start the local OpenAI-compatible server on port **1234**.

| Setting | Tested reference |
| --- | --- |
| Hardware | AMD Radeon RX 7600 XT, 16 GB VRAM; 128 GB system RAM |
| Runtime | Vulkan llama.cpp (Windows), recorded in the validated specification |
| Context length | 32768; confirmed in the loaded-model API |
| GPU offload | 75%, recorded in the validated specification |
| API base URL used by flow | `http://localhost:1234/v1` |
| Flow model name | `google/gemma-4-26b-a4b-qat` |
| Flow temperature / seed | 0.1 / 1 |
| Flow streaming | False |
| Flow max tokens | Unset in the preserved export |
| Flow client key | `lm-studio`, a dummy value, not a Langflow credential |

The current loaded-model API additionally reports evaluation batch 2048, physical
batch 1120, parallel 4, flash attention enabled, 32 context checkpoints and GPU KV
cache offload enabled. These are observed runtime values, not extra application
configuration requirements. GPU offload, batch sizes, parallelism and KV-cache
placement depend on available VRAM/RAM and runtime support. Another machine may
need lower values. The reference hardware is not a tested minimum specification.
Do not replace the reference model to solve a memory issue; adjust hardware load
settings and verify behavior. Keep the validated flow and Agent Instructions.

Ollama is not required by this application. The export contains a historical
Qwen/Ollama selector, but the connected LM Studio model and observed inference
used Gemma. Do not switch providers based on that stale selector.

## 4. Configure Langflow — important reproducibility boundary

Start the existing validated Langflow Desktop instance and wait for startup.
It must report **1.12.2** at `http://127.0.0.1:7860/api/v1/version`.

For a new installation, the reference asset to import through Langflow's flow
import interface is `reference/langflow/Identifier_LM Studio_Gamma.json`. First
verify its hash using the command below. Do not import a duplicate into the
already working reference installation. A fresh import was not performed during
repository preparation; the exact import UI and resulting flow ID have not been
certified on a second installation.

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '.\reference\langflow\Identifier_LM Studio_Gamma.json'
```

Expected SHA-256:

```text
9cb629b672f9b63dc454be4b9b25fd83032b7be156944894d62363e3216a2006
```

The current backend imports these constants from `scripts/integration_run.py`:

| Constant | Required current value |
| --- | --- |
| `BASE` | `http://127.0.0.1:7860` |
| `FLOW` | `88f6a048-d942-421a-af54-d297e8033806` |
| `INPUT` | `ChatInput-TKjnK` |
| `OUTPUT` | `ChatOutput-KxTA8` |

The export contains these same IDs. Check the imported flow ID and component IDs
in Langflow before running recognition. If import assigns a different flow ID,
the current source constant `FLOW` must be aligned to that ID locally and the
integration revalidated; there is no environment-variable override. Do not
change node IDs, Agent Instructions, tool settings, or model choice to work
around a mismatch. This source-level configuration limitation remains in the MVP.

The flow includes the LM Studio extension component, Web Search (3 results,
500-character content limit), URL retrieval (depth 1), and the frozen agent.
The required LM Studio component must resolve in the installed Langflow runtime;
the JSON is a flow reference, not a standalone runtime installer. Live public-web
research needs internet access and target pages may deny retrieval.

The backend expects the trusted local Desktop `/api/v1/auto_login` behavior.
It uses the returned cookies to create a one-hour API key per attempt, sends both
cookies and that key, and revokes the key afterward. A password-protected or
different server deployment is not a verified substitute. Do not disable
authentication or copy another user's login/session credentials. Stop and resolve
installation compatibility if local Desktop auto-login is unavailable.

No `.env.example` is provided because the application reads no `.env` files or
custom environment variables. Creating `.env` with keys or flow IDs has no effect.
Langflow's own `.env`, database and login state belong to its private runtime.

## 5. Start the app

After LM Studio and Langflow are ready, open two PowerShell terminals in the
project root and keep them open:

```powershell
# Backend terminal
.\scripts\start-backend.ps1
```

```powershell
# Frontend terminal
.\scripts\start-frontend.ps1
```

If script execution is blocked, these are the commands those scripts run:

```powershell
# Backend terminal, project root
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
```

```powershell
# Frontend terminal, project root
Set-Location frontend
npm.cmd run dev
```

Open <http://127.0.0.1:5173>. Backend health is available at
<http://127.0.0.1:8000/api/health>; `status: ok` checks the app only, not the model
or Langflow. Never run multiple backend workers or use automatic reload during
recognition: concurrency is controlled by an in-process lock. The production
build is a validation artifact; there is no packaged production deployment here.

## 6. Run the existing checks

From the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

From `frontend`:

```powershell
npm.cmd run build
npm.cmd test
```

Keep Vite on port 5173 running for `npm test`; install Google Chrome because the
test harness uses Playwright's `channel: 'chrome'`. A Playwright browser download
is not the configured browser. The ordinary tests do not need LM Studio or
Langflow and make no recognition calls.

`frontend/tests/live-browser.mjs`, `live-exhausted.mjs` and the integration
verification scripts are historical local QA tools. They depend on private
`data/integration` / `data/milestone2` fixtures and some original absolute paths.
They are preserved as source, but cannot reproduce the old live tests from a
public checkout. Do not copy private images into Git to make them run. Current
checkpoint verification and limitations are in [the review](REPOSITORY_CHECKPOINT.md).
