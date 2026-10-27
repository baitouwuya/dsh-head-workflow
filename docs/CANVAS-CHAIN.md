<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- SPDX-FileCopyrightText: 2026 Head Workflow contributors -->

# Canvas chain

The head workflow was reproduced end to end on Tripo Studio canvases. This directory
carries the real recipe from that run, not a design sketch.

## Shape of the chain

Parts are generated separately and only then assembled, so the face can be worked on
without regenerating a whole character:

    reference image -> T-pose -> body (SM) -> clothes (SM, fitted)
                              -> hairless head (SM, fitted) -> wig (SM, fitted)
                              -> rigging -> eyes/blink -> jaw -> expressions
                              -> texture -> export

Every geometry step ran in its own fresh AI 3D Lab node with a clean context, cloned
this repository at tag v0.1.2 (commit d426943), ran the repository tests first, and
reused head_repair/ and research_stages/ modules through an incremental patch. A step
that failed its own handoff check was not passed down the chain.

The measured run: 19 completed steps, 20 nodes, 22 edges, one fresh Lab per geometry
step, no existing project modified.

## Files

- flow-config.json - node parameters, dependencies and every per-step prompt.
- *.prompt.md - the exact prompt handed to each step, one file per step.
- lineage.json - which artifact fed which step.
- status.json, manifest.json - run state and artifact hashes.
- polish-attempt-PLAN.md, polish-attempt-profile.json - the bounded eyelid-collar,
  lash-tracking and faceting polish that was attempted on the frozen head.

## What the polish attempt established

Two builds were submitted and both failed their own geometry safety gates: cheek/chin
faceting worsened, projected inversions remained, and the protected mouth normal
deltas changed. The frozen head therefore stays the accepted face, and the failed
evidence is preserved rather than reported as success.

A future polish needs reliable collar and lash mapping, a smoothing step that
measurably reduces faceting, and strict mouth-normal preservation.

## Scope of the accepted face

The accepted head is a benchmark-based head with repaired eyelids and its original
mouth: 104,909 triangles, 68 joints, 18 morph names, original 8192 basecolor plus iris
images. The mouth keeps its declared 8-degree range; large-gap openings are not
supported. A pale eyelid collar, the original upper lash crease and some cheek/chin
faceting remain visible, and global inherited skin defect visibility is not certified.
