<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# Native renderer control contract

`tools/native_render_verification.py` runs rendering only inside the Lab's supplied
Blender. It imports `bpy` and `mathutils` lazily in its native entry point. Its pure
request/control functions can be tested with ordinary Python and fake key blocks;
those tests neither import nor execute Blender.

The runtime `controller` maps each measured blink-control name to a nonempty list
of `{value, name}` morph knots. Every raw value must be a finite numeric value in
`(0, 1]`, excluding booleans and numeric strings. Zero is the implicit neutral
basis and is not a named knot. Weights must be unique and reach exactly one. Names
must be nonempty strings and must not be reused by another knot or control.
Already valid knots may arrive unordered; sorting happens only after all raw
entries pass validation. Negative, zero and NaN entries are never filtered away.

Requested values must be finite numeric values in `[0, 1]` and refer only to
configured controls. Omitted configured controls are set to zero. The renderer
resets and sets only the morph names listed in this mapping. Existing jaw,
expression and other unrelated morph values stay at their imported values across
all blink states. The reference basis is never a controllable blink morph.

The renderer plans all assignments before making any changes. A mesh participating
in a requested nonzero control must contain its complete knot mapping. Another
mesh with the missing knot cannot hide that incomplete mapping. A requested
nonzero control must resolve on at least one mesh. Source models without candidate
blink knots may still render their neutral state without changing unrelated keys.

Importing for inspection suspends imported animation evaluation to keep matched
views deterministic; this does not reset unrelated shape-key values. The script
does not export a model or alter the sealed input files. Per-state control audits
record configured assignments and participating meshes. Actual appearance,
geometry and payload checks remain native handoff requirements; a successful
control assignment is not a visual-quality certificate.
