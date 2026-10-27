# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Bind exterior anchors to the frontmost measured skin surface in X-forward space."""
import numpy as np
from lab_recipes.skin_attachment import nearest_triangle_bindings


def frontmost_skin_bindings(points,vertices,faces,skin_triangle_ids,*,barycentric_tolerance=1e-9):
    p=np.asarray(points,float);v=np.asarray(vertices,float);f=np.asarray(faces);ids=np.asarray(skin_triangle_ids)
    if p.ndim!=2 or p.shape[1]!=3 or not len(p) or not np.isfinite(p).all() or v.ndim!=2 or v.shape[1]!=3 or not np.isfinite(v).all():raise ValueError('Finite nonempty point and vertex arrays required')
    if f.ndim!=2 or f.shape[1]!=3 or not np.issubdtype(f.dtype,np.integer) or ids.ndim!=1 or not len(ids) or not np.issubdtype(ids.dtype,np.integer) or ids.min()<0 or ids.max()>=len(f) or f.min()<0 or f.max()>=len(v):raise ValueError('Explicit valid source skin triangle IDs required')
    if not np.isfinite(barycentric_tolerance) or barycentric_tolerance<0:raise ValueError('Invalid barycentric tolerance')
    t=v[f[ids]];a=t[:,0,1:];u=t[:,1,1:]-a;w=t[:,2,1:]-a;det=u[:,0]*w[:,1]-u[:,1]*w[:,0];valid=abs(det)>1e-20;chosen=[];weights=[];positions=[];support=[]
    for number,q in enumerate(p):
        d=q[1:]-a;beta=np.divide(d[:,0]*w[:,1]-d[:,1]*w[:,0],det,out=np.zeros(len(ids)),where=valid);gamma=np.divide(u[:,0]*d[:,1]-u[:,1]*d[:,0],det,out=np.zeros(len(ids)),where=valid);hit=valid&(beta>=-barycentric_tolerance)&(gamma>=-barycentric_tolerance)&(beta+gamma<=1+barycentric_tolerance);candidates=np.flatnonzero(hit)
        if not len(candidates):raise ValueError('No projected source-skin support for anchor '+str(number))
        bc=np.c_[1-beta[candidates]-gamma[candidates],beta[candidates],gamma[candidates]];bc=np.maximum(bc,0);bc/=bc.sum(1)[:,None];position=np.einsum('ni,nij->nj',bc,t[candidates]);k=int(np.argmax(position[:,0]));chosen.append(int(ids[candidates[k]]));weights.append(bc[k]);positions.append(position[k]);support.append(len(candidates))
    positions=np.asarray(positions)
    return {'positions':positions,'source_triangle_ids':np.asarray(chosen,int),'barycentric':np.asarray(weights),'projected_support_count':np.asarray(support,int),'signed_forward_correction':positions[:,0]-p[:,0],'maximum_projection_residual_yz':float(np.abs(positions[:,1:]-p[:,1:]).max()),'source_geometry_changed':False}


def fit_frontmost_skin_anchors(query_points,vertices,faces,fitting_triangle_ids,skin_triangle_ids):
    """Fit projected support locally, then select its actual exterior skin sheet.

    The nearest local skin point establishes lateral/vertical support only. Its
    depth may be on an occluded fold; a complete skin ray determines exterior X.
    Source geometry, canonical identity and original image/UV bytes are untouched.
    """
    initial=nearest_triangle_bindings(query_points,vertices,np.asarray(faces)[fitting_triangle_ids]);out=frontmost_skin_bindings(initial['positions'],vertices,faces,skin_triangle_ids);out['initial_nearest_positions']=initial['positions'];out['initial_nearest_distances']=initial['distance'];out['hidden_nearest_anchor_count']=int((out['signed_forward_correction']>1e-6).sum());return out

