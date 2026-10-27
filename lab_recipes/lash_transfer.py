# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Rigid moving-least-squares transfer of original lashes from a measured lid rail.

The working frame is +X depth, Y lateral, +Z up. Each original point receives a
weighted rigid fit in the YZ material plane, plus a smooth measured depth
translation. This avoids directly adding an arbitrary displacement gradient to
a thick curved lash ribbon. Whole confirmed source components must be supplied;
this routine does not discover semantics, clip masks, edit topology or UVs.
The influence radius is measured/runtime configuration, never an asset constant.
Actual attachment, strain, interval validity and rendered appearance must still
be audited; a fitted transfer is not itself an acceptance certificate.
"""
import numpy as np

def _xyz(value,name):
    a=np.asarray(value,dtype=float)
    if a.ndim!=2 or a.shape[1]!=3 or not len(a) or not np.isfinite(a).all():
        raise ValueError(name+' must be a nonempty finite Nx3 array')
    return a

class RigidLashCurveBinding:
    def __init__(self,points,neutral_curve,*,influence_radius,weight_power=2.):
        self.points=_xyz(points,'points').copy();self.neutral_curve=_xyz(neutral_curve,'neutral_curve').copy()
        if len(self.neutral_curve)<2:raise ValueError('A lid rail requires at least two points')
        if not np.isfinite([influence_radius,weight_power]).all() or influence_radius<=0 or weight_power<=0:
            raise ValueError('influence_radius and weight_power must be finite and positive')
        q=self.neutral_curve[:,1:];p=self.points[:,1:]
        if np.linalg.norm(np.ptp(q,axis=0))<=0:raise ValueError('Neutral rail has no material-plane extent')
        self.influence_radius=float(influence_radius);self.weight_power=float(weight_power)
        distance=np.sum((p[:,None]-q[None])**2,axis=2)
        # Dividing by the smallest denominator makes this stable under unit scaling.
        denominator=distance+self.influence_radius**2
        weights=(denominator.min(1)[:,None]/denominator)**self.weight_power
        self.weights=weights/weights.sum(1)[:,None]
        self.centers=self.weights@q
        self.reference_offsets=q[None]-self.centers[:,None]
        self.point_offsets=p-self.centers

    def _fit(self,posed_curve):
        curve=_xyz(posed_curve,'posed_curve')
        if curve.shape!=self.neutral_curve.shape:raise ValueError('Posed rail changed topology or correspondence')
        target=curve[:,1:];centers=self.weights@target;offsets=target[None]-centers[:,None]
        dot=np.sum(self.weights*np.sum(self.reference_offsets*offsets,axis=2),axis=1)
        cross=np.sum(self.weights*(self.reference_offsets[:,:,0]*offsets[:,:,1]-self.reference_offsets[:,:,1]*offsets[:,:,0]),axis=1)
        if np.any(np.hypot(dot,cross)<=np.finfo(float).tiny):raise ValueError('Posed rail cannot define a rigid material-plane fit')
        return curve,centers,np.arctan2(cross,dot)

    def evaluate(self,posed_curve):
        curve=_xyz(posed_curve,'posed_curve')
        if curve.shape!=self.neutral_curve.shape:raise ValueError('Posed rail changed topology or correspondence')
        if np.array_equal(curve,self.neutral_curve):return self.points.copy()
        curve,centers,angle=self._fit(curve);cs=np.cos(angle);sn=np.sin(angle);p=self.point_offsets
        out=self.points.copy()
        out[:,1]=centers[:,0]+cs*p[:,0]-sn*p[:,1]
        out[:,2]=centers[:,1]+sn*p[:,0]+cs*p[:,1]
        out[:,0]+=self.weights@(curve[:,0]-self.neutral_curve[:,0])
        if not np.isfinite(out).all():raise ValueError('Non-finite lash transfer')
        return out

    def evaluate_normals(self,normals,posed_curve):
        """Rotate original material normals by the same fitted local rotation.

        Caller preserves source NORMAL bytes and exports the returned deltas
        only on the mapped original lash vertices. This is material-frame
        transfer, not a claim of recomputed smooth normals on the complete mesh.
        """
        n=_xyz(normals,'normals')
        if n.shape!=self.points.shape:raise ValueError('Normals do not match bound points')
        curve=_xyz(posed_curve,'posed_curve')
        if curve.shape!=self.neutral_curve.shape:raise ValueError('Posed rail changed topology or correspondence')
        if np.array_equal(curve,self.neutral_curve):return n.copy()
        _,_,angle=self._fit(curve);cs=np.cos(angle);sn=np.sin(angle);out=n.copy()
        out[:,1]=cs*n[:,1]-sn*n[:,2];out[:,2]=sn*n[:,1]+cs*n[:,2]
        return out

    def profile(self):
        return {'method':'rigid moving-least-squares in measured YZ material plane with measured X translation',
                'points':len(self.points),'rail_points':len(self.neutral_curve),
                'influence_radius':self.influence_radius,'weight_power':self.weight_power,
                'working_frame':'+X depth, Y lateral, +Z up',
                'semantic_requirement':'whole confirmed source lash components',
                'verification_required':['actual surface attachment','edge strain','continuous exported morph validity','neutral/reset identity','matched textured views']}

def audit_paired_attachment(neutral_roots,posed_roots,neutral_carrier_points,posed_carrier_points,*,maximum_gap):
    """Audit frozen material contacts against independently evaluated mesh points.

    Carrier points must come from actual source/posed triangles or canonical
    vertices using fixed correspondence, not from the transfer function itself.
    Already detached neutral points cannot obtain a pass by preserving their
    offset. Root classification/coverage and correspondence belong in evidence.
    """
    root=_xyz(neutral_roots,'neutral_roots');posed=_xyz(posed_roots,'posed_roots')
    carrier=_xyz(neutral_carrier_points,'neutral_carrier_points');current=_xyz(posed_carrier_points,'posed_carrier_points')
    if any(a.shape!=root.shape for a in [posed,carrier,current]):raise ValueError('Attachment correspondence shape mismatch')
    if not np.isfinite(maximum_gap) or maximum_gap<0:raise ValueError('maximum_gap must be finite and nonnegative')
    before=np.linalg.norm(root-carrier,axis=1);after=np.linalg.norm(posed-current,axis=1)
    return {'root_count':len(root),'maximum_gap_limit':float(maximum_gap),
            'neutral_gap_quantiles':np.quantile(before,[0,.5,.95,1]).tolist(),
            'posed_gap_quantiles':np.quantile(after,[0,.5,.95,1]).tolist(),
            'maximum_gap_growth':float((after-before).max()),
            'neutral_attachment_pass':bool(np.all(before<=maximum_gap)),
            'posed_attachment_pass':bool(np.all(after<=maximum_gap)),
            'attachment_pass':bool(np.all(before<=maximum_gap)&np.all(after<=maximum_gap))}

def audit_lash_edge_strain(neutral,posed,triangles,*,minimum_edge_length,minimum_ratio,maximum_ratio):
    """Check both extension and compression; all limits are explicit runtime data."""
    a=_xyz(neutral,'neutral');b=_xyz(posed,'posed');f=np.asarray(triangles)
    if a.shape!=b.shape or f.ndim!=2 or f.shape[1]!=3 or not len(f) or not np.issubdtype(f.dtype,np.integer) or f.min()<0 or f.max()>=len(a):raise ValueError('Invalid lash geometry')
    if not np.isfinite([minimum_edge_length,minimum_ratio,maximum_ratio]).all() or minimum_edge_length<0 or not 0<minimum_ratio<=1<=maximum_ratio:raise ValueError('Invalid strain thresholds')
    edges=np.unique(np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1),axis=0)
    initial=np.linalg.norm(a[edges[:,0]]-a[edges[:,1]],axis=1);final=np.linalg.norm(b[edges[:,0]]-b[edges[:,1]],axis=1);keep=initial>minimum_edge_length
    if not keep.any():raise ValueError('No valid source edges remain above the runtime floor')
    ratio=final[keep]/initial[keep];bad=(ratio<minimum_ratio)|(ratio>maximum_ratio)
    return {'source_edge_count':len(edges),'audited_edge_count':int(keep.sum()),'excluded_short_edge_count':int((~keep).sum()),
        'minimum_edge_length':float(minimum_edge_length),'allowed_ratio_range':[float(minimum_ratio),float(maximum_ratio)],
        'minimum_edge_ratio':float(ratio.min()),'maximum_edge_ratio':float(ratio.max()),
        'p99_abs_log_strain':float(np.quantile(abs(np.log(np.maximum(ratio,np.finfo(float).tiny))),.99)),
        'violating_edge_count':int(bad.sum()),'strain_pass':bool(not bad.any())}
