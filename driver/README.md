<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# DSH Canvas Driver 0.2.59

The Lab export, artifact publication/download, existing-asset input and non-image port actions are documented in [DRIVER-USAGE.md](DRIVER-USAGE.md). Install the updated extension and local writer together. The new actions have offline regression coverage; live verification after reload is still pending. Existing canvas nodes and the idle flow script are unchanged.

This is a Windows/Chrome procedure. Run it on the computer that owns the logged-in Chrome session. A host inspecting a VM share is a different computer: it will not see the guest's installed extension or C: runtime. No drive letter, Codex installation, or author-account project is required.

## Prerequisites and working copy

Use Chrome, PowerShell, and Node.js 20 or later from the official Node.js distribution. `node --version` must work, or pass an absolute `-NodePath` below. The scripts optionally discover Codex's bundled Node when present; it is not required. Never copy browser credentials or profile files.

Keep a sealed release immutable. Copy its `ext` folder to an editable working directory before registration or configuration changes. New evidence belongs in a new writable artifact root, never inside a sealed tree.

```powershell
$Package = 'C:\work\tripo-studio' # your extracted editable working copy
$Runtime = Join-Path $env:LOCALAPPDATA 'DSH\tripo-ext'
$Evidence = 'C:\work\tripo-evidence' # your writable evidence destination
New-Item -ItemType Directory -Force -Path $Evidence | Out-Null
& "$Package\ext\sync.ps1" -Destination $Runtime
```

In Chrome, open `chrome://extensions`, enable Developer mode, click **Load unpacked**, and select the printed `$Runtime` directory. Find **DSH Canvas Driver** and copy its displayed 32-letter **ID**. This installation's ID may differ from every example or prior installation. Do not use an ID copied from this report.

```powershell
$ExtensionId = 'PASTE_THE_ID_FROM_YOUR_CHROME'
& "$Package\ext\start-writer.ps1" -Root $Evidence -ExtensionId $ExtensionId
# If node is not on PATH, append: -NodePath 'C:\path\to\node.exe'
```

Writer defaults to `%LOCALAPPDATA%\DSH\tripo-writer` and listens only on `127.0.0.1:43127`. Its JSON config contains the evidence root and extension ID, not authentication. Startup verifies the running writer's root and ID. It refuses a conflicting writer; do not kill an arbitrary process on that port. To replace your own writer, inspect the PID in that writer directory's `pid.txt` and its command line, stop only that verified process, then rerun startup. Chrome remains open. The writer rejects other browser origins and secret-like payloads; any local process is still within its integrity boundary.

## Register a newly created canvas

1. In your logged-in Studio, use **New Project**, and name your new empty canvas `dsh-your-purpose`. Do not register an existing production canvas merely by changing its name. Keep a record that you created it.
2. Click the extension's **D** launcher, **Start capture**, then **Arm request learning** and reload the tab once. Opening a canvas is read-only. Do not send a prompt. The observer records redacted metadata; authentication stays in page memory.
3. The URL `/projects/PROJECT_UUID` supplies the project ID. **Export trace JSON** stops capture. In the exported JSON, find an actual `CanvasService/GetCanvas` response and its `details.signals` entries `canvas.canvasId` and `canvas.projectId`. Use those observed values; never assume the two IDs are equal. Confirm the associated project name is your new `dsh-` canvas. The exported trace may need **Save JSON** or copying the visible redacted JSON to your evidence directory.
4. Edit your working copy `ext\owned.js`. Replace the author-account entries with only your proven owned pairs, retaining this JavaScript shape:

```javascript
Object.defineProperty(window,'__dshOwnedCanvases',{value:Object.freeze([
  {projectId:'YOUR_PROJECT_UUID',canvasId:'YOUR_CANVAS_UUID',name:'dsh-your-purpose'}
])});
```

5. Run `sync.ps1 -Destination $Runtime`, click the extension card's **Reload** in `chrome://extensions`, then reload Studio. This is an extension update, not a Chrome restart. The driver rechecks the live project name, exact registry pair, URL, and canvas/project relationship before acting.

## First smoke test: zero-credit state capture

Open your owned canvas. Open **D**, click **Arm request learning**, and reload once to observe the site's authenticated reads and payment balance read. Click **Connect local writer**. If inventory learning is missing, navigate to the Projects list and open your owned canvas while learning is armed. Do not supply auth headers manually.

Replace both placeholders with the registered UUIDs and paste into **Driver plan JSON**:

```json
{"version":1,"projectId":"YOUR_PROJECT_UUID","canvasId":"YOUR_CANVAS_UUID","maxCredits":0,"steps":[{"id":"state","kind":"capture"}]}
```

Click **Dry-run plan**. Expected: `mode: dry-run`, `networkRequestsSent: 0`, `predictedCredits: 0`. Click **Run plan**. Expected: `state: done`, `credits 0`, unchanged balance, `existingNonDshChanged: 0`. Find the newly created `runs\p3-run-<timestamp>` directory under `$Evidence`, with checkpoint, trace, log, manifest and SHA256. Verify:

