# Loading a VRM as a Parametric Deformation pack

**Yes: the geometry, morph targets and linear skinning can be converted into a
PD pack and driven by a custom adapter. A VRM file is not itself a PD pack,
and the mapping is not a one-to-one preservation of the complete VRM model.**

**The add-on's own export stage is an empty interface stub. It cannot emit a
VRM.** `export/__init__.py` contains only a docstring saying implementation is
deferred. The host proof checks its AST and finds zero executable statements.
`TemplateAdapter.export_map()` supplies an empty mapping by default; returning
a populated mapping from a driver does not create an exporter. A separate VRM
export implementation, such as the installed VRM Blender extension, is still
required for an actual `.vrm` output.

The implementation in this branch supplies the missing import conversion and
evaluation adapter. It does not modify PD or pretend its exporter exists.

## What the installed code actually supports

This analysis inspected the installed Parametric Deformation 0.1.0 package in
host Blender 5.2. The exact hashes of the inspected modules are recorded in
[`evidence/vrm-pd-pack-proof.json`](evidence/vrm-pd-pack-proof.json).

| PD field | VRM/glTF source | Mapping and missing work |
|---|---|---|
| `meshes/*.mesh.json` | Mesh-node instances, primitives, attributes and indices | A glTF mesh can have several primitives and several node instances. Accessors can be shared, sparse or strided. The converter decodes them, creates one descriptor per active node/primitive, compacts referenced vertices, and remaps faces. There is no intrinsic one-descriptor/one-VRM-mesh correspondence. |
| `bs/linear/*.bs.json` | Primitive morph `POSITION` deltas | Numeric linear bases are directly representable. Their order, default weights and primitive/node association must be retained. Expression names are not morph weights: one VRM expression may bind multiple morphs. Normal/tangent morphs are not returned by PD's `MeshResult` and this converter does not preserve them. |
| `lbs/skeleton.json` | Node graph, local matrix or TRS, skin joint references | The converter topologically orders the graph and saves exact local 4×4 matrices plus parent indices. Intermediate non-joint nodes matter to FK. A skin's joint palette is not the entire node graph. Humanoid roles are separate VRM metadata. |
| Per-mesh `bones`, `indices`, `weights`, `bindposes` | `skin.joints`, `JOINTS_0`, `WEIGHTS_0`, `inverseBindMatrices` | These have a close numeric correspondence to the existing VRoid adapter's per-mesh layout. Palette indices must be remapped to the global skeleton; inverse bind matrices are column-major in glTF. The stock generic adapter instead expects dense joint-by-vertex `lbs/weights.npz` and a simpler joints/rotation model. |
| `params.json` | Raw morph controls and VRM expression definitions | A useful UI schema must be synthesized. Raw morphs, semantic expressions, defaults, ranges and mixing are different layers. Exported VRM does not contain the original VRoid identity sliders, measured `runtime_basis.json`, removed adjustment joints, or corrective rules. Those cannot be recovered by renaming fields. |
| `export_map.json` | `VRMC_vrm.humanoid` and expression bindings, or VRM 0 equivalents | Useful as semantic correspondence metadata. `load_pack()` reads it, but it is not an exporter or a complete VRM document. License/meta, first-person, look-at, spring-bone, constraint and rendering behavior require separate handling. |

Additional implementation gaps are visible in the installed code:

- `core/config.py::load_pack` reads JSON files and referenced arrays. It does
  not parse a `.vrm`/GLB. Validation is relatively shallow; it does not establish
  that all array shapes or references are coherent.
- `core/generic.py::GenericAdapter` loads only the first mesh descriptor and
  returns one mesh. It passes through matching direct linear weights. It does
  not implement VRM expression groups, node instances or full glTF skinning.
  It looks for `uvs`, while the existing per-mesh VRoid layout uses `uv`.
- `tools/__init__.py::load_driver` imports `pack/py/driver.py` and discovers a
  `TemplateAdapter` subclass. That is the supported extension point used here.
- `ui/panels.py::_prepare_mesh_data` already reads per-mesh bone palettes,
  indices and weights. `_ensure_vertex_groups` handles only four influences.
- `_keep_bone` is VRoid-specific: it retains `Root`, `J_Sec_*`, certain eye
  bones and `J_Bip_*` except end markers. An arbitrary VRM can therefore be
  numerically evaluable by the driver while its interactive PD rig loses bones.
  This converter preserves names; it does not disguise that UI limitation by
  renaming every skeleton node to look like a VRoid bone.
- The viewport rebuilds/recalculates mesh shading. Correct positional motion
  does not establish material, normal or visual equivalence to the source VRM.

## Converter and driver

Files:

- `head_workflow/pd_pack/convert.py`: conversion and pack writing.
- `head_workflow/pd_pack/gltf.py`: embedded GLB/accessor reader, also shared by
  the earlier normalized-reference extractor.
