<!--
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileCopyrightText: 2026 Head Workflow contributors
-->

# Canvas driver for Tripo Studio

The `driver/` directory is the MV3 browser extension used to operate a Tripo Studio
project canvas from outside the UI: a page-world API (`window.__dshShortcut`) plus a
popup with one button per action. It is the transport the Lab chain uses to create,
connect, submit, monitor, export and publish nodes without clicking.

## Install

1. Load the directory as an unpacked extension in the guest Chrome profile.
2. Enable it, then use the extension's own **Reload** control, then reopen the Studio
   canvas. Reloading this extension is an operator step; a page-level reload is not enough,
   because the content scripts are injected from disk at document start.
3. Confirm the page-world API answers `status` before submitting anything.

Paths used by the runtime are written as `<EXT_DIR>`, `<DSH_ROOT>` and `<SHARE_ROOT>` in
this package; bind them to the host layout of your own environment.

## Action surface

Base actions (0.2.5x): `capture`, `read`, `run`, `export`, `stop`, `createCanvas`,
`uploadAsset`, `createNode`, `connectNodes`, `saveCanvas`, `generate`, `waitTask`,
`autoLayout`, `selectNode`, `labExportDialog`.

Added in 0.2.59, closing the gap where every Lab handoff had to be clicked by hand:

| Action | Purpose |
| --- | --- |
| `labExport` | press the native Lab export control, choose format/resolution, and download the produced file |
| `labDownloadArtifact` | download the original Lab artifact, keeping the pre-conversion bytes distinguishable from a Studio-exported GLB |
| `publishLabArtifact` | publish a Lab artifact back onto the canvas as an asset and select it on its node |
| `listCanvasAssets` | enumerate canvas assets with their native ids |
| `listLabArtifacts` | enumerate Lab jobs and their artifacts |
| `setLabInput` | bind an existing canvas asset to a Lab input socket |

Every mutating action defaults to dry-run. Results carry before/after credit balances,
the ids and hashes of what was actually written, and never a signed URL.

## What is still not an action

- Submitting an AI 3D Lab conversation itself (the Lab turn is native UI).
- Lab job monitoring beyond the page's own card state.
- Deleting, renaming or duplicating nodes.
- Panel toggles and zoom.

## Source-only PNG carrier

When a Lab cannot fetch a source archive itself, the documented fallback is a PNG whose
metadata carries `dsh.recipe.zip.base64` and `dsh.recipe.zip.sha256` with an explicit
source-only label; the Lab verifies the hash before extracting. Never put secrets, VRoid
data or model binaries into that carrier. Prefer cloning the public repository; the carrier
is only for private or unreachable sources.

## Test status

`node --test driver/tests/*.test.cjs` runs 15 files. Twelve pass. Three legacy files -
`observer.test.cjs`, `representative-recovery.test.cjs`, `ui.test.cjs` - fail against
0.2.59 with the same error they produce against the live extension source, and they fail
identically there: they target an earlier observer/UI surface. They are shipped unchanged
rather than deleted, so the failure stays visible.

## Evidence

`driver/evidence/report.json` and `driver/evidence/tests.json` record the 0.2.59
implementation result and its offline test totals as reported by the implementing Lab.
The live-validation transcript is not part of this package.
