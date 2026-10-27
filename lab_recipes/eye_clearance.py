# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Measured projected-triangle clearance with explicitly fixed attachment vertices."""
import numpy as np

def _cross(a,b):return a[0]*b[1]-a[1]*b[0]
def _intersection(subject,clip):
    poly=[x.copy() for x in subject];orientation=np.sign(_cross(clip[1]-clip[0],clip[2]-clip[0]))
    if not orientation:return []
    for a,b in zip(clip,np.roll(clip,-1,axis=0)):
        if not poly:return []
        old=poly;poly=[];edge=b-a
        for p,q in zip(old,old[1:]+old[:1]):
            dp=orientation*_cross(edge,p-a);dq=orientation*_cross(edge,q-a);pin=dp>=-1e-12;qin=dq>=-1e-12
            if pin:poly.append(p)
            if pin!=qin:poly.append(p+(q-p)*dp/(dp-dq))
    return poly
def _bary(points,tri):
    p=np.asarray(points);a=tri[0];u=tri[1]-a;v=tri[2]-a;det=_cross(u,v)
    if abs(det)<1e-20:return None
    d=p-a;s=(d[:,0]*v[1]-d[:,1]*v[0])/det;t=(u[0]*d[:,1]-u[1]*d[:,0])/det
    return np.clip(np.c_[1-s-t,s,t],0,1)

def enforce_eye_clearance(poses,faces,eye_vertices,eye_faces,fixed_vertices,clearance,maximum_offset):
    """Increase only free X coordinates, shared across poses; Y/Z and fixed rows stay exact.

    Every projected overlap polygon vertex is checked. Since both triangle
    depths are affine in Y/Z, these vertices bound the complete overlap at each
    supplied pose. Static positive offsets keep all earlier constraints valid.
    This is not a proof for unsampled nonlinear or time-varying projected overlaps.
    """
    p=np.asarray(poses,float);f=np.asarray(faces);ev=np.asarray(eye_vertices,float);ef=np.asarray(eye_faces);fi=np.asarray(fixed_vertices)
    if p.ndim!=3 or p.shape[2]!=3 or not len(p) or not np.isfinite(p).all() or f.ndim!=2 or f.shape[1]!=3 or not np.issubdtype(f.dtype,np.integer) or f.size and (f.min()<0 or f.max()>=p.shape[1]):raise ValueError('Invalid lid positions or triangle indices')
    if ev.ndim!=2 or ev.shape[1]!=3 or not np.isfinite(ev).all() or ef.ndim!=2 or ef.shape[1]!=3 or not len(ef) or not np.issubdtype(ef.dtype,np.integer) or ef.min()<0 or ef.max()>=len(ev):raise ValueError('Invalid stationary-eye geometry')
    if fi.ndim!=1 or fi.size and (not np.issubdtype(fi.dtype,np.integer) or fi.min()<0 or fi.max()>=p.shape[1]) or not np.isfinite([clearance,maximum_offset]).all() or clearance<0 or maximum_offset<0:raise ValueError('Invalid fixed vertices or clearance limits')
    f=f.astype(int);eye=ev[ef.astype(int)];fixed=np.zeros(p.shape[1],bool);fixed[fi.astype(int)]=True
    lo=eye[:,:,1:].min(1);hi=eye[:,:,1:].max(1);front=eye[:,:,0].max(1);shift=np.zeros(p.shape[1]);constraints=0;adjusted=0;unresolved=[];maximum_initial_shortfall=0.
    for ki,pp in enumerate(p):
        for fi,face in enumerate(f):
            t=pp[face];yz=t[:,1:];d=_cross(yz[1]-yz[0],yz[2]-yz[0])
            if abs(d)<1e-20:continue
            mn=yz.min(0);mx=yz.max(0);x=t[:,0]+shift[face];candidate=np.flatnonzero((lo[:,0]<=mx[0])&(hi[:,0]>=mn[0])&(lo[:,1]<=mx[1])&(hi[:,1]>=mn[1])&(front+clearance>x.min()))
            for ei in candidate:
                poly=_intersection(yz,eye[ei,:,1:])
                if not poly:continue
                bc=_bary(poly,yz);ec=_bary(poly,eye[ei,:,1:])
                if bc is None or ec is None:continue
                source_depth=ec@eye[ei,:,0]
                for weights,depth in zip(bc,source_depth):
                    constraints+=1;needed=float(depth+clearance-weights@(t[:,0]+shift[face]));maximum_initial_shortfall=max(maximum_initial_shortfall,needed)
                    if needed<=1e-9:continue
                    free=weights.copy();free[fixed[face]]=0;den=float(free@free)
                    if den<1e-16:unresolved.append({'pose':ki,'face':fi,'source_face':int(ei),'shortfall':needed});continue
                    shift[face]+=needed*free/den;adjusted+=1
                    if shift.max()>maximum_offset:raise ValueError('Required clearance offset exceeds the declared input-fitted limit')
    result=p.copy();result[:,:,0]+=shift
    return {'poses':result,'x_offsets':shift,'constraints':constraints,'adjustments':adjusted,'maximum_x_offset':float(shift.max()),'maximum_encountered_shortfall':maximum_initial_shortfall,'unresolved_fixed_constraints':unresolved,'fixed_vertices_unchanged':bool(np.array_equal(result[:,fixed],p[:,fixed]))}
