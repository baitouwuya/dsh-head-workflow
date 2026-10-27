<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# Native construction, sealing and own-file motion verification

These helpers run only in the native Lab's provided Blender. They do not install
a runtime, submit a job, upload geometry or publish an asset. Host precheck mode
is rejected before Blender is imported. A host render or array cache never serves
as the native pipeline artifact.

The Lab first constructs its arrays from its actual incoming model using the
runtime-pinned repository. It assembles those arrays with `full_look_review`, using
`mode: native_stage_build`. Add `native_build_provenance` with the actual
`input_artifact_id`, checked-out `repository_commit` and native
`construction_report_path`. Add `native_source_render_spec` containing the native
source file `path` and its measured `world_to_review` matrix. These are runtime
values, not a fixed artifact, filename, model version or commit embedded in stage
guidance.

```python
import json
from pathlib import Path
import native_stage_export
import native_cycle_verification

sealed = native_stage_export.export_native_session(
    native_session_id, native_output_directory)
request = native_stage_export.cycle_verification_request(
    native_session_id, sealed['glb'], native_review_directory)
request_path = Path(native_review_directory).parent / 'native-cycle-request.json'
request_path.write_text(json.dumps(request, indent=2))
review = native_cycle_verification.verify_native_cycles(request_path)
```

The exporter filters available Blender RNA options and requires essential GLB,
skin and morph support. It retains original mesh attributes, source morphs and
ancestor/armature/constraint dependencies, including bone names. Arbitrary source
object drivers require an explicit adapter and are not silently certified. The
currently measured source is unrigged. The editable BLEND contains the native
scene and its dependencies, controller and provenance. Source animation actions
may remain editable dependencies; unrelated animation export is not certified.

Original encoded image hashes must still occur among the GLB's embedded images.
An image change stops sealing and retains the raw export for diagnosis. The pure
GLB postprocessor appends independent and bilateral blink clips from exported
`targetNames` and the actual runtime knot mapping. It preserves node-specific
unrelated rest weights, preexisting animation records, all original BIN bytes and
embedded images. Every exported mesh has a stable animation-binding extra so the
verifier can map imported mesh targets without relying on Blender's renaming.

The verifier creates separate scenes without a factory reset. It imports the
actual sealed GLB, records target names and imported Action presence, and decodes
the actual serialized weight channels. Those decoded weights drive the imported
morph targets at original and between-key sample times. This is direct sealed
clip evaluation, **not Blender Action playback**. The distinction is recorded in
the report. It renders independent and bilateral close/reopen sequences from all
configured front, oblique and profile views; the original source neutral uses the
same camera, lights, renderer and color transform. VSE encodes actual PNGs into
MP4 with explicit strip duration, Standard view transform and Blender-version
compatible VIDEO media selection. Input and sealed GLB hashes are checked before
and after verification.

Source normals remain their original neutral local loop normals. Generated
neutral normals are set once and Blender evaluates shape-key deformation.
Writing posed normals back onto the Basis each frame is forbidden: host ablations
reproduced severe false pleating from that double compensation. Native reimport
renders must still establish the exported shading quality.

Sealing and completed renders do not imply visual acceptance. Review the Lab's
own motion and its remaining appearance/geometry limitations. Only then publish
and select its own sealed GLB as the canvas artifact, retaining failed evidence.
