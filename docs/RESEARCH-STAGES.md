<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# Research geometry stages

Standalone stages used for measurement, closure, visibility and probe work. Each module is independent: it takes an object or scene, performs one bounded operation, and reports numbers. Nothing here is required to run the build pipeline.

| module | purpose |
| --- | --- |
| __init__.py | Standalone geometry stages used for measurement and repair experiments. |
| adaptive_refine.py |  |
| boolean_mouth.py |  |
| close_portals.py |  |
| contract_probes.py |  |
| defect_visibility.py |  |
| edge_fair.py |  |
| evaluate_assembly.py |  |
| evaluate_boolean_candidate.py |  |
| flip_repair.py |  |
| fold_relax.py |  |
| full_scene_probes.py |  |
| joint_dihedral.py | Pure NumPy bounded joint dihedral repair; no topology/UV changes. Not an audit. |
| main_shell.py |  |
| mouth_corrective.py |  |
| mouth_integration.py |  |
| mouth_pose_optimizer.py |  |
| native_cap_closure.py | Private SM iris-cap closure with exact seam identity and glint apertures. |
| oral_portal_walls.py |  |
| oral_stage.py | Internal-only structural stage; controlled by assembly-profile.json. |
| patch_mouth.py |  |
| posed_visibility.py |  |
| render_comparison.py |  |
| rounded_lids.py |  |
| scleral_globes.py |  |
| skin_repair.py | SM-source topology surgery. All new caps are internal. No donor outer skin. |
| sm_eye_integration.py | Private direct SM eye assembly, diagnostic and unaccepted. |
| sm_native_cap_closure.py | Private SM iris-cap closure with exact seam identity and glint apertures. |
| sm_vroid_parts.py | Private INTERNAL-ONLY extraction of observed VRoid structural source parts. |
| stable_dihedral.py | Optional altitude-bounded feasible-descent dihedral repair. Original solver unchanged. |
| topology_core.py | Generic topology/geometry observations. No Blender or model data dependency. |
