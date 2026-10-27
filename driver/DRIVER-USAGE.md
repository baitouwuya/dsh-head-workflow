<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# DSH Canvas Driver 0.2.59

## Lab artifact and input actions

The existing `status`, `actions`, `run(name,args)` and `dsh-shortcut-request` / `dsh-shortcut-response` contracts are unchanged. Mutating actions still default to dry-run; only `dryRun:false` applies them. Existing `labExportDialog` remains open/read/close only and never presses Export. Omitted native export options retain the values currently shown by Studio. No new Chrome permissions were added.

| Action | Arguments and behavior |
| --- | --- |
| `labExport` | `{nodeId, format?, textureResolution?, filename?, exportSkeleton?, packUv?, dryRun?}`. Opens the selected Lab's native export UI, applies only specified options, presses the final Export button once, captures that matching native download and saves it through the bounded local writer. Returns `download.completed`, actual byte count, SHA256 and relative saved path only after the writer verifies the whole file. This is a **Studio export/conversion**, not a promise of identical Lab artifact bytes. Supported native format choices: USD, FBX, OBJ, STL, GLB, 3MF; the selected format must be offered by the current UI. Resolution choices: 1k/2k/4k/8k or `Current`; unavailable choices fail visibly. |
| `listLabArtifacts` | `{nodeId, jobId?}`. Reads jobs belonging to the Lab on the open canvas. Without a job ID it returns the job IDs/statuses; with one it returns that job's artifact IDs, names, kinds and native asset IDs. No signed URLs are returned. |
| `labDownloadArtifact` | `{nodeId, jobId, artifactId, dryRun?}`. Downloads the original artifact bytes from the freshly read native job, without Studio format/texture conversion. Supports model files, editable scenes, images, reports and ZIP bundles. Default dry-run reads metadata only. Use this for exact Lab-export hashes and metadata preservation. |
| `publishLabArtifact` | `{nodeId, jobId, artifactId, name?, position?, dryRun?}`. Verifies that the completed job belongs to the named Lab on the open canvas. If its native asset is already on the canvas, returns it unchanged. A previously published historical asset is reused in a new reference card without transfer. Otherwise a GLB or PNG artifact is downloaded, container-checked, uploaded through the captured storage/import contract and placed in a new native upload/reference card. Existing nodes are retained. Returns the asset/reference IDs. Studio may process imported models; importing unchanged bytes does not certify that Studio's later representations preserve rig, morph or image data. |
| `listCanvasAssets` | `{}` or target IDs. Reads asset IDs currently referenced by canvas outputs or input mounts and their owning node IDs. |
| `setLabInput` | `{nodeId, assetId, replace?:false, dryRun?}`. Connects an existing asset from the **open canvas** to the Lab input socket through its selected upstream output or upload reference. Live Studio rejects direct model `inputMount` on Labs. Appends an input edge by default; `replace:true` explicitly replaces this Lab's input edges. Preserves node fields and unrelated edges, refuses an active Lab, checks the revision and verifies the saved connection. An unselected historical output must first have an exact upload/reference source; the action never silently changes upstream asset selection. Cross-project asset IDs are refused. |
| `connectNodes` | Existing `{from,to,fromPort?,toPort?,dryRun?}` remains valid, including legacy empty-port defaults. Explicit ports are checked against rendered handles, saved edges and captured native type contracts. Non-image examples are model→Lab (`model`/`input`) and Lab→Lab (`output`/`input`). `auto` prefers a single rendered handle and refuses ambiguity. Repeating an identical connection returns its existing edge without another save. |

Call discovery actions and use their returned IDs. Examples below intentionally use runtime variables rather than a particular project or asset:

```js
await api.run('listCanvasAssets');
await api.run('listLabArtifacts', {nodeId: sourceLabId});
await api.run('listLabArtifacts', {nodeId: sourceLabId, jobId});
await api.run('labDownloadArtifact', {nodeId: sourceLabId, jobId, artifactId}); // preview
await api.run('labDownloadArtifact', {nodeId: sourceLabId, jobId, artifactId, dryRun:false});
const published = await api.run('publishLabArtifact', {nodeId: sourceLabId, jobId, artifactId, dryRun:false});
await api.run('setLabInput', {nodeId: destinationLabId, assetId: published.assetId, dryRun:false});
await api.run('connectNodes', {from: previousNodeId, to: nextNodeId, fromPort:'auto', toPort:'input', dryRun:false});
await api.run('labExport', {nodeId: sourceLabId, format:'GLB', textureResolution:'Current', dryRun:false});
```

