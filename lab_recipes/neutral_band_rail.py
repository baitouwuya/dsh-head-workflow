# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Coherent constant-lateral-coordinate projection onto an actual source band."""
import numpy as np

def project_rail_to_band_sections(rail,vertices,triangles):
    rail=np.asarray(rail,float);v=np.asarray(vertices,float);f=np.asarray(triangles)
    if rail.ndim!=2 or rail.shape[1]!=3 or len(rail)<2 or not np.isfinite(rail).all() or v.ndim!=2 or v.shape[1]!=3 or not len(v) or not np.isfinite(v).all():raise ValueError('Finite source band and rail coordinates required')
    if f.ndim!=2 or f.shape[1]!=3 or not len(f) or not np.issubdtype(f.dtype,np.integer) or f.min()<0 or f.max()>=len(v):raise ValueError('Integer source band triangles required')
    if np.any(np.diff(rail[:,1])<=0):raise ValueError('Rail must have strictly increasing lateral coordinates')
    t=v[f];fitted=[];source_faces=[];source_bary=[]
    for point in rail:
        y=point[1];ids=np.flatnonzero((t[:,:,1].min(1)<=y+1e-12)&(t[:,:,1].max(1)>=y-1e-12));candidates=[]
        for i in ids:
            hits=[]
            for a,b in [(0,1),(1,2),(2,0)]:
                ya,yb=t[i,a,1],t[i,b,1]
                if abs(yb-ya)<1e-14:
                    if abs(y-ya)<1e-12:
                        for k in [a,b]:bc=np.eye(3)[k];hits.append((t[i,k],bc))
                elif min(ya,yb)-1e-12<=y<=max(ya,yb)+1e-12:
                    w=np.clip((y-ya)/(yb-ya),0,1);bc=np.zeros(3);bc[a]=1-w;bc[b]=w;hits.append((bc@t[i],bc))
            if not hits:continue
            for a,ba in hits:
                for b,bb in hits:
                    d=b-a;w=np.clip(((point-a)@d)/(d@d),0,1) if d@d>1e-20 else 0.;p=a+w*d;bc=ba+w*(bb-ba);candidates.append((float(np.linalg.norm(p-point)),int(i),p,bc))
        if not candidates:raise ValueError('Source band has no surface support at rail lateral coordinate')
        _,i,p,bc=min(candidates,key=lambda x:x[0]);fitted.append(p);source_faces.append(i);source_bary.append(bc)
    return {'positions':np.array(fitted),'triangle_indices':np.array(source_faces),'barycentric':np.array(source_bary),'maximum_refit_distance':float(np.linalg.norm(np.array(fitted)-rail,axis=1).max())}

def apply_neutral_rail_fit(poses,construction_to_final,cross_section_samples,target_rail,inner_rail,knots):
    p=np.asarray(poses,float);mapping=np.asarray(construction_to_final);inner=np.asarray(inner_rail);target=np.asarray(target_rail,float);knots=np.asarray(knots,float)
    if not isinstance(cross_section_samples,(int,np.integer)) or isinstance(cross_section_samples,bool) or cross_section_samples<4 or cross_section_samples%4:raise ValueError('Explicit quarter-sampled closed-ring topology required')
    m=int(cross_section_samples);station_count=len(inner)
    if p.ndim!=3 or p.shape[2]!=3 or p.shape[0]<2 or not np.isfinite(p).all() or knots.shape!=(len(p),) or not np.isfinite(knots).all() or knots[0]!=0 or knots[-1]!=1 or np.any(np.diff(knots)<=0):raise ValueError('Finite sampled poses and increasing zero-to-one controls required')
    if inner.ndim!=1 or not len(inner) or not np.issubdtype(inner.dtype,np.integer) or inner.min()<0 or inner.max()>=p.shape[1] or mapping.shape!=(station_count*m+2,) or not np.issubdtype(mapping.dtype,np.integer) or mapping.min()<0 or mapping.max()>=p.shape[1] or target.shape!=(station_count,3) or not np.isfinite(target).all():raise ValueError('Construction mapping, inner rail or target mismatch')
    delta=target-p[0,inner];weights=((1-np.sin(2*np.pi*np.arange(m)/m))/2)**2;old=np.zeros((len(mapping),3));old[:station_count*m]=(delta[:,None,:]*weights[None,:,None]).reshape(-1,3);correction=np.zeros_like(p[0]);seen={}
    for oldi,newi in enumerate(mapping):
        if int(newi) in seen and np.linalg.norm(old[oldi]-seen[int(newi)])>1e-9:raise ValueError('Welded trajectories require incompatible neutral fitting offsets')
        seen[int(newi)]=old[oldi];correction[newi]=old[oldi]
    fitted=p+(1-knots)[:,None,None]*correction[None];return fitted


def fit_tapered_neutral_band_rail(rail,vertices,triangles,lateral_bounds,*,taper_outer_fraction,taper_inner_fraction):
    """Fit the central margin while preserving original rail near the canthi.

    Taper fractions are explicit runtime fit parameters, not contact thresholds.
    Band geometry and the declared diagnostic contact limits are unchanged.
    """
    lo,hi=map(float,lateral_bounds)
    if not np.isfinite([lo,hi,taper_outer_fraction,taper_inner_fraction]).all() or hi<=lo or not 0<=taper_outer_fraction<taper_inner_fraction<.5:raise ValueError('Invalid runtime lateral bounds or taper parameters')
    result=project_rail_to_band_sections(rail,vertices,triangles);rail=np.asarray(rail,float);station=(rail[:,1]-lo)/(hi-lo);u=np.clip(np.minimum((station-taper_outer_fraction)/(taper_inner_fraction-taper_outer_fraction),(1-taper_outer_fraction-station)/(taper_inner_fraction-taper_outer_fraction)),0,1);weight=u*u*(3-2*u);result['untapered_positions']=result['positions'].copy();result['positions']=rail+weight[:,None]*(result['positions']-rail);result['taper_weights']=weight;result['maximum_refit_distance']=float(np.linalg.norm(result['positions']-rail,axis=1).max());return result