class FrontmostSkinIndex:
    """Certify no source-skin triangle occludes any point of a boundary segment."""
    def __init__(self,vertices,faces,skin_triangle_ids):
        vv=np.asarray(vertices,float);ff=np.asarray(faces);ii=np.asarray(skin_triangle_ids)
        if vv.ndim!=2 or vv.shape[1]!=3 or not len(vv) or not np.isfinite(vv).all() or ff.ndim!=2 or ff.shape[1]!=3 or not len(ff) or not np.issubdtype(ff.dtype,np.integer) or ff.min()<0 or ff.max()>=len(vv) or ii.ndim!=1 or not len(ii) or not np.issubdtype(ii.dtype,np.integer) or ii.min()<0 or ii.max()>=len(ff):raise ValueError('Valid nonempty source skin geometry required')
        self.ids=ii.astype(int);self.tri=vv[ff[self.ids]];self.a=self.tri[:,0,1:];self.u=self.tri[:,1,1:]-self.a;self.w=self.tri[:,2,1:]-self.a;self.det=self.u[:,0]*self.w[:,1]-self.u[:,1]*self.w[:,0];self.valid=abs(self.det)>1e-20
    def _bary(self,p):
        d=np.asarray(p)[1:]-self.a;s=np.divide(d[:,0]*self.w[:,1]-d[:,1]*self.w[:,0],self.det,out=np.zeros(len(self.ids)),where=self.valid);t=np.divide(self.u[:,0]*d[:,1]-self.u[:,1]*d[:,0],self.det,out=np.zeros(len(self.ids)),where=self.valid);return np.c_[1-s-t,s,t]
    def segment_frontmost(self,a,b,tolerance=1e-6):
        if not np.isfinite(tolerance) or tolerance<0:raise ValueError('Invalid visibility tolerance')
        a=np.asarray(a,float);b=np.asarray(b,float)
        if a.shape!=(3,) or b.shape!=(3,) or not np.isfinite([a,b]).all():raise ValueError('Finite segment endpoints required')
        ba=self._bary(a);bb=self._bary(b);delta=bb-ba;lo=np.zeros(len(self.ids));hi=np.ones(len(self.ids));valid=self.valid.copy() & (self.tri[:,:,1:].min(1)<=np.maximum(a[1:],b[1:])+1e-12).all(1) & (self.tri[:,:,1:].max(1)>=np.minimum(a[1:],b[1:])-1e-12).all(1)
        for j in range(3):
            inc=delta[:,j]>1e-15;dec=delta[:,j]<-1e-15;constant=~(inc|dec);threshold=np.divide(-ba[:,j],delta[:,j],out=np.zeros(len(self.ids)),where=~constant);lo[inc]=np.maximum(lo[inc],threshold[inc]);hi[dec]=np.minimum(hi[dec],threshold[dec]);valid &= ~(constant&(ba[:,j]<-1e-10))
        valid &= lo<=hi+1e-12
        depths_a=np.einsum('ij,ij->i',ba,self.tri[:,:,0])-a[0];depths_b=np.einsum('ij,ij->i',bb,self.tri[:,:,0])-b[0];gap_lo=depths_a+lo*(depths_b-depths_a);gap_hi=depths_a+hi*(depths_b-depths_a);gaps=np.maximum(gap_lo,gap_hi);ids=np.flatnonzero(valid)
        if not len(ids):return {'frontmost':False,'nonempty_projected_support':False,'maximum_occluding_depth':None}
        intervals=sorted((max(0.,float(lo[j])),min(1.,float(hi[j]))) for j in ids);reach=0.;covered=True
        for l,h in intervals:
            if l>reach+1e-10:covered=False;break
            reach=max(reach,h)
        covered=covered and reach>=1-1e-10
        i=ids[np.argmax(gaps[ids])];return {'frontmost':bool(covered and gaps[i]<=tolerance),'nonempty_projected_support':True,'complete_projected_support':covered,'maximum_occluding_depth':float(gaps[i]),'occluding_source_triangle':int(self.ids[i]),'witness_parameter':float(np.clip(lo[i] if gap_lo[i]>=gap_hi[i] else hi[i],0,1))}

def frontmost_skin_triangle_ids(vertices,faces,skin_triangle_ids,candidate_triangle_ids,*,depth_tolerance=1e-6):
    """Conservative complete-triangle exterior-sheet test against all source skin.

    Both projected triangle depths are affine. Their difference reaches its
    maximum on an overlap polygon vertex, so centroid/vertex samples are not used
    as a substitute for this complete overlap test.
    """
    from lab_recipes.eye_clearance import _intersection,_bary
    v=np.asarray(vertices,float);f=np.asarray(faces);skin=np.asarray(skin_triangle_ids);candidates=np.asarray(candidate_triangle_ids)
    FrontmostSkinIndex(v,f,skin)
    if candidates.ndim!=1 or not len(candidates) or not np.issubdtype(candidates.dtype,np.integer) or candidates.min()<0 or candidates.max()>=len(f) or not np.isfinite(depth_tolerance) or depth_tolerance<0:raise ValueError('Valid explicit candidate triangles and depth tolerance required')
    st=v[f[skin]];lo=st[:,:,1:].min(1);hi=st[:,:,1:].max(1);mx=st[:,:,0].max(1);result=[];rejected=[]
    for fid in candidates:
        t=v[f[fid]];yz=t[:,1:];a=yz[1]-yz[0];b=yz[2]-yz[0]
        if abs(a[0]*b[1]-a[1]*b[0])<1e-20:continue
        mn=yz.min(0);ma=yz.max(0);possible=np.flatnonzero((lo[:,0]<=ma[0])&(hi[:,0]>=mn[0])&(lo[:,1]<=ma[1])&(hi[:,1]>=mn[1])&(mx>t[:,0].min()+depth_tolerance));maxgap=0.;blocker=None
        for j in possible:
            if skin[j]==fid:continue
            polygon=_intersection(yz,st[j,:,1:])
            if not polygon:continue
            bc=_bary(polygon,yz);other=_bary(polygon,st[j,:,1:])
            if bc is None or other is None:continue
            gap=float(np.max(other@st[j,:,0]-bc@t[:,0]))
            if gap>maxgap:maxgap=gap;blocker=int(skin[j])
            if gap>depth_tolerance:break
        if maxgap<=depth_tolerance:result.append(int(fid))
        else:rejected.append({'triangle':int(fid),'occluding_triangle':blocker,'depth_gap':maxgap})
    return {'triangle_ids':np.asarray(result,int),'rejected':rejected,'candidate_count':len(candidates),'depth_tolerance':float(depth_tolerance)}
