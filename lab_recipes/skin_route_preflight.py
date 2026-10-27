# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Measure continuously attached routes on an explicit source-skin domain.

Anchor fitting and route connectivity are separate: orientation filters valid
for finding front anchors can remove legitimate folds from a source corridor.
This preflight changes no geometry or tolerance. It fits a length bound from
certified local source paths, not by repeatedly loosening a failed gate.
"""
import numpy as np
from lab_recipes.skin_attachment import SkinSurfaceIndex,nearest_triangle_bindings
from lab_recipes.surface_routes import SkinTriangleGraph
from lab_recipes.source_paths import SkinEdgeGraph


def measure_skin_route_requirements(boundary_positions,source_vertices,source_faces,
        canonical_ids,routing_triangle_ids,*,attachment_tolerance,route_padding,
        maximum_route_padding,route_depth_margin,segment_exterior_check=None):
    p=np.asarray(boundary_positions,float);v=np.asarray(source_vertices,float);f=np.asarray(source_faces);ids=np.asarray(routing_triangle_ids)
    if f.ndim!=2 or f.shape[1]!=3 or not len(f) or not np.issubdtype(f.dtype,np.integer) or f.min()<0 or f.max()>=len(v) or not np.issubdtype(ids.dtype,np.integer):raise ValueError('Integer source topology and routing triangle IDs required')
    limits=np.array([attachment_tolerance,route_padding,maximum_route_padding,route_depth_margin])
    if p.ndim!=2 or p.shape[1]!=3 or len(p)<2 or not np.isfinite(p).all() or not np.isfinite(limits).all() or (limits<0).any() or maximum_route_padding<route_padding:raise ValueError('Invalid boundary or route limits')
    if ids.ndim!=1 or not len(ids) or ids.min()<0 or ids.max()>=len(f):raise ValueError('Explicit routing skin triangle IDs required')
    skin=f[ids];index=SkinSurfaceIndex(v,skin);tg=SkinTriangleGraph(v,skin,canonical_ids);eg=SkinEdgeGraph(v,skin,canonical_ids);bind=nearest_triangle_bindings(p,v,skin)
    if bind['distance'].max()>attachment_tolerance:raise ValueError('Boundary vertices are not attached to routing skin')
    rows=[];required=0.
    for station,(a,b) in enumerate(zip(p[:-1],p[1:])):
        if index.segment_coverage(a,b,attachment_tolerance)['covered'] and (segment_exterior_check is None or segment_exterior_check(a,b)):
            rows.append({'station':station,'direct':True,'length':float(np.linalg.norm(b-a))});continue
        start,end=map(int,bind['triangle_indices'][station:station+2]);candidates=[]
        for padding in [route_padding,maximum_route_padding]:
            try:candidates.append(tg.route(a,b,start,end,padding=padding)['positions'])
            except ValueError:pass
        try:candidates.append(eg.route(a,b,skin[start],skin[end],minimum_x=min(a[0],b[0])-route_depth_margin)['positions'])
        except ValueError:pass
        valid=[]
        for path in candidates:
            path=path[np.r_[True,np.linalg.norm(np.diff(path,axis=0),axis=1)>1e-12]]
            direction=b-a;den=direction@direction;fractions=np.clip(((path-a)@direction)/den,0,1) if den else np.zeros(len(path));deviation=float(np.linalg.norm(path-a-fractions[:,None]*direction,axis=1).max())
            if deviation>maximum_route_padding or path[:,0].min()<min(a[0],b[0])-route_depth_margin:continue
            if not all(index.segment_coverage(u,w,attachment_tolerance)['covered'] for u,w in zip(path[:-1],path[1:])):continue
            if segment_exterior_check is not None and not all(segment_exterior_check(u,w) for u,w in zip(path[:-1],path[1:])):continue
            length=float(np.linalg.norm(np.diff(path,axis=0),axis=1).sum());valid.append((length,path,deviation))
        if not valid:raise ValueError('No certified local exterior skin route at boundary station '+str(station))
        length,path,deviation=min(valid,key=lambda x:x[0]);required=max(required,length);rows.append({'station':station,'direct':False,'length':length,'positions':path.tolist(),'maximum_chord_distance':deviation,'minimum_x':float(path[:,0].min()),'endpoint_minimum_x':float(min(a[0],b[0]))})
    return {'routes':rows,'required_maximum_route_length':float(np.nextafter(required,np.inf)),'attachment_tolerance':float(attachment_tolerance),'route_padding':float(route_padding),'maximum_route_padding':float(maximum_route_padding),'route_depth_margin':float(route_depth_margin),'boundary_vertex_max_distance':float(bind['distance'].max()),'source_geometry_changed':False}
