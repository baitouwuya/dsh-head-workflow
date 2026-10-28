# SPDX-License-Identifier: GPL-3.0-or-later
"""Opt-in adapter for lab_recipes.lid_surface; never edits pipeline profiles."""
import numpy as np
from .geometry import normalize, sample_path
from .fit import bounded_fit, sample_eye


def canvas_frame(eye):
    """+X-forward canvas geometry -> medial/lateral normalized measurement frame."""
    rim = np.asarray(eye['rim_xyz'], dtype=float)
    ends = rim[[np.argmin(rim[:,1]), np.argmax(rim[:,1])]]
    inner = int(np.argmin(np.abs(ends[:,1])))
    a, b = ends[inner], ends[1-inner]
    width = np.linalg.norm(b-a)
    if width < 1e-8:
        raise ValueError('degenerate canvas eye')
    lateral = (b-a)/width
    up = np.array([0.,0.,1.])
    up -= lateral*np.dot(up,lateral)
    up /= np.linalg.norm(up)
    depth = np.cross(lateral,up)
    if depth[0] < 0:
        depth *= -1
    return (a+b)/2, np.stack([lateral,up,depth]), width


def measure_canvas_lids(eye, settings, frame=None, count=65):
    """Read the analytic inner margin from the existing rounded-lid builder.

    Requires cross_section_samples divisible by four so phi=3*pi/2 is sampled.
    Optional lash construction belongs to the caller; this adapter makes no
    claim that a lid shell alone includes lashes.
    """
    from lab_recipes.lid_surface import build
    frame = canvas_frame(eye) if frame is None else frame
    n, m = settings['length_segments'], settings['cross_section_samples']
    if m < 4 or m % 4 or n < 3:
        raise ValueError('need length_segments >=3 and cross sections divisible by four')
    by_lid = []
    for upper in (True, False):
        positions, _ = build(eye, upper, settings)
        indices = np.r_[(n-1)*m, np.arange(n-1)*m+3*m//4, (n-1)*m+1]
        neutral = normalize(positions(0.)[indices], frame)
        if neutral[0,0] > neutral[-1,0]:
            indices = indices[::-1]
            neutral = neutral[::-1]
        by_lid.append([sample_path(normalize(positions(w)[indices], frame),neutral,count)
                       for w in (0.,.25,.5,.75,1.)])
    return np.transpose(np.asarray(by_lid),(1,0,2,3))


def fit_canvas_lids(eye, target_eye, settings, bounds, *, lash_evaluator=None, **solver_options):
    """Fit selected existing shell settings in metres against normalized targets.

    lash_evaluator(settings, weights, u) may return normalized shape (5,65,3).
    Without it only lid margins are fit, and the result explicitly says so.
    Use fitted lash offsets from evaluate_lid to construct/attach a separate band.
    """
    target = sample_eye(target_eye)
    frame = canvas_frame(eye)
    wanted = target['margin'].ravel()
    if lash_evaluator is not None:
        wanted = np.r_[wanted, target['lash'].ravel()*.5**.5]
    def evaluate(parameters):
        candidate = {**settings, **parameters}
        rows = measure_canvas_lids(eye,candidate,frame).ravel()
        if lash_evaluator is not None:
            lash = np.asarray(lash_evaluator(candidate,(0.,.25,.5,.75,1.),np.linspace(0,1,65)))
            if lash.shape != (5,65,3):
                raise ValueError('lash evaluator must return normalized (5,65,3) samples')
            rows = np.r_[rows,lash.ravel()*.5**.5]
        return rows
    result = bounded_fit(evaluate,wanted,{k:settings[k] for k in bounds},bounds,**solver_options)
    result['fitted_features'] = ['lid_margin'] + (['lash_band'] if lash_evaluator is not None else [])
    result['settings'] = {**settings,**result['parameters']}
    result['physical_thickness_measured'] = False
    return result