- `head_workflow/pd_pack/runtime.py`: portable NumPy FK, morph and skin evaluator.
- `head_workflow/pd_pack/driver.py`: the real PD `TemplateAdapter` subclass.
- `tools/vrm-to-pd-pack.py`: command-line conversion.
- `tools/test-vrm-pd-pack.ps1` and `tools/pd_pack_host_check.py`: live host proof.
- `tests/test_pd_pack.py`: synthetic-only regression tests.

The generated pack contains `manifest.json`, `params.json`, per-primitive mesh
descriptors, linear basis descriptors, `lbs/skeleton.json`, `export_map.json`,
private NumPy arrays, and a self-contained `py/driver.py` + `py/runtime.py`.
No runtime import of this repository is needed after conversion.

Coordinates remain in glTF mesh-local/node space in the pack. For skinning,
the driver evaluates world node transforms and applies:

```text
p_blender = C * sum_j(weight_j * world_joint_j * inverse_bind_j
                    * (base_position + sum_k(morph_weight_k * morph_delta_k)))
```

`C` maps glTF `(x,y,z)` to Blender `(x,-z,y)`. For a skinned mesh, the mesh-node
world transform cancels between local skinning and final world placement; it
must not be applied a second time. Unskinned instances use their mesh-node
world matrix. Raw node matrices, including nonuniform scale, remain intact.
`pose.rotations` accepts one local rotation vector in radians per packed node,
post-multiplied onto its rest matrix; `pose.translation` is in glTF world axes.

The driver exposes raw controls such as `morph_n59_013` and expression controls
such as `vrm_blink`. VRM 1 bindings address nodes; VRM 0 bindings address meshes
and use percentage weights, which are converted to fractions. VRM expressions
are accumulated on top of the explicitly exposed raw/default morph values.
For standard VRM expression-only operation, leave the raw controls at defaults.

The expression mixer handles continuous and binary weights, procedural
blink/mouth/look overrides, and their binary interactions. It follows the
[VRM expression specification](https://github.com/vrm-c/vrm-specification/blob/master/specification/VRMC_vrm-1.0/expressions.md):
binary activation is strictly greater than 0.5; binary output controls overrides;
an overridden binary expression is fully suppressed by any attenuation. A
procedural expression does not override its own group. Material-changing
expressions are rejected, rather than silently becoming geometry-only controls.

## Deliberate limits

This is a geometry/morph/skin converter, not a lossless VRM round-trip converter.
It supports embedded GLB, dense/strided/sparse accessors, triangle primitives,
multiple primitive streams and mesh instances, nonidentity node transforms,
four-influence skinning, default morph weights, and VRM 0/1 morph bindings.
The output directory must be new; conversion never overwrites a pack.

It rejects compressed geometry requiring Draco/Meshopt decoding, non-triangle
primitives, malformed data, more than four skin influences, and expressions
that modify materials or texture transforms. It omits materials/images,
normal/tangent streams, animation playback, spring/constraint simulation,
automatic gaze, first-person and VRM permission/rendering metadata. The manifest
records these losses. Runtime humanoid export and full VRM serialization are
not implemented. Identity-shaping controls must be authored separately.

Converted arrays contain private source geometry. Keep the pack outside the
repository or under ignored `private-packs/`. Each generated pack also contains
a `*` `.gitignore`. No converted arrays or private pack are published here.

## Reproduction and live evidence

Ordinary conversion, with Python and NumPy:

```sh
python tools/vrm-to-pd-pack.py private-inputs/base.vrm --output private-packs/operator-base
```

In this VM, source and pack paths are **host paths**. Host execution is routed
only through the required `blender-call.ps1 -File` bridge:

```powershell
& tools/test-vrm-pd-pack.ps1 -VrmPath 'C:\private\base.vrm' `
  -PrivatePackDirectory 'D:\Staging\PD\fresh-private-converted-pack' `
  -ReportPath 'docs/evidence/vrm-pd-pack-proof.json'
```

The operator's actual `base.vrm` produced 9 primitive descriptors, 63 skeleton
transform nodes, 57 raw morph controls, 14 expression controls and 54 humanoid
role mappings. The real `validate_pack()` returned no issues; the real loader
instantiated `VRMAdapter`.

At blink weights `0, .25, .5, .75, 1`, the adapter was compared with an independent
direct evaluation of the source VRM's morph binding and skin matrices using
Blender `mathutils` for the node transforms. Maximum positional discrepancy was
`1.775e-7` of avatar height; full blink moved 997 compacted primitive vertices.
The real `bpy.ops.pd.load_pack` and `bpy.ops.pd.evaluate` were then driven through
the generated `vrm_blink` slider. Every written viewport mesh matched the driver
result exactly at all five weights. Original scene datablock sets were restored.

The numerical proof is version-bound by source/add-on hashes and contains no
reference arrays. It establishes this operator file's PD morph/skin evaluation,
not arbitrary-VRM rendering equivalence, recovered identity sliders, or export.

```sh
python -m unittest discover -s tests -v
node --test tests/verify-glb.test.cjs
```

The 45 Python tests pass, including 10 new converter/runtime tests. The four
original GLB Node tests pass. Previously recorded driver-suite failures are
unrelated and no canvas driver code is changed.
