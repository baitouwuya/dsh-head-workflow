# SPDX-License-Identifier: GPL-3.0-or-later
"""NumPy-only profile regression and bounded fitting for PD/custom lid builders."""
import numpy as np
from .geometry import curve_points, encode_curve, encode_piecewise, anchor_frames


def validate(profile):
    if profile.get('schema_version') != 1 or profile.get('blink_weights') != [0., .25, .5, .75, 1.]:
        raise ValueError('unsupported reference schema or blink grid')
    if profile.get('units') != 'neutral canthus distance = 1':
        raise ValueError('targets must use neutral eye-width units')
    if set(profile.get('eyes', {})) != {'positive_x', 'negative_x'}:
        raise ValueError('both canonical eye sides are required')

    def check_curve(c):
        a = np.asarray(c.get('coefficients'), dtype=float)
        if c.get('basis') == 'piecewise_chebyshev':
            breaks = np.asarray(c.get('breaks'),dtype=float)
            if a.shape != (8,5,3) or breaks.shape != (9,) or not np.allclose(breaks,np.linspace(0,1,9)) or not np.isfinite(a).all():
                raise ValueError('invalid piecewise curve')
            for left,right in zip(a,a[1:]):
                if not np.allclose(left.sum(0),np.array([(-1)**j for j in range(5)])@right,atol=2e-6):
                    raise ValueError('discontinuous piecewise curve')
            return a
        if c.get('basis') != 'chebyshev' or a.ndim != 2 or a.shape[1] != 3 or not 3 <= a.shape[0] <= 17 or not np.isfinite(a).all():
            raise ValueError('invalid normalized curve coefficients')
        return a

    for eye in profile['eyes'].values():
        if len(eye['lid_margin']) != 5 or len(eye['lash_band']['samples']) != 5:
            raise ValueError('five margin and lash samples required')
        for row in [eye['aperture']] + eye['lid_margin']:
            for key in ('upper', 'lower'):
                check_curve(row[key])
                if row[key]['basis'] != 'chebyshev':
                    raise ValueError('lid margin requires a single Chebyshev curve')
            ends = [curve_points(row[k], [0., 1.]) for k in ('upper', 'lower')]
            if np.max(np.abs(ends[0] - ends[1])) > 2e-5:
                raise ValueError('upper/lower canthi disagree')
        for key in ('upper', 'lower'):
            if not np.allclose(curve_points(eye['aperture'][key], np.linspace(0,1,33)),
                               curve_points(eye['lid_margin'][0][key], np.linspace(0,1,33)), atol=2e-6):
                raise ValueError('aperture must equal neutral lid margin')
        endpoints = curve_points(eye['aperture']['upper'], [0., 1.])
        if not np.allclose(endpoints, [[-.5,0,0],[.5,0,0]], atol=2e-5):
            raise ValueError('invalid neutral normalization')
        for sample in eye['lash_band']['samples']:
            check_curve(sample['centreline'])
            check_curve(sample['anchor_offsets'])
        u = np.asarray(eye['lash_band']['anchor_u'])
        if u.shape != (65,) or not np.isfinite(u).all() or not np.allclose(u, np.linspace(0,1,65)):
            raise ValueError('unsupported lash anchor correspondence')
        for stats in (eye['socket_depth']['statistics'], eye['lid_thickness']['collar_edge_length_proxy']):
            if set(stats) != {'min','median','mean','p95','max'} or not np.isfinite(list(stats.values())).all():
                raise ValueError('invalid statistics')
            if not stats['min'] <= stats['median'] <= stats['p95'] <= stats['max'] or not stats['min'] <= stats['mean'] <= stats['max']:
                raise ValueError('unordered statistics')
    return profile


def sample_eye(eye, count=65):
    u = np.linspace(0, 1, count)
    return {'margin': np.array([[curve_points(m[k], u) for k in ('upper', 'lower')] for m in eye['lid_margin']]),
            'lash': np.array([curve_points(s['centreline'], u) for s in eye['lash_band']['samples']])}


def target_vector(profile, count=33, lash_weight=.5, socket_weight=1.):
    """Geometry-only loss: include all five poses, both sides, margin and lash."""
    validate(profile)
    if not np.isfinite([lash_weight,socket_weight]).all() or min(lash_weight,socket_weight) < 0:
        raise ValueError('invalid feature weight')
    if not isinstance(count,int) or count < 3:
        raise ValueError('at least three samples required')
    rows = []
    for side in ('positive_x', 'negative_x'):
        eye = profile['eyes'][side]
        samples = sample_eye(eye, count)
        rows.extend([samples['margin'].ravel(), samples['lash'].ravel() * np.sqrt(lash_weight)])
        rows.append(np.array([eye['socket_depth']['statistics'][k] for k in ('mean','median','p95')])*np.sqrt(socket_weight))
    return np.concatenate(rows)