Downloads default to 200 MiB, a 45-second no-byte timeout and a 240-second overall timeout. Optional `maxBytes`, `idleTimeoutMs` and `downloadTimeoutMs` are bounded to 512 MiB, 120 seconds and 300 seconds. The native-export capture also times out if no matching download arrives. It restores the intercepted anchor method on completion, timeout, STOP or navigation; unrelated downloads retain normal behavior. Saved files use generated safe names under the configured writer root's `out/`; caller paths are not accepted. A final Export click alone is never reported as a completed download. If native export uses an unsupported save mechanism or a different filename, the action reports an unconfirmed outcome and does not press Export again.

Publication records append-only durable intent before import and before canvas save. Repeat calls reuse completed results. An interrupted import or save with unknown outcome is refused rather than blindly duplicated. An already-imported asset is retained for recovery. Native signed URLs and storage credentials are never persisted in those journals. STOP cancels further local work, but cannot undo an accepted import/save or a native export already submitted.

### Installation and verification of this update

The new modules are `canvas-assets.js`, `lab-operations.js` and `artifact-download.js`; the manifest now loads durable storage directly. Sync the source using `sync.ps1`, update the owned local writer using `start-writer.ps1`, then reload the extension and the Studio tab. The writer health response must advertise `artifact-chunks`. A stale writer fails before the native Export press. This is not a flow.js-only update; the old hot UI loader does not install the new artifact writer or the new modules. Existing `flow.js` is left untouched and starts no new pipeline work.

Run the current suites with `node --test tests/canvas-assets-v059.test.cjs tests/lab-operations-v059.test.cjs tests/artifact-download-v059.test.cjs tests/ui-export-v059.test.cjs tests/writer-artifacts-v059.test.cjs` (35 checks), then `node tests/runtime-v059.test.cjs` (33 checks). They exercise the shipped source, public MAIN/isolated/DOM action contract, native-shaped requests, real chunk-file writer and UI fixtures. Historical tests referring to retired driver-core files are not the current suite. Tests use mock native transport: they are not a claim of a live publication or input/edge mutation. The implementation was developed while the current canvas nodes were held unchanged. Native export selectors were read from the live Studio dialog; end-to-end execution after extension reload remains a separate verification step.

### Reusable Lab prompts

Lab prompts and node descriptions describe operations on the input model, input image, incoming GLB or previous stage's artifact. They must not hard-code source node names, asset filenames, versions or hashes. Read repository configuration, source identity, filenames and hashes at run time; record concrete values only as observed provenance. Keep historical submitted prompts as evidence rather than rewriting them.

---

Automatic reload flow, popup shortcuts, and a click-free page API. No prepare, grant, arm, permit, repeated read equality or certificate steps. Inputs must parse and editing operations must target the open canvas. Keep STOP, readable errors, redaction and balance accounting. Dry-run is the default for mutations.

Current flow.js registers the UI compatibility runtime only. It starts no generation or UI action. Older generation-flow sections below describe archived proofs.

## Agent API

The extension injects flow.js into MAIN after driver readiness. It calls window.__dshShortcut.run(name,args) directly. The isolated popup object is separate. The DOM event bridge below remains supported for external page callers; flow.js itself uses no CustomEvent caller.

The browser automation tool can evaluate only read-only page JavaScript; it cannot invoke mutating calls. The installed extension executes its authorized flow without operator scripts or clicks.

```js
function tripoAction(name,args={}) {
  return new Promise((resolve,reject)=>{
    const id=crypto.randomUUID();
    const timer=setTimeout(()=>{document.removeEventListener('dsh-shortcut-response',receive);reject(Error('Timed out locally; check status or STOP before resubmitting.'));},300000);
    function receive(e){if(e.detail?.id!==id)return;clearTimeout(timer);document.removeEventListener('dsh-shortcut-response',receive);e.detail.ok?resolve(e.detail.result):reject(Error(e.detail.error));}
    document.addEventListener('dsh-shortcut-response',receive);
    document.dispatchEvent(new CustomEvent('dsh-shortcut-request',{detail:{id,name,args}}));
  });
}
await tripoAction('status');
await tripoAction('actions');
```

