<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# P1 live instrumentation proof

Run: ../runs/20261021T180042Z/ . Trace: traces/canvas-open-20261021T181452Z.json . Version: 0.1.0. Installed extension ID: lbjmllmbibicamcilbjpghdpebjfihpk.

## Reproduced action

Existing logged-in Chrome, /projects. Panel initially STOPPED with 0 events. Start capture was clicked explicitly. One ordinary UI click opened the existing owned empty dsh-canvas-recon-20261021 canvas. No Send, Continue, Regenerate, Create New Canvas, or export submission during this proof. Export trace JSON stopped capture; its redacted textarea value was written directly to the trace file using the file tool. Native Save picker is implemented but not independently verified.

Capture start 2026-10-21T18:14:41.637Z. Canvas click command started 18:14:44.373Z. Navigation marker 18:14:46.153Z. Export/stop 18:14:52.609Z. These are capture timestamps, not an automation efficiency comparison.

35 events; 0 dropped. 10 fetch request/response pairs with 10 JSON-shape events, 1 XHR pair, 1 navigation, start and stop markers. All 11 responses were HTTP 200; durations 188-537 ms. Application-level error codes were stripped to types, so HTTP status alone is not a claim of application success. Canvas controls and empty state were independently observed on-screen.

## What the trace actually proves

Eight fetch POSTs went to https://msapi.tripo3d.ai/ms/web/api and carried an x-micro-method header. Its value is redacted in v0.1; these calls must not yet be assigned guessed operation names. Request/response schema pairs include:

- f2: empty object -> error, registryVersion, tools array (18), nodeConnections array (19).
- f10: offset/pageSize -> projects array (10) and total.
- f14: projectId -> project with canvasId and metadata fields.
- f18: canvasId -> canvas (canvasId, projectId, revision), nodes [], edges [], nodeRuns []. This matches the displayed empty canvas.
- f20: canvasId -> redacted sensitive field; meaning unknown.
- f25: redacted request field -> messages [].
- f32: canvasId -> runs [].
- f34: redacted field + statuses array (4) -> turns [].

Two other fetch calls observed during the canvas open: GET api.tripo3d.ai/v2/studio/user/profile/payment and POST api.tripo3d.ai/v2/studio/message/new. They are incidental observations; no generic Studio mapping or replay was done. The payment-shaped response includes wallet total_credit as a number type; no payment was submitted.

One site-origin XHR went to a Cloudflare precursor path and returned 200. No human challenge/captcha UI, access denial, solving, or bypass occurred. Background security traffic is recorded as an observation, not a canvas operation. Do not replay it.

0 WebSocket events in this interval. This does not prove the canvas uses no WebSockets. SSE payloads are not parsed by v0.1. No generating run stream, stop, approval, retry, or resume channel was exercised.

## Safety and restoration

All recorded header values and URL query values are redacted; body scalar values are type-only. No credential store read or token export. Trace verification paired all 11 requests/responses.

Separate Kill test: Start then Kill/Stop, normal Back navigation to /projects; count stayed STOPPED 40/400 before and after navigation. Evidence kill-proof.json and 19-kill-stopped-navigation.png.

Disable test: switched OFF only DSH Canvas Observer. Panel count became 0 without page reload. Opened own empty canvas; Add node enabled, Send disabled, credit display 278659. Evidence disable-proof.json and 21-disabled-canvas-usable.png. This establishes the observed navigation path, not every possible site behavior.

Re-enabled extension; clicked its Reload icon; Chrome showed Reloaded. No human help was needed after initial loading. Returned original tab to /projects; observer shows STOPPED 0/400. Temporary extension-management tab closed. No Chrome restart.

Balance before/after: 278659 -> 278659. No generating action or spending approval. No efficiency claim or full Track A completion is made. P2 must recover only explicitly safe operation identifiers from real traffic and distinguish canvas conversation session IDs from authentication secrets; P3 remains unimplemented.