def bounded_fit(evaluate, target, initial, bounds, max_iterations=30, tolerance=1e-7):
    """Damped finite-difference least squares in unit parameter ranges.

    evaluate(dict) returns a fixed-length measurement vector. Bounds are never
    exceeded. Reports convergence separately from residual acceptance; a stalled
    solution or a low-dimensional model need not reproduce its target.
    """
    names = list(initial)
    if not names or set(names) != set(bounds):
        raise ValueError('initial values and bounds must have the same nonempty keys')
    lo, hi = np.array([bounds[n] for n in names], dtype=float).T
    x = np.array([initial[n] for n in names], dtype=float)
    target = np.asarray(target, dtype=float).ravel()
    if not target.size or not np.isfinite(target).all() or not np.isfinite([lo,hi,x]).all() or np.any(hi <= lo) or np.any(x < lo) or np.any(x > hi):
        raise ValueError('nonfinite target or invalid parameter bounds/initial values')
    if max_iterations < 1 or tolerance <= 0:
        raise ValueError('invalid solver limits')
    span = hi-lo
    z = (x-lo)/span
    calls = 0

    def residual(z):
        nonlocal calls
        calls += 1
        value = np.asarray(evaluate(dict(zip(names, lo+span*z))), dtype=float).ravel()
        if value.shape != target.shape or not np.isfinite(value).all():
            raise ValueError('evaluator returned wrong shape or nonfinite measurements')
        return value-target

    r = residual(z)
    history = [float(np.sqrt(np.mean(r*r)))]
    damping, status, rank = 1e-4, 'iteration_limit', 0
    for iteration in range(max_iterations):
        if history[-1] <= tolerance:
            status = 'residual_tolerance'
            break
        columns = []
        for i in range(len(z)):
            a, b = z.copy(), z.copy()
            a[i], b[i] = max(0., z[i]-.001), min(1., z[i]+.001)
            columns.append((residual(b)-residual(a))/(b[i]-a[i]))
        j = np.array(columns).T
        rank = int(np.linalg.matrix_rank(j))
        improved = False
        for _ in range(10):
            step = np.linalg.solve(j.T@j + damping*np.eye(len(z)), -j.T@r)
            candidate = np.clip(z+step, 0., 1.)
            rr = residual(candidate)
            if rr@rr < r@r:
                delta = np.linalg.norm(candidate-z)
                z, r = candidate, rr
                history.append(float(np.sqrt(np.mean(r*r))))
                damping = max(1e-10, damping/3)
                improved = True
                if delta < tolerance:
                    status = 'step_tolerance'
                break
            damping *= 10
        if not improved:
            status = 'stalled'
            break
        if status == 'step_tolerance':
            break
    if history[-1] <= tolerance:
        status = 'residual_tolerance'
    return {'parameters': {n: float(v) for n,v in zip(names,lo+span*z)},
            'status': status, 'rms': history[-1], 'max_abs': float(np.max(np.abs(r))),
            'accepted': history[-1] <= tolerance, 'history': history,
            'evaluations': calls, 'jacobian_rank': rank,
            'at_bound': [n for n,v in zip(names,z) if v < 1e-6 or v > 1-1e-6]}


def fit_pd(reference, target, initial, bounds, **kwargs):
    """Solve the installed add-on's identity controls against normalized targets."""
    return bounded_fit(lambda p: target_vector(reference.extract(p)), target_vector(target),
                       initial, bounds, **kwargs)


def fit_lid_profile(profile, degree=6, shell_thickness=None):
    """Solve compact lid/lash curve parameters against all measured targets.

    Thickness is deliberately supplied by the caller: open reference sheets do
    not determine it. Curves are endpoint-constrained linear least squares.
    """
    validate(profile)
    if not 3 <= degree <= 12:
        raise ValueError('degree must be between 3 and 12')
    if shell_thickness is not None and (not np.isfinite(shell_thickness) or not 0 < shell_thickness < .2):
        raise ValueError('shell thickness must be in (0,.2) eye-width units')
    result = {'schema_version': 1, 'units': profile['units'], 'blink_weights': profile['blink_weights'],
              'shell_thickness': shell_thickness, 'thickness_source': 'caller' if shell_thickness is not None else 'required_for_solid_construction',
              'source_private_input_sha256': profile['provenance']['private_input_sha256'], 'eyes': {}}
    for name, eye in profile['eyes'].items():
        samples = sample_eye(eye, 129)
        margins, lashes = [], []
        errors = []
        for w in range(5):
            row = {k: encode_curve(samples['margin'][w,i], degree) for i,k in enumerate(('upper','lower'))}
            lash = encode_piecewise(samples['lash'][w])
            margins.append(row)
            lashes.append(lash)
            for c in [*row.values(),lash]:
                errors.append(c['reduction_rms'])
        result['eyes'][name] = {'lid_margin': margins, 'lash_centreline': lashes,
                               'socket_depth': eye['socket_depth'], 'lid_thickness': eye['lid_thickness'],
                               'fit_rms': float(np.sqrt(np.mean(np.square(errors)))),
                               'fit_max': max(c['reduction_max'] for row, lash in zip(margins,lashes) for c in [*row.values(),lash])}
    return result


def evaluate_lid(model, side, blink, u):
    """Sample fitted margin, transported lash anchors and local frames at any weight."""
    if not np.isfinite(blink) or not 0 <= blink <= 1:
        raise ValueError('blink must be in [0,1]')
    u = np.atleast_1d(np.asarray(u, dtype=float))
    if u.ndim != 1 or not np.isfinite(u).all() or np.any(u < 0) or np.any(u > 1):
        raise ValueError('u must be in [0,1]')
    eye = model['eyes'][side]
    i = min(int(blink*4), 3)
    t = blink*4-i
    def mix(a,b):
        return {**a, 'coefficients':((1-t)*np.array(a['coefficients'])+t*np.array(b['coefficients'])).tolist()}
    upper = mix(eye['lid_margin'][i]['upper'], eye['lid_margin'][i+1]['upper'])
    lower = mix(eye['lid_margin'][i]['lower'], eye['lid_margin'][i+1]['lower'])
    lash = mix(eye['lash_centreline'][i], eye['lash_centreline'][i+1])
    origin, axes = anchor_frames(upper,u)
    center = curve_points(lash,u)
    return {'upper':origin, 'lower':curve_points(lower,u), 'lash':center,
            'anchor_origin':origin, 'anchor_axes':axes,
            'anchor_offsets':np.einsum('nij,nj->ni',axes,center-origin)}
