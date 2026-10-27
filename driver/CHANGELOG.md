<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

## Durable flow storage v1 — 2026-10-26

- Full flow state moved to immutable IndexedDB history with verified small localStorage pointers and strict aggregate64000-byte cap.
- Awaited writes, concurrency lock, explicit quota/conflict errors and visible failure banner; no history compaction/deletion.
- Legacy writer contexts retired; real cross-tab/reload/known-job recovery verified. Adapter is embedded in generated flow.js; manifest permissions and installed Chrome version unchanged.

# 0.2.52 — retain native authenticated RPC headers

A public RPC response had replaced authenticated headers and caused a live GetCanvas replay to return HTTP 401. Capture now updates authentication only from native requests that carry x-auth-token. No token values are persisted. Regression test covers a public RPC arriving after authenticated capture.

# 0.2.51 — captured PNG upload and CreateRun contracts

Implements temporary token, signed S3 PUT and ImportInputAssets; bundles observed CreateRun constants and two native node shapes for a fresh canvas. Includes exact page-world operator scripts. Offline tests pass; live API proof remains pending. Native capture failed studio_submit_failed at zero debit.

# 0.2.50 — temporary credential redaction

Redacts sts_ak/sts_sk; captures the observed S3 origin. Prior affected capture scrubbed in place.

# 0.2.49
Capture exports redacted native request/response bodies and multipart field/file metadata. XHR capture retains the same metadata. Starts the observer when capture resumes across reload. No automatic service operation.

# 0.2.48
Added named canvas/create-node/connect/save/generate/wait adapters to the MAIN API, DOM bridge and popup. Generation retains native request constants and requires an observed run-ID response. uploadAsset is explicitly unavailable until its contract is captured. Preserved dry-run, STOP, open-canvas targeting, readable errors, redaction and accounting. 16 mocked-service checks passed; no live execution.

# 0.2.47
Added the MAIN-world shortcut convenience object alongside the existing unconditional DOM listener. Project-list reads report no open canvas.

# 0.2.46
Replaced the legacy 170 KB driver with canvas shortcuts. Removed permit/grant workflows, persistent save fences, proof jobs, repeated inventory/equality checks and certificates from the runtime. The DOM event bridge is the agent API; the convenience object lives in the isolated extension world.

## 0.2.54 — 2026-10-23

Authorized reload flow, injected from web_accessible_resources into MAIN by lifecycle.js after driver readiness. Direct API calls; resumable creation/open sequence; title/dataset result and local writer checkpoint; stop on first error. Bundle original PNG after old URL returned 403. Final save projects the latest read state so generated outputs survive. Exact original recipe now has a live successful API proof, balance 278329 -> 278329.

## Three-stage workflow configuration (2026-10-23)

The current flow.js configuration creates dsh-body-clothes-hair-v1 and reproduces the observed source recipes: T-pose, base body, clothed body, head, then standalone hair. Five serial generations produce the three target images; six nodes and 11 original incoming connections are preserved. Each stage records its run ID, output asset IDs, duration and balances. The original prompts and ports are in runs/three-stage-1792775569327/recipes.json. Runtime remains v0.2.54; only flow configuration changed.

The final layout is saved through the same API. Studio recenters the graph on reload, so a uniform x translation has no rendered effect. The display arrangement keeps the three targets together below the prerequisite cards; the reference card sits farther right to keep target images clear of the Agent panel. Terminal reloads do not regenerate. Evidence and tests are in runs/three-stage-1792775569327.

## 0.2.55
Added deterministic data-flow autoLayout action, popup button, dry-run, geometry inverse, section fitting, cycle reporting, and unchanged-layout save skipping. 33 offline tests pass. No new permissions. Live proof recorded separately.


## 0.2.56
Fixed Auto-layout failing before native startup identity/authentication arrives. Added cancellable startup wait, route-change cancellation and truthful ready status. No new permissions or generation behavior. Tests include an immediate first API call without Capture.


## 0.2.57
The generate action now accepts captured fixed pipeline node types: image, Smart Mesh, HD Model, texture, rigging and Smart UV. It preserves each node's existing recipe when no overrides are supplied. The native Smart Mesh MODE_CONTROL/CreateRun contract was observed on dsh-avatar-production-v1; AI 3D Lab remains a separate native conversation.

# 0.2.58 — observed UI actions

- Add native selectNode and Lab export-dialog open/read/close actions, with dry-run, readable errors, current-page targeting and STOP-aware waits.
- Add local-review Test all controls and Measure all morphs actions through the same page-world DOM event bridge; clearly distinguish UV-atlas checks from geometric morph measurements.
- Keep sealed review pages unchanged by using a separate companion. No new host permissions, panel toggles, zoom actions, export submission or generation.
- Provide a flow-loader compatibility runtime for the already-loaded0.2.57 manifest. New0.2.58 manifests register the actions directly after the next successful Chrome restart.
- Benchmark manual versus API click calls on identical operations and compare returned measurements/options. Internal DOM dispatches are reported separately.

# 0.2.59

- Added `labExport` with native format/resolution controls, one final Export press and a verified bounded download receipt; kept `labExportDialog` non-submitting.
- Added original-artifact discovery/download and GLB/PNG publication with durable duplicate protection and native-asset reuse.
- Added canvas asset discovery and append-by-default Lab input binding with explicit replacement, active-job checks and readback.
- Extended `connectNodes` validation to native non-image handles and idempotent exact connections; retained legacy empty defaults.
- Added bounded artifact-file support to the local writer without new Chrome permissions. Existing flow remains idle/unmodified; extension and writer reload are required.
- Added reusable-prompt guidance and source/UI/writer regression tests. Live canvas mutation validation is deliberately separate from offline coverage.

## 0.2.59 live validation repair — 2026-10-27

- Live Studio rejected direct model inputMount on Labs. setLabInput now uses a selected upstream output/input edge, retaining append/explicit-replace arguments and dry-run defaults. It refuses unselected historical outputs rather than changing source selection.
- Native Lab output/input connections and duplicate-call idempotence passed live. Asset discovery and already-published native asset reuse passed. Existing six nodes remained unchanged; the next Lab was created but not submitted.
- Writer health succeeds, but the first artifact chunk was rejected by the running extension worker. Added an explicit worker build identity to health and a content-bridge readiness marker for diagnosis. Synced source worker and actual writer both support artifact chunks.
- 38 focused tests and 33 public-contract integration tests pass after the repair. Final export/download live validation remains pending extension startup recovery.

