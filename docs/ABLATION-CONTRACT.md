<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# Full-look appearance ablations

Run only in the authorized host Blender or native Lab runtime. These are
diagnostic renders, never native output assets or acceptance evidence by proxy.
The input session is the assembled, textured full-look review. No runtime install,
geometry upload, model export, or native job is performed by this module.

The first renders show obvious ribs, upper black patches, and a profile gap.
Do not equate any numeric test result with visual quality. Separate causes using
the same camera, lights, positions and original source textures:

```python
import full_look_ablation as ab
values = {'right': 1, 'left': 1}  # Use actual runtime controller identifiers.
a = ab.build(session_id, values, 'static-measured-explicit',
             colors='measured', normals='explicit', source_normals='rotated')
ab.render(a['ablation_id'], ['front', 'oblique', 'profile'])
b = ab.build(session_id, values, 'static-uniform-explicit',
             colors='uniform', normals='explicit', source_normals='rotated')
ab.render(b['ablation_id'], ['front', 'oblique', 'profile'])
c = ab.build(session_id, values, 'static-uniform-auto',
             colors='uniform', normals='auto', source_normals='auto')
ab.render(c['ablation_id'], ['front', 'oblique', 'profile'])
```

Compare A to the original shape-key render to test posed custom normals being
interpreted through rest-mesh deformation. Compare B to A to isolate generated
vertex-colour pigment. Compare C to B to isolate explicit normal conventions;
this also changes original source custom normals, so inspect source-face shading
separately. For a narrower follow-up, use `normals='auto'` while retaining
`source_normals='rotated'`.

Every generated diagnostic mesh is rebuilt at its actual posed coordinates with
no shape keys. A report compares those positions to the original evaluated mesh.
The source is copied from its evaluated geometry with original UV and material
layers. All old scenes and rendered files remain intact. Uniform colour is the
median generated linear skin colour and uses the same material/roughness; it is
an ablation, not a proposed accepted flat-colour result. Static explicit normals
are evaluated from the posed geometry, with source-conforming strip normals
kept separate. Auto normals use Blender's own smooth surface normals.

Original-image bytes and existing source material datablocks are never changed.
