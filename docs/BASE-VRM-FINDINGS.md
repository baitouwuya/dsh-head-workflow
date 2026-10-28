# Operator VRM: native blink and PD compatibility

The operator's new VRM is a usable **native blink reference**, but the installed
Parametric Deformation add-on does **not directly drive identity shaping on its
imported face**. The preferred lid-motion target is now
`profiles/reference/base-vrm.json`, with a fitted model in `base-vrm-fit.json`.
F00/M00 remain available for comparisons and PD-template parameter fitting.
Nothing automatically changes the canvas pipeline's selected reference.

The input remains private even though the operator authorized broad use.
Published data contains only derived normalized coefficients, measurements,
hashes, and verification metadata. No reference mesh, vertex array, topology,
UVs, textures, materials, or VRM is included.

## Native blink result

This VRM 1.0 file binds the `blink` preset to `Fcl_EYE_Close` at weight one,
with continuous interpolation. The reader resolves the preset binding rather
than assuming an expression index or using the similar-looking Joy target.
The installed `bl_ext.user_default.vrm` importer confirms the preset and all
five weights: `0, .25, .5, .75, 1`.

Blender's importer reorders the face vertices. Comparing the same numeric
indices is invalid. The host check matches neutral geometry, allowing coincident
seam vertices, then checks the blink delta. Maximum neutral discrepancy is
`0.0004581` eye widths; maximum morph-delta discrepancy is `9.33e-8` eye widths.
No correspondence or source coordinates are published.

The following values measure the private source polylines **before curve
reduction**, at 129 lateral cross-sections, excluding `0.02` eye widths at each
canthus. Values are for the positive-X side; the other side agrees closely.

| Full-weight measurement, eye-width units | Native blink | F00 Eye.Joy |
|---|---:|---:|
| RMS signed-height gap magnitude | 0.0133300 | 0.0934434 |
| Maximum positive opening | 0.0022028 | 0 |
| Maximum projected overlap | 0.0225926 | 0.1015605 |
| Maximum absolute depth difference | 0.0305044 | 0.0344126 |

The native blink is about seven times better on the RMS closure measure and
has substantially less overlap. It is a better reference for the motion and
closed shape, **not a certified watertight or collision-free eyelid**. The
reference still has small gaps, overlap, and depth separation.

Do not synthesize bilateral blink by summing `blinkLeft` and `blinkRight`:
their sum differs from the native bilateral morph by as much as `0.1812` eye
widths over the face. The side presets also have some opposite-side motion.
The dataset evaluates the actual bilateral `blink` binding directly at every
weight. The evidence file records the side-preset measurements separately.

## Lash/band and thickness limits

The new face has an `Eyeline` geometric sheet and no separate `Eyelash` slot.
The profile therefore labels the eyeline centreline as a **lash-band anchor
proxy**. It is not a measurement of visible, alpha-cutout lashes. Native band
extensions and bends are preserved in the piecewise coefficients.

As with the earlier packs, the skin is an open sheet. Physical lid thickness
and anatomical socket-floor depth remain null, with explicitly named collar
edge-length and recess proxies. The reference cannot supply a physical shell
thickness; solid construction needs a caller-selected value.

Maximum source-to-profile reduction errors are `0.00721` eye widths for margins
and `0.00639` for the band. The fitted model adds RMS error about `0.001163` and
maximum error `0.00538`. These approximation errors are larger than the small
remaining source opening; do not use the reduced coefficients alone as proof
of an exact seal.

## PD face-shaping experiment

The live Blender 5.2 experiment imported the VRM into a temporary scene, made
its face the active selected object, loaded the supplied F00 template pack,
and evaluated three PD controls separately at `0.5`:

| Control | PD template maximum displacement, normalized by reference eye width | Imported VRM displacement |
|---|---:|---:|
| Eye Size Y | 0.126501 | 0 |
| Outer Eye Slant (Y) | 0.055668 | 0 |
| Move Upper Eyelid Down | 0.053630 | 0 |

The operations succeeded, but updated the separate `PD_Avatar` template object.
The selected imported face did not change, either in base coordinates or in
evaluated world coordinates after its modifiers. Inspection of the installed add-on's
update path confirms that it uses its pack adapter and named PD output objects,
not the currently selected arbitrary mesh.

There are also two concrete obstacles to an immediate transfer:

- The exported face has 3,989 vertices; the template face has 4,169. Direct
  index-based displacement transfer is invalid.
- `Eye Size Y` changes 36 template joint transforms; 34 of those joints are
  absent from the exported face skin. The two remaining eye bones cannot
  reproduce the template's complete facial adjustment system.

Driving this VRM with PD would require a new identity-deformation adapter or
an explicitly validated surface/bone transfer. This task tests compatibility;
it does not introduce an unverified nearest-vertex deformation transfer. The
native blink can already drive the reference fitter independently of that work.

## Reproduce

With host Blender running, the VRM extension and PD extension installed, PD
idle with no pack loaded, no existing `PD_Avatar` objects, and Object mode:

```powershell
& tools/run-vrm-reference.ps1 -VrmPath 'C:\private\base.vrm' -OutputDirectory profiles/reference
```

`VrmPath` is a **host** path. The wrapper executes host Python only through
`C:\ProgramData\dsh\hostcap\blender-call.ps1 -File <script.py>`.
The default F00 pack directory is `D:\Staging\PD\vroid`; override
`-PackDirectory` if needed. With no `-AddonDirectory`, the runner uses the
installed, already-registered PD package. It refuses to replace an active PD
session. The importer test currently requires a single full-weight blink
binding, as present in this input.

The experiment creates temporary imported and PD objects, runs real operators,
then removes only newly created datablocks. It restores the original scene,
selection, active object, PD state and dynamic properties. The evidence confirms
that original datablock sets and selection are restored. Textures remain in
memory during the import test and are never extracted or saved to disk.

The numeric reader supports embedded GLB buffers, strided/dense/sparse accessors,
and weighted VRM 1.0 morph bindings. This adapter deliberately rejects binary
blink, multiple expression nodes, nonidentity mesh world transforms, nonzero
default morph weights, and split primitive position/morph streams. These need
explicit adapters; unsupported layouts are not silently treated as this export.

To consume the new target without the private file or Blender:

```sh
python tools/fit-reference.py profiles/reference/base-vrm.json --output build/base-vrm-fit.json
python -m unittest discover -s tests -v
node --test tests/verify-glb.test.cjs
```

All 35 Python tests pass, including 11 new VRM tests using synthetic GLB fixtures
and normalized outputs only. The original four GLB Node tests pass. No driver
or canvas implementation is changed; its six previously recorded baseline
failures are outside this addition. Detailed live numbers are in
`profiles/reference/base-vrm-verification.json`.
