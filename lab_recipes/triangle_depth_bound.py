# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Conservative local front-depth bounds from actual stationary eye triangles.

The callback bounds each supplied Y/Z footprint by the maximum X of all source
triangles whose projected bounding boxes intersect it. This is conservative:
triangle X is affine and cannot exceed its maximum vertex X. False-positive
bbox overlap only increases clearance. Empty footprints return negative infinity
explicitly, allowing the caller to retain its documented no-obstacle fallback.
"""
import numpy as np

class TriangleDepthBound:
    def __init__(self,triangles):
        t=np.asarray(triangles,dtype=float)
        if t.ndim!=3 or t.shape[1:]!=(3,3) or not len(t) or not np.isfinite(t).all():
            raise ValueError('Expected nonempty finite Nx3x3 stationary eye triangles')
        self.minimum=t[:,:,1:].min(axis=1)
        self.maximum=t[:,:,1:].max(axis=1)
        self.front=t[:,:,0].max(axis=1)
        self.last_empty_footprints=0

    def __call__(self,minimum,maximum):
        lo=np.asarray(minimum,dtype=float);hi=np.asarray(maximum,dtype=float)
        if lo.ndim!=2 or lo.shape[1:]!=(2,) or hi.shape!=lo.shape or not np.isfinite(lo).all() or not np.isfinite(hi).all() or np.any(lo>hi):
            raise ValueError('Expected matching finite Nx2 ordered Y/Z footprint bounds')
        result=np.full(len(lo),-np.inf)
        for i,(a,b) in enumerate(zip(lo,hi)):
            overlap=(self.minimum[:,0]<=b[0])&(self.maximum[:,0]>=a[0])&(self.minimum[:,1]<=b[1])&(self.maximum[:,1]>=a[1])
            if overlap.any():result[i]=self.front[overlap].max()
        self.last_empty_footprints=int(np.isneginf(result).sum())
        return result
