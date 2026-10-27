# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Explicit aperture-chain contract for the measured eyelid recipe.

Coordinates use the recipe's documented working frame: +X forward, Y across
the aperture, +Z upward. An observed aperture envelope is not, by itself, an
anatomical attachment loop. Never infer a contour from arbitrary point order.
"""
import math


def _points(values, name):
    points = [tuple(float(v) for v in p) for p in values]
    if not points or any(len(p) != 3 or not all(math.isfinite(v) for v in p) for p in points):
        raise ValueError(name + ' must contain finite XYZ triples')
    return points


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def validate_ordered_rim(rim_xyz):
    """Reject non-simple, zero-area or non-Y-monotone closed rim sequences.

    The closing point is implicit; repeating the first point at the end is an
    error. Return copied finite XYZ tuples. Input is never silently reordered.
    """
    rim = _points(rim_xyz, 'rim_xyz')
    if len(rim) < 3:
        raise ValueError('rim_xyz requires at least three ordered boundary points')
    yz = [(p[1], p[2]) for p in rim]
    span = max(max(p[k] for p in yz)-min(p[k] for p in yz) for k in (0, 1))
    if span <= 0:
        raise ValueError('rim_xyz has no aperture extent')
    eps = span * 1e-10
    eps_area = span * eps
    def same(a, b):
        return math.dist(a, b) <= eps
    if any(same(a, b) for i, a in enumerate(yz) for b in yz[i+1:]):
        raise ValueError('rim_xyz contains repeated projected boundary points')
    area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(yz,yz[1:]+yz[:1]))
    if abs(area) <= eps_area:
        raise ValueError('rim_xyz has zero projected area or an invalid winding')
    def on(a, b, p):
        return abs(_cross(a,b,p)) <= eps_area and all(min(a[k],b[k])-eps <= p[k] <= max(a[k],b[k])+eps for k in (0,1))
    edges = list(zip(yz,yz[1:]+yz[:1]))
    for i,(a,b) in enumerate(edges):
        for j in range(i+1,len(edges)):
            if j == i+1 or (i == 0 and j == len(edges)-1):
                continue
            c,d=edges[j]
            ac,ad,ca,cb=_cross(a,b,c),_cross(a,b,d),_cross(c,d,a),_cross(c,d,b)
            if (ac*ad < -eps_area**2 and ca*cb < -eps_area**2) or on(a,b,c) or on(a,b,d) or on(c,d,a) or on(c,d,b):
                raise ValueError('rim_xyz is self-intersecting; supply ordered upper/lower boundary chains')
    ys=sorted(set(p[0] for p in yz))
    for left,right in zip(ys,ys[1:]):
        if right-left <= eps:
            continue
        y=(left+right)/2
        crossings=sum(min(a[0],b[0]) < y < max(a[0],b[0]) for a,b in edges)
        if crossings != 2:
            raise ValueError('rim_xyz must form a single Y-monotone aperture envelope')
    return rim


def rim_from_upper_lower_chains(upper_xyz, lower_xyz):
    """Join explicit upper/lower chains, both supplied in increasing Y order.

    The chains must have matching sample Y coordinates and upper Z >= lower Z.
    Endpoints may coincide, with closure deduplicated explicitly. Return lower
    left-to-right followed by upper right-to-left (CCW in the YZ plane).
    """
    upper=_points(upper_xyz,'upper_xyz');lower=_points(lower_xyz,'lower_xyz')
    if len(upper) != len(lower) or len(upper) < 2:
        raise ValueError('upper/lower chains need equal length and at least two stations')
    scale=max(max(p[1] for p in upper)-min(p[1] for p in upper),max(p[2] for p in upper)-min(p[2] for p in lower))
    eps=max(scale,1e-300)*1e-10
    if any(b[1]-a[1] <= eps for chain in (upper,lower) for a,b in zip(chain,chain[1:])):
        raise ValueError('upper/lower chains must each be strictly increasing in Y')
    if any(abs(u[1]-l[1]) > eps or u[2] < l[2]-eps for u,l in zip(upper,lower)):
        raise ValueError('upper/lower stations must match in Y and preserve upper/lower Z order')
    raw=lower+list(reversed(upper));rim=[]
    for p in raw:
        if rim and math.dist(p[1:],rim[-1][1:]) <= eps:
            if math.dist(p,rim[-1]) > eps:
                raise ValueError('coincident projected endpoints disagree in depth')
            continue
        rim.append(p)
    if len(rim)>1 and math.dist(rim[0][1:],rim[-1][1:]) <= eps:
        if math.dist(rim[0],rim[-1]) > eps:
            raise ValueError('closing endpoints disagree in depth')
        rim.pop()
    return validate_ordered_rim(rim)


def construction_envelope_from_samples(samples_xyz):
    """Make an explicit conservative convex construction envelope in YZ.

    This operation is intentionally separate from ordered-rim validation. Its
    convex hull is NOT an anatomical rim or attachment loop, and must NOT
    replace or shrink the frozen source visibility/acceptance probes. It is
    suitable only when a conservative construction envelope is an explicitly
    recorded choice. Duplicate projected YZ samples retain maximum X, giving
    the conservative front depth in the recipe's +X-forward working frame.
    """
    samples=_points(samples_xyz,'samples_xyz')
    front={}
    for x,y,z in samples:
        front[(y,z)]=max(x,front.get((y,z),-math.inf))
    points=sorted(front)
    if len(points)<3:
        raise ValueError('construction envelope needs at least three distinct projected samples')
    lower=[]
    for point in points:
        while len(lower)>=2 and _cross(lower[-2],lower[-1],point)<=0:
            lower.pop()
        lower.append(point)
    upper=[]
    for point in reversed(points):
        while len(upper)>=2 and _cross(upper[-2],upper[-1],point)<=0:
            upper.pop()
        upper.append(point)
    hull=lower[:-1]+upper[:-1]
    if len(hull)<3:
        raise ValueError('construction envelope samples are collinear')
    return validate_ordered_rim([(front[(y,z)],y,z) for y,z in hull])


def weighted_clearance_projection(value, minimum, weight):
    """Continuous projection correction; weight=0 must leave value unchanged.

    This fixes a neutral-invariance defect, not inadequate topology or closure.
    A full blink still requires independent exported-geometry validation.
    """
    if not all(math.isfinite(v) for v in (value,minimum,weight)) or not 0 <= weight <= 1:
        raise ValueError('clearance projection requires finite values and weight in [0,1]')
    return value + weight * max(0.0,minimum-value)


def validate_surface_parameters(eye, parameters):
    for name in ('linear_contour', 'conservative_envelope', 'uniform_cross_section'):
        if name in parameters and not isinstance(parameters[name], bool):
            raise ValueError(name + ' must be a boolean')
    rim=validate_ordered_rim(eye['rim_xyz'])
    center=_points([eye['sphere_center']],'sphere_center')[0]
    radius=float(eye['sphere_radius'])
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError('sphere_radius must be finite and positive')
    affine=eye['affine_globe']
    for name in ('depth_scale','shear_y','shear_z'):
        if not math.isfinite(float(affine[name])):
            raise ValueError('affine_globe contains non-finite values')
    if affine['depth_scale'] <= 0:
        raise ValueError('affine_globe.depth_scale must be positive')
    for name,minimum in (('length_segments',3),('cross_section_samples',4)):
        value=parameters[name]
        if isinstance(value,bool) or not isinstance(value,int) or value < minimum:
            raise ValueError(name+' must be an integer >= '+str(minimum))
    if parameters.get('uniform_cross_section') and parameters['cross_section_samples'] % 4:
        raise ValueError('uniform_cross_section requires a multiple of four samples to retain exact outer anchors')
    positive=('collar_width_m','shell_thickness_m','globe_softplus_epsilon_m2','smoothmax_epsilon_m')
    nonnegative=('corner_extension_m','closure_overlap_m','clearance_m','upper_closure_depth_offset_m')
    for name in positive+nonnegative:
        value=float(parameters[name])
        if not math.isfinite(value) or (value <= 0 if name in positive else value < 0):
            raise ValueError(name+' has an invalid range')
    smoothing=float(parameters.get('envelope_smoothing_m',.0008))
    if not math.isfinite(smoothing) or smoothing <= 0:
        raise ValueError('envelope_smoothing_m must be finite and positive')
    fraction=float(parameters['closure_height_fraction'])
    if not math.isfinite(fraction) or not -1 < fraction < 1:
        raise ValueError('closure_height_fraction must lie strictly between -1 and 1')
    return rim,center
