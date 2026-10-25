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
