<!--
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileCopyrightText: 2026 Head Workflow contributors
-->
# Package verification

This record distinguishes tests of the portable package from historical results of the interactive construction session.

| Check | Observed result |
|---|---|
| Python source parsing | 17 files parsed successfully |
| Configuration tests | 6 passed, including wrong-model hash, duplicate eye side, unsupported jaw, non-finite fit and excessive resolution rejection |
| GLB verifier tests | 4 passed, covering truncated file, valid sparse data, non-finite sparse data and invalid sparse index |
| Fitted-profile input binding | Passed against the separately held original input; input asset is not bundled |
| Portable GLB checker on the delivered head | Passed; 68 bones, 18 morph names, 20 mesh nodes, 1,167,958 finite float values checked including sparse morph values |
| Portable browser renderer | Three.js r180, WebGL2; 37 views rendered and saved |
| Browser deformation checks | 37/37 finite; all 36 non-neutral poses move; eyeballs stationary during blink; exact neutral reset (maximum coordinate difference 0) |
| Browser render-loop time | 3,811.2 ms on the test machine; not a performance guarantee |
| Browser console | 0 warnings, 0 errors during the completed run |
| Browser STOP | Clicked during a fresh load; rendering stopped, controls reset, no completed report or PNG saved |
| Sheet visual review | Inspected full composite; fixed framing, readable labels, no tile collisions |
| Full consolidated Blender run | **Not run: host connector rejected access because its token had expired.** No alternate route was used. |
| Tripo Lab rebuild | Pending operator publication of the repository and an observed Lab execution route |

The tested delivered-head GLB SHA-256 is `a3e51128f8b571a20b59394abf18cd3dec11b41502635e78761afa2b2deddeba`. It is an external test input and is not included in the publication folder. Browser and structural results above test this package's harness against that asset; they do not claim that the consolidated runner has recreated it.

The packaging changes needing Blender regression are documented in WORKFLOW.md. The source stages' earlier success does not close that gap. Before accepting a new build, run the documented command in a fresh Blender process and retain its output manifest, closure/protection audits and browser result.

No Tripo account operation occurred during packaging; credits spent: 0. Before/after balances were not queried. No GitHub credentials were accessed and no repository was published by this tool.
