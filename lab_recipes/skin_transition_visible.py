# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Continuous attachment strips with explicit source-triangle provenance.

The input is a generated closed hood with already projected, fixed outer
vertices. A fixed vertex on skin does not imply that its adjacent edge lies on
skin. This helper certifies the complete edge, or replaces its contact boundary
with a measured source-surface route and adds a fixed transition strip. It never
changes source geometry. The caller supplies fitted tolerances and route limits.
"""
import numpy as np
from lab_recipes.skin_attachment import nearest_triangle_bindings, SkinSurfaceIndex, weld_identical_generated_trajectories
from lab_recipes.source_paths import SkinEdgeGraph
from lab_recipes.surface_routes import SkinTriangleGraph

def append_skin_transition_strips(poses,faces,ordered_boundary,source_vertices,
        source_faces,source_canonical_ids,skin_triangle_ids,
        source_sample_triangle_ids,source_sample_barycentric,*,
        attachment_tolerance,source_double_area_floor,route_padding,
        maximum_route_padding,route_depth_margin,maximum_route_length,segment_acceptance=None):
    p=np.asarray(poses,float);f=np.asarray(faces,int);boundary=np.asarray(ordered_boundary,int)
    sv=np.asarray(source_vertices,float);sf=np.asarray(source_faces,int);skin_ids=np.asarray(skin_triangle_ids,int)
    sample_ids=np.asarray(source_sample_triangle_ids,int);sample_bary=np.asarray(source_sample_barycentric,float)
    if p.ndim!=3 or p.shape[2]!=3 or f.ndim!=2 or f.shape[1]!=3 or not len(f) or not np.isfinite(p).all() or f.min()<0 or f.max()>=p.shape[1]:raise ValueError('Invalid generated hood')
    if boundary.ndim!=1 or len(boundary)<2 or boundary.min()<0 or boundary.max()>=p.shape[1] or sample_ids.shape!=(p.shape[1],) or sample_bary.shape!=(p.shape[1],3):raise ValueError('Boundary or sample-binding shape mismatch')
    if not np.array_equal(p[:,boundary],np.broadcast_to(p[0,boundary],p[:,boundary].shape)):raise ValueError('Input hood boundary must remain fixed at every control knot')
    limits=[attachment_tolerance,source_double_area_floor,route_padding,maximum_route_padding,route_depth_margin,maximum_route_length]
    if not np.isfinite(limits).all() or min(limits)<0 or maximum_route_padding<route_padding or maximum_route_length<=0:raise ValueError('Invalid input-fitted route limits')
    area=np.linalg.norm(np.cross(p[:,f[:,1]]-p[:,f[:,0]],p[:,f[:,2]]-p[:,f[:,0]]),axis=2)
    if np.any(area<=source_double_area_floor):raise ValueError('Generated core has a degenerate face; do not classify it as inherited source geometry')
    skin=sf[skin_ids];index=SkinSurfaceIndex(sv,skin);triangle_graph=SkinTriangleGraph(sv,skin,source_canonical_ids);edge_graph=SkinEdgeGraph(sv,skin,source_canonical_ids)
    bindings=nearest_triangle_bindings(p[0,boundary],sv,skin)
    if np.any(bindings['distance']>attachment_tolerance):raise ValueError('Fixed boundary vertices are not actually attached to source skin')
    newpoints=[];newfaces=[];outer_edges=[];point_samples=[];routes=[]
    for station,(ai,bi) in enumerate(zip(boundary[:-1],boundary[1:])):
        if ai==bi:continue
        a,b=p[0,[ai,bi]]
        if index.segment_coverage(a,b,attachment_tolerance)['covered'] and (segment_acceptance is None or segment_acceptance(a,b)):
            outer_edges.append((int(ai),int(bi)));continue
        start,end=map(int,bindings['triangle_indices'][station:station+2]);candidates=[]
        for padding in [route_padding,maximum_route_padding]:
            try:
                path=triangle_graph.route(a,b,start,end,padding=padding)['positions'];candidates.append(path);break
            except ValueError:pass
        try:candidates.append(edge_graph.route(a,b,skin[start],skin[end],minimum_x=min(a[0],b[0])-route_depth_margin)['positions'])
        except ValueError:pass
        certified=[]
        for path in candidates:
            keep=np.r_[True,np.linalg.norm(np.diff(path,axis=0),axis=1)>1e-12];path=path[keep]
            length=float(np.linalg.norm(np.diff(path,axis=0),axis=1).sum())
            if length<=maximum_route_length and all(index.segment_coverage(u,v,attachment_tolerance)['covered'] and (segment_acceptance is None or segment_acceptance(u,v)) for u,v in zip(path[:-1],path[1:])):certified.append((length,path))
        if not certified:raise ValueError('No bounded, continuously attached source-skin route was verified')
        length,path=min(certified,key=lambda x:x[0]);arc=np.r_[0,np.cumsum(np.linalg.norm(np.diff(path,axis=0),axis=1))]/length;chord=a+(b-a)*arc[:,None];pi=[int(ai)];qi=[int(ai)]
        for pp,qq in zip(path[1:-1],chord[1:-1]):
            pi.append(p.shape[1]+len(newpoints));newpoints.append(pp);point_samples.append(pp)
            qi.append(p.shape[1]+len(newpoints));newpoints.append(qq);point_samples.append(pp)
        pi.append(int(bi));qi.append(int(bi))
        for i in range(len(pi)-1):
            newfaces.extend([(qi[i],qi[i+1],pi[i+1]),(qi[i],pi[i+1],pi[i])]);outer_edges.append((pi[i],pi[i+1]))
        routes.append({'original_boundary_segment':station,'source_route_length':length,'source_surface_segments':len(pi)-1})
    if newpoints:
        p=np.concatenate([p,np.broadcast_to(np.asarray(newpoints),(len(p),len(newpoints),3))],axis=1)
        extra=nearest_triangle_bindings(point_samples,sv,skin);sample_ids=np.r_[sample_ids,skin_ids[extra['triangle_indices']]];sample_bary=np.vstack([sample_bary,extra['barycentric']])
    core_count=len(f)
    if newfaces:f=np.vstack([f,np.asarray(newfaces,int)])
    p=p.astype(np.float32).astype(float);clean=weld_identical_generated_trajectories(p,f);p=clean['poses'];f=clean['faces'];remap=clean['old_to_new']
    # Original core is already valid; only static zero-area added strip faces
    # can be discarded. A pose-dependent collapse always remains a failure.
    area=np.linalg.norm(np.cross(p[:,f[:,1]]-p[:,f[:,0]],p[:,f[:,2]]-p[:,f[:,0]]),axis=2);remove=np.all(area<=source_double_area_floor,axis=0);remove[:core_count]=False
    domains=np.r_[np.zeros(core_count,int),np.ones(len(f)-core_count,int)];f=f[~remove];domains=domains[~remove]
    if np.any(area[:,~remove]<=source_double_area_floor):raise ValueError('Attachment created a generated degenerate face')
    outer=remap[np.asarray(outer_edges,int)];outer=outer[outer[:,0]!=outer[:,1]]
    failed=[i for i,(a,b) in enumerate(outer) if not index.segment_coverage(p[0,a],p[0,b],attachment_tolerance)['covered'] or (segment_acceptance is not None and not segment_acceptance(p[0,a],p[0,b]))]
    if failed:raise ValueError('Float32 attachment boundary failed its complete-edge certificate')
    vertices=np.unique(outer);surface=nearest_triangle_bindings(p[0,vertices],sv,skin)
    return {'poses':p,'faces':f,'face_domains':domains,'skin_boundary_edges':outer,
        'skin_boundary_vertices':vertices,'boundary_source_triangle_ids':skin_ids[surface['triangle_indices']],
        'boundary_barycentric':surface['barycentric'],'source_sample_triangle_ids':sample_ids[clean['kept_vertex_indices']],
        'source_sample_barycentric':sample_bary[clean['kept_vertex_indices']],
        'old_to_new':remap,'routes':routes,'complete_edge_certificate_pass':True,
        'attachment_tolerance':float(attachment_tolerance),'generated_neutral_degenerates':0,
        'removed_fixed_zero_area_strip_faces':int(remove.sum()),'source_geometry_changed':False}
