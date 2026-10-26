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
