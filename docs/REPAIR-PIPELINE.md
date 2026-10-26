<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# Head repair modules

Targeted repair of eye and mouth anatomy on an already-rigged head asset. These modules assume a source head with joints and morph targets and operate on a copy. They are the repair side of the workflow; the build side lives in head_workflow/.

| module | purpose |
| --- | --- |
| __init__.py | Head repair modules: targeted eye/mouth anatomy repair on a rigged head asset. |
| appearance.py |  |
| audit.py | Acceptance is entirely profile-driven. Missing evidence never passes. |
| config.py | Resolved inputs and immutable per-run settings; no Blender dependency. |
| controls.py |  |
| eye_plan.py |  |
| eyes.py |  |
| fairing.py | Positive-weight harmonic depth solve with a fixed rim and eyeball obstacle. |
| legacy.py | Remove obsolete eye planes on the copy; retain every protected hair face. |
| measure.py | Raw observations. Acceptance limits are deliberately absent. |
| mouth.py |  |
| pipeline.py |  |
| render.py |  |
| semantic.py |  |
| subdivision.py | Localized Loop refinement; original vertex indices and control deltas survive. |
