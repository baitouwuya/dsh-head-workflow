<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

## Unreleased: stationary-blink diagnosis and construction correction

- Reproduce the rejected input's closure failure outside the Lab and distinguish
  the unweighted depth clamp, split lash masks and between-keyframe collapse.
- Correct the semantic diagnosis: predecessor eye labels selected dark lash
  bands and lash labels selected pale collars. Qualify the historical mixed
  probe set and require fresh texture/geometry semantic checks in the guidance.
- Validate simple ordered aperture contours; explicitly construct conservative
  envelopes from measured samples without relabeling them anatomical rims.
- Add static, local swept-triangle bounds from actual stationary eye geometry;
  preserve fixed anchors and avoid point-depth interpolation underestimation.
- Add original-lash component/seam, neutral/near-neutral and continuous LINEAR
  morph checks, with explicit runtime thresholds and no empty-data passes.
- Make the legacy clearance projection weight-dependent; this change alone is
  not a complete closure repair.
- Add a generic head-only Lab prompt and document numerical proof separately
  from native appearance, attachment and export acceptance. Existing tags and
  historical failed evidence remain unchanged.

## v0.1.4

Canvas driver published, and the eyes-and-gaze limit documented from a measured run.

- driver/ - the MV3 extension that operates a Studio canvas over its page-world API, with
  the 0.2.59 additions: `labExport`, `labDownloadArtifact`, `publishLabArtifact`,
  `listCanvasAssets`, `listLabArtifacts`, `setLabInput`. Every mutating action defaults
  to dry-run; results carry what was actually written and never a signed URL.
- driver/tests/ - the offline test suite shipped with the extension.
- docs/CANVAS-DRIVER.md - install and activation steps, the full action surface, and the
  operations that are deliberately still not actions (Lab submission, job monitoring, node
  deletion, panel toggles).
- docs/GAZE-LIMITS.md - the measured failure of an eyes-and-gaze stage on a shallow-socket
  Smart Mesh head: worst aperture coverage 66.12 % over 18 gaze samples, one degenerate iris
  triangle, protected-face movement and reset error both zero, primary model withheld. The
  v0.1.2 recipe covers stationary eyeballs and blink only; no gaze stage exists.
- No model, texture or rig asset is included in this release.

## v0.1.3

Canvas chain published: the recipe that reproduced the head pipeline end to end on
Tripo Studio canvases.

- canvas-chain/ - flow-config.json with every per-step prompt, the exact prompt files,
  lineage, run status and artifact manifest of the measured run (19 steps, 20 nodes,
  22 edges, one fresh Lab per geometry step).
- canvas-chain/polish-attempt-* - the bounded eyelid-collar, lash-tracking and
  faceting polish that was attempted on the frozen head, including the fact that both
  builds failed their own geometry safety gates.
- tools/matched-viewer-baseline.js - matched camera/lighting baseline for before/after
  renders.
- docs/CANVAS-CHAIN.md - how the chain is shaped and what the accepted face does and
  does not certify.
- No model, texture or rig asset is included in this release.

## v0.1.2

Repair side published: the eye/mouth repair modules and the research stages behind them.

- head_repair/ - 14 modules for targeted eye and mouth repair, plus repair.py, host_runner.py, audit-observability-tests.py, test_profile.py and audit-definition-lock-v1.json.
- research_stages/ - 30 standalone geometry stages (closure, fairing, subdivision, portal walls, mouth integration, posed visibility, probe harnesses).
- lab_recipes/lid_surface.py - the eyelid envelope surface recipe used for the cloud-Lab steps.
- docs/REPAIR-PIPELINE.md, docs/RESEARCH-STAGES.md - what each module does.
- No model, texture or rig asset is included in this release.

<!--
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileCopyrightText: 2026 Head Workflow contributors
-->
# Changes

## 0.1.1

- Select BLENDER_EEVEE on Blender 5, falling back to BLENDER_EEVEE_NEXT on Blender 4.2, and reuse the selected engine in the source review scene. Geometry algorithms are unchanged.
- Normalize text to LF and declare checkout line endings so source manifest hashes survive Git checkout.
- Record the clean Blender 5.2 reconstruction and the Blender 4.2 Lab reproduction separately.

Base: public commit fd7b5d504ddd241f5d6980377a1a43df0c384f83. See VERIFICATION.md for completed checks and remaining limits.