```powershell
$Run = Get-ChildItem "$Evidence\runs" -Directory -Filter 'p3-run-*' | Sort-Object Name -Descending | Select-Object -First 1
$Checkpoint = Get-Content -Raw "$($Run.FullName)\checkpoint.json" | ConvertFrom-Json
$Checkpoint.job.steps | Select-Object id,status,creditDelta
$Checkpoint.job.isolation
Get-FileHash "$($Run.FullName)\manifest.json" -Algorithm SHA256
Get-Content "$($Run.FullName)\manifest.sha256"
```

Use **STOP DRIVER** when done; collapse **D** and return to Projects. There must be no active run or open dialog. The smoke test requires no generation template or credit spending.

## Prompt plans and explicit submission allowance

Every plan requires `maxCredits` in 0..200. **A zero cap forbids every prompt submission**, including image prompts with an observed price of zero. Read-only capture, inspection, and retrieval remain possible at zero cap. Unknown cost classes are refused. An image step additionally requires `allowZeroEstimateSubmit:true` and a positive cap; the allowance is explicit permission to submit, not a promise of zero price.

Prompt driving requires a real observed CreateTurn contract. On your newly registered canvas, arm learning and send one authorized manual prompt through the site, record the balance before/after, then **Save recording**. Do not bootstrap using a production canvas or a speculative API request. A fresh installation without this observed shape refuses prompting. Subsequent reloads retain only the redacted contract shape; current authentication and conversation still must be relearned.

Example capped image plan (substitute your IDs and text, explicitly approve any spending under your policy before running):

```json
{"version":1,"projectId":"YOUR_PROJECT_UUID","canvasId":"YOUR_CANVAS_UUID","maxCredits":1,"steps":[{"id":"image","kind":"prompt","costClass":"image","allowZeroEstimateSubmit":true,"text":"Create exactly one reference image of a cube. No 3D model.","pauseAfter":true}]}
```

Example HD plan, observed estimate 40 credits:

```json
{"version":1,"projectId":"YOUR_PROJECT_UUID","canvasId":"YOUR_CANVAS_UUID","maxCredits":40,"steps":[{"id":"model","kind":"prompt","costClass":"hd-model","text":"Generate one HD model from my existing image node. No texture or additional assets.","autoApprove":false,"pauseAfter":true}]}
```

Use **Continue step** only after reviewing the site's requested approval. `autoApprove:true` is an explicit choice for a reviewed plan. Preflight estimates and the reactive debit watcher are **not an atomic server spending limit**. A server may debit before the browser detects it. On breach, the driver retains/resolves the exact run ID, sends CancelTurn and StopRun, checks terminal state, and reads the balance to verify refund. If it cannot resolve a run ID, it reports `stop.unresolved` and requires operator action; it never claims a successful stop from an empty list. 403/429 or unexpected non-JSON stops automation. Do not bypass challenges.

## Resume, replay, retrieval and diagnostics

**Resume checkpoint** skips completed steps, reconciles identified running turns, and refuses ambiguous submissions or terminal failed/stopped steps. Never edit a paid checkpoint to pending. **Record source session** stores observed user-turn text and IDs; **Build replay plan** maps your explicit `replayIndices` and replacement prompt steps to that source. The fresh destination must be registered and owned. Full image-to-HD replay remains unproven while image submission returns `studio_submit_failed`; do not treat queued HD steps as successful.

For `exportGlb` or `inspectGlb`, use an `assetId` observed on your owned canvas, or omit it to select the last HD output on that canvas. `exportGlb` retrieves the actual observed renderer `model_url` and validates GLB before writing a hashed artifact. It can differ in encoding/size from the site's manual export. `inspectGlb` reads triangle and vertex counts without writing a model. Neither generates assets. Example step: `{"id":"mesh","kind":"inspectGlb","assetId":"YOUR_ASSET_UUID"}`. Do not compare a renderer download with a differently encoded manual export as equal work.

**Read owned diagnostics** accepts optional `diagnosticRunIds` (up to 5) and `diagnosticAssetIds` (up to 3), verifies association with the owned canvas, and stores redacted responses, HTTP status, balance and inventory. These are read-only. Session IDs, cookies, bearer tokens and signed URL query values never belong in plans, docs, logs or the share.

## Tests and maintenance

From `ext`, run `node tests/observer.test.cjs`, `node tests/ui.test.cjs`, `node tests/details.test.cjs`, `node tests/driver.test.cjs`, and `node tests/driver-runtime.test.cjs`. These are offline tests, not backend evidence. Live runs and their manifests establish observed service behavior. If Studio changes request shapes, unknown fields, prices or response meanings, stop and observe again; do not guess. Keep old release trees sealed and create a new version for further work.

## Data-flow auto-layout

Open the extension popup and choose Auto-layout. Dry-run previews without changing the canvas; uncheck it to save. See DRIVER-USAGE.md for the page-world autoLayout action, spacing options, inverse restoration and limits. Source planner: auto-layout.js. Latest proof: runs/auto-layout-1792777729724.

Auto-layout works on the first request after a page load; it waits for native startup context. No Capture + reload step is required. Startup-fix evidence: runs/auto-layout-startup-1792780883788.
