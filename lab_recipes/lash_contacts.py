# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Freeze explicit static-corner, moving-rail and accessory contact roles.

The caller classifies complete original components from the actual input.
Incidental neutral skin overlap is not automatically a static anatomical root.
All distances, support spans and orientation limits come from runtime fitting.
No character-specific vertex IDs, component numbers or filenames are embedded.
"""
import numpy as np

def classify_lash_contacts(vertices,triangles,canonical_ids,band_indices,skin_triangle_indices,
                           accessory_groups,rail_poses,aperture_lateral_bounds,*,
                           contact_tolerance,corner_fraction,minimum_front_normal_x,
                           minimum_dynamic_motion,minimum_moving_roots,minimum_moving_span,
                           query_nearest_triangles):
    v=np.asarray(vertices,float);f=np.asarray(triangles);ids=np.asarray(canonical_ids);band=np.asarray(band_indices);skin=np.asarray(skin_triangle_indices);rail=np.asarray(rail_poses,float)
    if v.ndim!=2 or v.shape[1]!=3 or not len(v) or not np.isfinite(v).all():raise ValueError('Finite source vertices required')
    if f.ndim!=2 or f.shape[1]!=3 or not len(f) or not np.issubdtype(f.dtype,np.integer) or f.min()<0 or f.max()>=len(v):raise ValueError('Valid source triangle indices required')
    if ids.shape!=(len(v),) or not np.issubdtype(ids.dtype,np.integer) or np.any(ids<0):raise ValueError('Nonnegative canonical source IDs required')
    for index,limit in [(band,len(v)),(skin,len(f))]:
        if index.ndim!=1 or not len(index) or not np.issubdtype(index.dtype,np.integer) or index.min()<0 or index.max()>=limit:raise ValueError('Valid nonempty band/skin indices required')
    lo,hi=map(float,aperture_lateral_bounds)
    thresholds=[contact_tolerance,corner_fraction,minimum_front_normal_x,minimum_dynamic_motion,minimum_moving_span,lo,hi]
    if not np.isfinite(thresholds).all() or contact_tolerance<0 or not 0<corner_fraction<.5 or not -1<=minimum_front_normal_x<=1 or minimum_dynamic_motion<0 or minimum_moving_span<0 or hi<=lo or not isinstance(minimum_moving_roots,int) or isinstance(minimum_moving_roots,bool) or minimum_moving_roots<1:raise ValueError('Invalid runtime contact thresholds')
    if rail.ndim!=3 or rail.shape[2]!=3 or rail.shape[0]<2 or rail.shape[1]<2 or not np.isfinite(rail).all():raise ValueError('Corresponded finite neutral/posed rails required')
    _,first=np.unique(ids[band],return_index=True);band=band[first];skin_vertices=np.unique(f[skin])
    def nearest_vertex(points,target):
        distances=[];indices=[]
        for start in range(0,len(points),32):
            d=np.sum((points[start:start+32,None]-target[None])**2,axis=2);which=d.argmin(1);distances.extend(np.sqrt(d[np.arange(len(which)),which]));indices.extend(which)
        return np.asarray(distances),np.asarray(indices,int)
    distance,nearest=nearest_vertex(v[band],v[skin_vertices]);candidate=np.flatnonzero(distance<=contact_tolerance);skin_contacts=band[candidate]
    if not len(candidate):raise ValueError('No measured source-skin contacts; contact roles require review')
    surface=query_nearest_triangles(v[skin_contacts],v,f[skin]);face=v[f[skin[np.asarray(surface['triangle_indices'],int)]]];normal=np.cross(face[:,1]-face[:,0],face[:,2]-face[:,0]);norm=np.linalg.norm(normal,axis=1);normal_x=np.divide(normal[:,0],norm,out=np.zeros(len(norm)),where=norm>0)
    station=(v[skin_contacts,1]-lo)/(hi-lo);corner=(station<=corner_fraction)|(station>=1-corner_fraction);front=normal_x>minimum_front_normal_x;static=skin_contacts[corner&front];static_carriers=skin_vertices[nearest[candidate[corner&front]]]
    if not len(static) or not (np.any(station[corner&front]<=corner_fraction) and np.any(station[corner&front]>=1-corner_fraction)):
        raise ValueError('Verified front-skin support is required at both aperture ends')
    # Bind moving margin points to one coherent inner rail, not arbitrary front/back hood triangles.
    origin=rail[0,:-1];edge=rail[0,1:]-origin;den=np.sum(edge*edge,axis=1)
    if np.any(den<=0):raise ValueError('Neutral rail contains a zero-length segment')
    fraction=np.clip(np.einsum('nki,ki->nk',v[band,None]-origin[None],edge)/den,0,1);point=origin[None]+fraction[:,:,None]*edge[None];dist=np.linalg.norm(point-v[band,None],axis=2);segment=dist.argmin(1);frac=fraction[np.arange(len(band)),segment];neutral=point[np.arange(len(band)),segment];gap=dist[np.arange(len(band)),segment]
    posed=rail[:,segment]*(1-frac[None,:,None])+rail[:,segment+1]*frac[None,:,None];motion=np.linalg.norm(posed-neutral[None],axis=2).max(0)
    moving=(gap<=contact_tolerance)&(motion>=minimum_dynamic_motion)&~np.isin(ids[band],ids[static]);mi=np.flatnonzero(moving)
    if len(mi)<minimum_moving_roots or np.ptp(v[band[mi],1])<minimum_moving_span:raise ValueError('Insufficient measured moving-margin contact support')
    accessories=[]
    for group in accessory_groups:
        group=np.asarray(group)
        if group.ndim!=1 or not len(group) or not np.issubdtype(group.dtype,np.integer) or group.min()<0 or group.max()>=len(v):raise ValueError('Valid complete accessory component indices required')
        d,near=nearest_vertex(v[group],v[band]);take=np.flatnonzero(d<=contact_tolerance)
        if not len(take):raise ValueError('Accessory component has no measured band contact')
        accessories.append({'source_vertices':group[take],'carrier_vertices':band[near[take]],'neutral_gap':d[take]})
    return {'static_vertices':static,'static_carrier_vertices':static_carriers,
            'moving_vertices':band[mi],'moving_segments':segment[mi],'moving_fractions':frac[mi],
            'moving_neutral_carrier':neutral[mi],'moving_neutral_offset':v[band[mi]]-neutral[mi],
            'moving_gap':gap[mi],'moving_span':float(np.ptp(v[band[mi],1])),
            'incidental_or_moving_skin_contacts':skin_contacts[~(corner&front)],
            'accessories':accessories,'contact_tolerance':float(contact_tolerance),
            'working_frame':'+X front, Y lateral, +Z up',
            'classification_limit':'Geometric candidates require matched source-view review; no anatomical labels inferred solely from proximity.'}