Requests: {id,name,args}; responses: {id,ok:true,result} or {id,ok:false,error}. args may be an object or a JSON string. The same handlers serve the popup and events. No trusted click is required.

The driver observes startup traffic automatically for the authorized flow. Credentials and native canvas identity come from actual page requests. Explicit capture also continues across one navigation within 60 seconds. Credentials remain in memory. STOP clears them. After STOP, capture and reopen before authenticated actions.

| Action | Behavior |
| --- | --- |
| capture | Observe native traffic, including one subsequent reload. Never starts a generation. |
| read | Read the open canvas and credit balance. Optional count repeats at two-second spacing. |
| createCanvas | {name,dryRun:false}: CreateProject {}, optional UpdateProject, return projectId/canvasId/url. Caller opens the returned URL. |
| uploadAsset | {sourceUrl OR base64 OR bytes,filename,mime,dryRun:false}. Captured PNG flow: temporary_token → signed S3 PUT → ImportInputAssets. Returns assetId and before/after balances. sourceUrl is fetched in the page with credentials omitted; CORS failure is reported without a fallback or retry. PNG is the captured format; other formats are unverified. |
| createNode | {type,params,inputMount?,position?,nodeTemplate?,body?,dryRun:false}. Append using the native node shape, save, read revision. Bundled native Upload and Generate Image shapes work on a fresh empty canvas. |
| connectNodes | {from,to,fromPort,toPort,dryRun:false}. Both IDs must exist on the open canvas. Image ports are explicitly 'image'. |
| saveCanvas | {body?,dryRun:false}. Save supplied body or the latest read canvas projected onto observed native write fields; one GetCanvas updates the revision. No equality proof. |
| generate | {nodeId,params?,model?,amount?,scale?,t_pose?,sketch_to_render?,prompt?,dryRun:false}. Save recipe then submit captured MODE_CONTROL / RUN_ORIGIN_CANVAS / includeCompleted:true with a fresh idempotency key. Returns runId and provisional accounting. |
| waitTask | {runId?,timeoutMs?}. Poll GetRun every 2.5 seconds; returns completed node outputs and final accounting. Default four minutes. Failure includes failCode and balance. Timeout leaves the run tracked; wait again or STOP. |
| export | Write redacted evidence through the existing local writer. Does not save the canvas. |
| stop | Abort local I/O immediately. For a submitted task, request server cancellation separately and report its confirmation. An interrupted submission without a run ID has unknown outcome; do not blindly retry. |
| run | Sequential plan steps: capture, prompt, saveCanvas, inspectGlb, exportGlb. Prompt replay still needs a native CreateTurn captured on the open canvas. |

Editing defaults to dry-run and sends zero requests. Unknown pricing is not invented. No credit approval gate or spending cap is imposed. Before/after balances are recorded. Failed tasks can still cost credits; report their actual balance. No automatic retries or concurrent mutations. A tracked run blocks another submission until waitTask or STOP resolves it.

## Reload workflow

Edit <SHARE_ROOT>\ext\flow.js, choose a new config.runKey for a new run, sync to <EXT_DIR>, and reload a Studio /projects page. After this version is installed, flow.js-only edits need a page reload, not an extension reload. Manifest and content-script edits still require the VM's Chrome restart procedure.

The flow creates and names its own canvas, opens it, uploads the bundled original input.png, creates Upload and Generate Image nodes, connects image ports, runs the original recipe, polls, and saves. It persists step results across the create/open navigation. The bundled PNG is the operator-authorized original input, SHA256 4bbaa4f66d73286409f86bebe1e1cda979d107897bee2a601883de5c3b511ead, 2,479,760 bytes. Packaging avoids dependence on the old asset URL, which returned HTTP 403 in the first live flow test. No credential is packaged.

Read document.title, document.body.dataset.dshFlowStatus and JSON.parse(document.body.dataset.dshFlowResult). The terminal result is written through the existing local writer to runs/p3-recording-<timestamp>/checkpoint.json with capture.json and log.txt. Output IDs, URLs, per-step times, and before/after balances are in the result. No new service endpoint is involved.

