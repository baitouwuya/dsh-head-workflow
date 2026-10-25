<!--
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileCopyrightText: 2026 Head Workflow contributors
-->
# Verified reconstruction and limits

## Source binding

Base public repository: https://github.com/baitouwuya/dsh-head-workflow, commit fd7b5d504ddd241f5d6980377a1a43df0c384f83. Version 0.1.1 adds the renderer-only compatibility patch in docs/blender-4-5-compat.patch, LF normalization and updated evidence documentation. Geometry algorithms, profile and acceptance thresholds are unchanged.

The executed head_helpers.py SHA-256 is c89beb05b164df9b3cbe7307c37dfc0cbde9a0b264a74a6eaedbd97f89327f45; it matches the file independently executed in native Tripo Lab. Source and model assets remain separate.

## Observed runs

| Check | Result |
|---|---|
| Unmodified public base, fresh Blender 5.2.0 LTS | Exit 0; all declared build checks passed |
| Unmodified public base, native Lab Blender 4.2.9 LTS | Failed before reconstruction: BLENDER_EEVEE is unavailable |
| Patched source, fresh Blender 5.2.0 LTS | Exit 0; all declared build checks passed |
| Patched source, native Lab Blender 4.2.9 LTS | Exit 0; BLENDER_EEVEE_NEXT selected; all declared build checks passed |
| Dense full-blink probes | 7,021 per eye; zero failures, including empty rays |
| Mouth probes | 775; zero back-head/empty hits |
| Closed eyeballs | Zero boundary/nonmanifold edges; repeated after clean GLB import |
| Protected hair/star | 25,895 vertices at zero displacement; 25,465 faces unchanged |
| Lab native poses | 37 states; finite, moving controls, stationary eyes during blink, exact neutral reset |
| Independent browser test of actual Lab GLB | 37 views; all finite; all 36 non-neutral states move; eyeballs stationary during blink; resetMax 0 |
| Browser runtime | Three.js r180, WebGL2; 2998.6 ms for the test loop on the verification machine |
| Browser console | Zero warnings and errors |
| Export structure | Head: 20 mesh nodes, 68 joints, 18 morph names; integrated:21 mesh nodes, 68 joints |
| Finite float data checked locally | Head 1,190,140; integrated 2,655,763, including sparse morph values |
| Unit tests | Six configuration tests and four GLB-verifier tests passed |
| Syntax | 17 Python files parsed |

The independently tested Lab head SHA-256 is 4069784c1db2963e59cb3d9ef94a266e1c6e8c40271d08f2b93f7076e1c5c10a; the integrated GLB is 365e64028e383408691360d51665f7618cf5d78712de81a3e3fd2f129dd23461. Neither model is included in this source package.

One native render tool returned exit 143 even though all 37 images and result rows were written and its log reached normal completion; its cause is unknown. A separate fresh-process numeric verification passed all 37 states and agreed with the rendered displacement data. The subsequent independent WebGL2 run also passed. The reconstruction process itself exited0. These distinctions are retained rather than describing every process as successful.

## Visual acceptance boundary

Reconstruction and declared controls are reproduced. This is not a polished close-up facial asset. Full opening exposes angular lip-corner strips and visible edges of the overlapping mouth insert. Close views also show lid/lash creasing. The oral lining is capped but not welded to every source sheet. Zero frontal probe failures does not certify global watertightness, arbitrary mixtures, all-angle collisions, extreme gaze or other engines.

The Lab performed matched neutral comparisons, both obliques/profile, mouth close-ups, integrated-avatar checks, original bone hierarchy and texture audits. Maximum original-bone rest-matrix component difference after export/reimport was5.15580177e-06. Four-influence normalization is documented, not called exact original-weight preservation.

## Canvas and accounting

The original-source head and integrated-avatar models were saved as new private outputs of the authorized existing dsh Lab node. Other 67 nodes, all 103 edges and other 15 project records were unchanged. Only the authorized Lab node outputs and target-project metadata changed. Two Lab attempts each read 277,774 credits before and after: total observed debit 0. No GitHub push, account/security change, donor-data use or public model upload occurred.

The original input SHA-256 remained unchanged; host Blender retained its 71 existing objects and active scene. Source publication of this updated folder is a separate operator action.

Studio's native saved-head preview returned an unknown server error after delivery. The saved asset records were READY and the downloaded GLB passed independent local WebGL2 tests. Native preview success is not claimed; the cause remains unknown.
