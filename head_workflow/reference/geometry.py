# SPDX-License-Identifier: GPL-3.0-or-later
"""Geometry reduction. Source topology and coordinates never enter public output."""
from collections import Counter, defaultdict
import numpy as np
from numpy.polynomial import chebyshev as ch


def boundary_loops(faces):
    counts = Counter(tuple(sorted((int(a), int(b))))
                     for tri in faces for a, b in zip(tri, np.roll(tri, -1)))
    if any(n > 2 for n in counts.values()):
        raise ValueError('non-manifold region')
    adj = defaultdict(set)
    for (a, b), n in counts.items():
        if n == 1:
            adj[a].add(b)
            adj[b].add(a)
    if not adj or any(len(v) != 2 for v in adj.values()):
        raise ValueError('region must have simple closed boundaries')
    remaining, loops = set(adj), []
    while remaining:
        start = min(remaining)
        loop, prev, cur = [], None, start
        while True:
            loop.append(cur)
            remaining.remove(cur)
            nxt = min(adj[cur] - ({prev} if prev is not None else set()))
            if nxt == start:
                break
            prev, cur = cur, nxt
        loops.append(np.array(loop))
    return loops


def split_lids(vertices, loop, side):
    q = vertices[loop]
    x = side * q[:, 0]
    inner, outer = int(np.argmin(x)), int(np.argmax(x))
    ordered = np.roll(loop, -inner)
    k = int(np.where(ordered == loop[outer])[0][0])
    a = ordered[:k + 1]
    b = np.r_[ordered[0], ordered[:k - 1:-1]]
    return (a, b) if vertices[a, 2].mean() > vertices[b, 2].mean() else (b, a)


def frame_for(vertices, upper):
    inner, outer = vertices[upper[[0, -1]]]
    lateral = outer - inner
    width = np.linalg.norm(lateral)
    if not np.isfinite(width) or width < 1e-8:
        raise ValueError('degenerate eye width')
    lateral /= width
    up = np.array([0., 0., 1.])
    up -= lateral * np.dot(up, lateral)
    if np.linalg.norm(up) < 1e-8:
        raise ValueError('eye lateral axis parallel to up')
    up /= np.linalg.norm(up)
    forward = np.cross(lateral, up)
    if forward[1] > 0:
        forward *= -1  # PD faces -Y; both eyes use positive outward depth.
    return (inner + outer) / 2, np.stack([lateral, up, forward]), width


def normalize(points, frame):
    origin, axes, width = frame
    return (np.asarray(points) - origin) @ axes.T / width


def sample_path(points, neutral_points, count=65):
    lengths = np.r_[0., np.cumsum(np.linalg.norm(np.diff(neutral_points, axis=0), axis=1))]
    if lengths[-1] < 1e-10 or np.any(np.diff(lengths) < 1e-12):
        raise ValueError('degenerate path')
    t = lengths / lengths[-1]
    u = np.linspace(0, 1, count)
    return np.column_stack([np.interp(u, t, points[:, k]) for k in range(3)])


def encode_curve(points, degree=8):
    """Constrained Chebyshev regression; endpoints are retained, no vertex list."""
    p = np.asarray(points, dtype=float)
    x = np.linspace(-1, 1, len(p))
    a = ch.chebvander(x, degree)
    c = ch.chebvander(np.array([-1., 1.]), degree)
    lhs = np.block([[a.T @ a, c.T], [c, np.zeros((2, 2))]])
    rhs = np.vstack([a.T @ p, p[[0, -1]]])
    coeff = np.linalg.solve(lhs, rhs)[:degree + 1]
    error = np.linalg.norm(a @ coeff - p, axis=1)
    return {'basis': 'chebyshev', 'coefficients': np.round(coeff, 7).tolist(),
            'reduction_rms': round(float(np.sqrt(np.mean(error**2))), 7),
            'reduction_max': round(float(error.max()), 7)}


def curve_points(curve, u):
    if curve['basis'] == 'piecewise_chebyshev':
        u = np.asarray(u, dtype=float)
        breaks = np.array(curve['breaks'])
        idx = np.clip(np.searchsorted(breaks,u,side='right')-1,0,len(breaks)-2)
        x = 2*(u-breaks[idx])/(breaks[idx+1]-breaks[idx])-1
        coeff = np.asarray(curve['coefficients'])
        return np.einsum('...j,...jk->...k',ch.chebvander(x,coeff.shape[1]-1),coeff[idx])
    return ch.chebvander(2 * np.asarray(u) - 1, len(curve['coefficients']) - 1) @ np.asarray(curve['coefficients'])


def encode_piecewise(points, degree=4, segments=8):
    p = np.asarray(points)
    if (len(p)-1) % segments:
        raise ValueError('sample intervals must be divisible by segment count')
    step = (len(p)-1)//segments
    curves = [encode_curve(p[i*step:(i+1)*step+1],degree) for i in range(segments)]
    result = {'basis':'piecewise_chebyshev','breaks':np.linspace(0,1,segments+1).tolist(),
              'coefficients':[c['coefficients'] for c in curves]}
    errors = np.linalg.norm(curve_points(result,np.linspace(0,1,len(p)))-p,axis=1)
    result.update(reduction_rms=round(float(np.sqrt(np.mean(errors**2))),7),
                  reduction_max=round(float(errors.max()),7))
    return result


def statistics(values):
    a = np.asarray(values, dtype=float)
    if not a.size or not np.isfinite(a).all():
        raise ValueError('empty or nonfinite measurement')
    return {k: round(float(v), 7) for k, v in zip(
        ('min', 'median', 'mean', 'p95', 'max'),
        (a.min(), np.median(a), a.mean(), np.quantile(a, .95), a.max()))}


def anchor_frames(margin, u):
    """Right-handed tangent/binormal/normal frames in normalized coordinates."""
    u = np.asarray(u)
    origin = curve_points(margin, u)
    coeff = np.asarray(margin['coefficients'])
    tangent = ch.chebvander(2*u-1, len(coeff)-2) @ ch.chebder(coeff) * 2
    norm = np.linalg.norm(tangent, axis=1)
    if np.any(norm < 1e-10):
        raise ValueError('degenerate anchor tangent')
    tangent /= norm[:, None]
    normal = np.tile([0., 0., 1.], (len(u), 1))
    normal -= (normal*tangent).sum(1)[:, None]*tangent
    norm = np.linalg.norm(normal, axis=1)
    if np.any(norm < 1e-10):
        raise ValueError('anchor tangent parallel to depth')
    normal /= norm[:, None]
    binormal = np.cross(normal, tangent)
    return origin, np.stack([tangent, binormal, normal], axis=1)