A completed, failed or stopped runKey does not submit again on reload. To begin another run, edit runKey. An interrupted mutation with unknown outcome stops rather than silently duplicating it. STOP aborts the current action and prevents the next flow step. The first error stops the flow and is displayed in the title and result. Keep the native canvas idle while the API edits it. Reload after completion to display server changes; this reload does not repeat the completed run.

## Live API proof

Run 01a16989-4dbb-7d96-a0ed-b99f192190eb succeeded via the popup-to-page API using the exact original recipe: gpt_image_2, amount 1, 1:1, t_pose true, sketch_to_render false, empty template_id, original prompt. Output asset 01a16989-b509-70ca-9023-4697fd7ae1f1 persisted and appeared after refresh. Balance: 278329 -> 278329. Evidence: runs/submit-diagnosis-1792771708107/api-proof-capture.json and api-proof-rendered.png.

The failed native capture had t_pose false and a nonempty template_id. Changing to the exact original recipe resolved this reproduction; the service's internal cause of studio_submit_failed remains unknown. This is not a general server-error fix.

## Captured contracts and limits

- p3-recording-1792770306931: temporary_token {client:'aws',format:'png'}; S3 accelerate PUT; ImportInputAssets objectRefs/projectId; returned READY asset.
- p3-recording-1792770402393: CreateRun exact body and root runId response. Run 01a16971-40ca-7954-948c-a1131d6f8266 then failed studio_submit_failed with no taskId. Credit balance 278329 → 278329. This is a contract capture, not a successful generation or API proof.
- The native T Pose UI stored a template_id with t_pose:false. The supplied API reproduction instead uses the originally requested t_pose:true and empty template_id. The cause of the native failure is unknown.
- Native upload credentials are requested anew for each upload and stay in memory. The PUT signer is tested against the [AWS published signature example](https://docs.aws.amazon.com/AmazonS3/latest/developerguide/sig-v4-header-based-auth.html). The endpoint and import contract came from live traffic; the signer implementation is independently built from that documented standard. Live signed upload succeeded in v0.2.54: 2,479,760 bytes, READY asset, zero credit debit. The complete create/upload/nodes/edge/generate/wait/save flow succeeded in 78.647 seconds.
- An earlier v0.2.49 export missed two temporary storage credential fields. The existing file was scrubbed in place and v0.2.50 corrected the filter. No unsanitized backup was kept. Cookies, bearer and session tokens remained redacted. See the run incident log.

## Verification and deployment

19 actual-source tests pass across separate MAIN, isolated and page-event VM contexts with a mocked transport; includes upload ordering, dry-run, accounting, generation, task tracking, redaction and STOP abort. The AWS published signature vector passes. These are offline tests, not browser API execution.

Source: <SHARE_ROOT>\ext. Sync with powershell -File <SHARE_ROOT>\ext\sync.ps1 to <EXT_DIR>. This VM requires Chrome restart to load the manifest; preserve its tabs. No new permissions were added. Runtime has 16 files including flow.js and input.png; driver.js is 29,088 bytes. Seven flow tests additionally verify navigation, direct MAIN calls, idempotence, first error and STOP.

## Three-stage workflow configuration (2026-10-23)

The current flow.js configuration creates dsh-body-clothes-hair-v1 and reproduces the observed source recipes: T-pose, base body, clothed body, head, then standalone hair. Five serial generations produce the three target images; six nodes and 11 original incoming connections are preserved. Each stage records its run ID, output asset IDs, duration and balances. The original prompts and ports are in runs/three-stage-1792775569327/recipes.json. Runtime remains v0.2.54; only flow configuration changed.

The final layout is saved through the same API. Studio recenters the graph on reload, so a uniform x translation has no rendered effect. The display arrangement keeps the three targets together below the prerequisite cards; the reference card sits farther right to keep target images clear of the Agent panel. Terminal reloads do not regenerate. Evidence and tests are in runs/three-stage-1792775569327.

## Auto-layout (v0.2.55)

Open a canvas, open the DSH Canvas Driver popup, and choose **Auto-layout**. Leave **Dry-run** checked to preview; uncheck it to save. Empty arguments use defaults. The action reads the current canvas itself. Dry-run performs a read but sends no mutation. Save changes only positions and existing container sizes, retaining recipes, assets, edges, names and parent membership. Reload the Studio tab after a save to display server geometry.

Using the page-world `tripoAction` event-bridge helper above:

```js
const preview = await tripoAction('autoLayout');
const result = await tripoAction('autoLayout', {dryRun:false});
// Optional spacing and origin in canvas units:
await tripoAction('autoLayout', {gapX:180, gapY:60, origin:{x:0,y:0}, dryRun:false});
// Restore a returned layout inverse, preserving current content:
await tripoAction('autoLayout', {inverse:result.inverse, dryRun:false});
```

The planner derives layers from connections. Inputs start at the left, consumers follow their dependencies, branches occupy separate rows, and downstream single-child nodes align with their input. Disconnected lineages occupy separate bands. Existing nested sections retain their children and fit with the previously observed 64px padding. Cycles are collapsed into a column and reported; cycles or contradictory section ordering can prevent every edge from pointing right. Duplicate port-specific edges are preserved. No generation action is called.

Planning is deterministic for unchanged graph content, dimensions and options. A repeated apply returns changedNodes:0 and skips SaveCanvas. STOP aborts pending reads or the pause before save. An already accepted save cannot be undone by STOP; use its inverse. The result includes changes, inverse, changedNodes, planned metrics, warnings, revision and before/after balances on apply. Dimensions use rendered unscaled card sizes, then saved sizes, then a 303px fallback. Metrics are planning results; native section normalization and offscreen card sizing still require visual inspection after reload. Live validation covers the six-node canvas; nested/cyclic graphs and the captured 63-node graph have offline coverage.

The packaged flow.js is idle after the one-time live proof. To run a custom workflow, explicitly install that workflow in flow.js; the prior three-stage recipe flow is archived in the auto-layout evidence pack. The popup and DOM event bridge work independently of flow.js.

## First-click startup fix (v0.2.56)

Auto-layout now waits for Studio's own startup requests to supply the current canvas identity and authenticated request context. Capture and an extra reload are not prerequisites. The API's ready field is false until that context is available. A request made immediately after document_start remains pending and continues once startup completes. STOP cancels the wait, changing canvases cancels it, and a 30-second timeout sends no changes. This readiness wait only observes normal startup traffic; it does not guess endpoints or persist credentials.

A plain reload still displays the saved arrangement. Auto-layout does not submit generations. Existing dry-run, inverse, cycle reporting and spacing behavior remain unchanged.

## Fixed-node generation (0.2.57)

generate accepts nodeId for Image, Smart Mesh, HD Model, Texture, Rigging and Smart UV nodes. With no parameter overrides it retains the current recipe. Read the open canvas before a batch, then call generate and waitTask serially for each ready node. The captured MODE_CONTROL/CreateRun envelope selects that node; the backend resolves connected inputs. AI 3D Lab uses its native conversation and is not submitted through this action. Per-run balances and STOP remain unchanged.

## UI actions (0.2.58)

These actions repeat observed UI operations. They do not use guessed service endpoints or private framework state. Panel toggles and zoom are intentionally excluded.

| Surface | Action | Arguments and result |
| --- | --- | --- |
| Studio canvas | selectNode | `{nodeId,dryRun:false}` selects the rendered node by ID. Returns selected state and internal DOM click count; already-selected nodes are unchanged. |
| Studio AI 3D Lab | labExportDialog | `{nodeId,operation:'open'|'read'|'close',dryRun:false}` opens, reads or closes that node's native Export dialog. Returns filename, format, resolution and skeleton/UV switches. **Does not press the final Export button, change options or download a file.** |
| Local review companion | labTestAllControls | `{dryRun:false}` runs the existing **Test all controls** calculation and returns its fresh UV-atlas results. This is not a native Studio action or a test of geometric blinks. |
| Local review companion | labMeasureAllMorphs | `{dryRun:false}` runs the existing **Measure all morphs** calculation and returns changed vertex counts and maximum displacement for every morph. This is not a visual-quality certificate. |

All default to dry-run. Use the page-world `tripoAction` DOM-event helper at the top of this document; no trusted click or grant step is required. The Studio popup also exposes Select node and Lab export dialog. Missing nodes, absent native export controls, wrong surfaces and changed pages return readable errors. STOP cancels pending selection/model/dialog waits and prevents subsequent actions. It cannot undo a native click or interrupt a synchronous review calculation after dispatch.

```js
await tripoAction('selectNode', {nodeId:'<existing node ID>', dryRun:false});
await tripoAction('labExportDialog', {nodeId:'<existing Lab node ID>', operation:'open', dryRun:false});
await tripoAction('labExportDialog', {nodeId:'<existing Lab node ID>', operation:'close', dryRun:false});
// On the matching local review companion page:
await tripoAction('labTestAllControls', {dryRun:false});
await tripoAction('labMeasureAllMorphs', {dryRun:false});
```

The test labels were found in the earlier local GLB viewers, not native Lab. The new companion serves copies under runs/ui-actions-1792857827564/review; sealed prior pages/models are read-only. Start it with `node <SHARE_ROOT>\ext\serve-review-companion.cjs`, then read that run's review-server.json for the actual loopback URL. The fixed server map serves only those review files and dependencies. No Chrome host permissions were added. The popup remains Studio-only; companion actions use the page event bridge.

For a browser tool restricted to read-only evaluate, navigate the companion to `controls/?model=final&dshAction=labTestAllControls` or `morphs/?model=final-avatar.glb&dshAction=labMeasureAllMorphs`. The companion's own page script dispatches and receives the documented DOM events. Read `JSON.parse(document.body.dataset.dshReviewResult)` for the actual result. With no dshAction, nothing runs automatically. Tests run against the existing review algorithms; the controls page uses the earlier atlas candidate only to reproduce that calculation, not to approve it for production.

### Loading into the existing VM session

The packaged manifest and driver are0.2.58. This VM's native Chrome controls did not perform the requested restart, so the current session can load the same UI module through the existing flow.js resource. `ui-hot-runtime.js` registers the new names with the DOM bridge and delegates old actions to the existing driver. Runtime status reports version0.2.58, baseDriverVersion0.2.57 and uiRuntime `flow-loader` when this compatibility path is active. After a normal Chrome restart loads the new manifest, the driver registers these actions directly and the compatibility setup is a no-op.

The final flow.js contains registration only, with no automatic UI action or generation. Explicit benchmark flows are archived in the evidence pack. The one-time native proof uses the real page-world event bridge and reports agent clicks separately from internal DOM clicks; a reduction in tool-call clicks is not elimination of UI dispatch under the hood.



## Durable flow storage (2026-10-26)

Maintained Lab/new-card/scaffold flows embed durable-state.js. Full sanitized state, profiles and evidence are append-only IndexedDB revisions; localStorage carries only small pointers plus the unchanged native-save-hold marker. The TOTAL dsh-* footprint, including key names in UTF-16 bytes, must remain strictly below64000bytes. Each write records navigator.storage.estimate and per-key sizes; commits/readback checks finish before the next mutation. No history eviction/deletion/compression is permitted. Old --compact-snapshots, default in-place carrier replacement and manual compaction are retired.

Storage failures show a visible key/reason/job-identity banner. No-request and unknown-outcome states are distinguished; a known job must be monitored/resumed, not assumed cancelled. --resume-job-id pins a read-only known-job recovery and forbids creation. Generated flows embed the adapter, so no new manifest permission or Chrome restart is required. See runs/head-refinement-1792921289985/routes/sm-canvas-reconstruction/durable-state-upgrade/README.md for tests/migration evidence. All current Tripo uploads/reconstruction submissions are frozen under the operator internal-only scope.

## Lab profile routing (2026-10-26)

Generated Lab flows now require the explicit query `?dshRun=<config.runKey>` on the own canvas URL. This selects the intended profile; it is not an approval step. A mismatched URL remains idle. Post-submit automatic reload is disabled. Wait for and record the returned native job ID and node ID before changing the deployed flow. Known-job recovery reads the existing native job; it does not submit another build. Artifact downloads refresh their native download link in memory, show byte progress, honor STOP, and fail visibly after 45 seconds without bytes. No signed URL or authentication value is persisted.

Cross-node Lab workspaces may not be able to fetch a redacted artifact URL directly. Supply the already downloaded source through the verified native PNG metadata carrier when needed: `dsh.recipe.zip.base64`, `dsh.recipe.zip.sha256`, and an explicit source-only purpose label. Verify the exact ZIP hash in Lab before extracting. Never put secrets, VRoid data or model binaries in a source-only carrier.
