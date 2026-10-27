# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Required exterior-sheet fitting and continuous source-skin attachment.

The source is immutable. The caller supplies measured candidate skin faces,
aperture and displacement limits. All visibility comparisons use the complete
source skin domain, never only the restricted fitting/routing domain.
"""
import numpy as np
from lab_recipes.skin_attachment import transition_outer_boundary,weld_identical_generated_trajectories,nearest_triangle_bindings
from .frontmost_skin import frontmost_skin_triangle_ids,fit_frontmost_skin_anchors,FrontmostSkinIndex
from .skin_route_preflight import measure_skin_route_requirements
from .skin_transition_visible import append_skin_transition_strips


def _cross(a,b):return a[0]*b[1]-a[1]*b[0]

def aperture_overlap_area(triangle_yz,aperture_yz):
    polygon=[np.asarray(p,float) for p in triangle_yz];hull=np.asarray(aperture_yz,float)
    if sum(_cross(a,b) for a,b in zip(hull,np.roll(hull,-1,axis=0)))<0:hull=hull[::-1]
    for a,b in zip(hull,np.roll(hull,-1,axis=0)):
        if not polygon:break
        result=[];edge=b-a
        for u,w in zip(polygon,polygon[1:]+polygon[:1]):
            du=_cross(edge,u-a);dw=_cross(edge,w-a);inside_u=du>=-1e-12;inside_w=dw>=-1e-12
            if inside_u:result.append(u)
            if inside_u!=inside_w:result.append(u+(w-u)*du/(du-dw))
        polygon=result
    return 0. if len(polygon)<3 else abs(sum(_cross(a,b) for a,b in zip(polygon,polygon[1:]+polygon[:1])))/2


def exterior_skin_domains(vertices,faces,skin_triangle_ids,candidate_triangle_ids,aperture_rim,*,visibility_tolerance):
    v=np.asarray(vertices,float);f=np.asarray(faces,int);rim=np.asarray(aperture_rim,float)
    from lab_recipes.aperture_contract import validate_ordered_rim
    validate_ordered_rim(rim)
    visible=frontmost_skin_triangle_ids(v,f,skin_triangle_ids,candidate_triangle_ids,depth_tolerance=visibility_tolerance)
    outside=np.array([i for i in visible['triangle_ids'] if aperture_overlap_area(v[f[i],1:],rim[:,1:])<=1e-14],int)
    if not len(outside):raise ValueError('No fully exterior source skin supports this aperture')
    center=v[f[outside]].mean(1);mid=(rim[:,2].min()+rim[:,2].max())/2
    return {'routing_triangle_ids':outside,'upper_triangle_ids':outside[center[:,2]>=mid],'lower_triangle_ids':outside[center[:,2]<=mid],'candidate_count':len(candidate_triangle_ids),'visible_count':len(visible['triangle_ids'])}


def fit_exterior_skin_boundary(poses,faces,anchor_vertices,ordered_boundary,inner_rail_vertices,cross_section_samples,
        source_vertices,source_faces,source_canonical_ids,skin_triangle_ids,candidate_triangle_ids,aperture_rim,upper,*,
        attachment_tolerance,source_double_area_floor,maximum_anchor_refit,maximum_lateral_vertical_refit,
        route_padding,maximum_route_padding,route_depth_margin,maximum_route_length):
    """Mandatory exterior gate wraps construction; there is no omit-callback path."""
    raw_faces=np.asarray(faces);raw_indices=[np.asarray(x) for x in [anchor_vertices,ordered_boundary,inner_rail_vertices]]
    if not np.issubdtype(raw_faces.dtype,np.integer) or any(x.ndim!=1 or not len(x) or not np.issubdtype(x.dtype,np.integer) for x in raw_indices):raise ValueError('Integer generated topology and binding indices required')
    p=np.asarray(poses,float)
    if p.ndim!=3 or p.shape[0]<2 or p.shape[2]!=3 or not np.isfinite(p).all() or raw_faces.ndim!=2 or raw_faces.shape[1]!=3 or not len(raw_faces) or raw_faces.min()<0 or raw_faces.max()>=p.shape[1] or any(x.min()<0 or x.max()>=p.shape[1] for x in raw_indices):raise ValueError('Valid finite generated trajectories required')
    f=np.asarray(faces,int);v=np.asarray(source_vertices,float);sf=np.asarray(source_faces,int);anchors=np.asarray(anchor_vertices,int);ordered=np.asarray(ordered_boundary,int);inner=np.asarray(inner_rail_vertices,int);rim=np.asarray(aperture_rim,float)
    if not np.isfinite([maximum_anchor_refit,maximum_lateral_vertical_refit]).all() or min(maximum_anchor_refit,maximum_lateral_vertical_refit)<0:raise ValueError('Explicit finite refit limits required')
    domains=exterior_skin_domains(v,sf,skin_triangle_ids,candidate_triangle_ids,rim,visibility_tolerance=attachment_tolerance);selected=domains['upper_triangle_ids' if upper else 'lower_triangle_ids'];routing=domains['routing_triangle_ids']
    if not len(selected):raise ValueError('No exterior skin supports the requested lid side')
    bound=fit_frontmost_skin_anchors(p[0,anchors],v,sf,selected,skin_triangle_ids);shift=bound['positions']-p[0,anchors];movement=float(np.linalg.norm(shift,axis=1).max());yz_movement=float(np.linalg.norm(shift[:,1:],axis=1).max())
    if movement>maximum_anchor_refit or yz_movement>maximum_lateral_vertical_refit:raise ValueError('Exterior anchor refit exceeds declared displacement limit')
    attached=transition_outer_boundary(p,anchors,bound['positions'],cross_section_samples);clean=weld_identical_generated_trajectories(attached,f);pnew=clean['poses'];fnew=clean['faces'];ordered=clean['old_to_new'][ordered];inner=clean['old_to_new'][inner];visibility=FrontmostSkinIndex(v,sf,skin_triangle_ids)
    def exterior(a,b):
        if not visibility.segment_frontmost(a,b,attachment_tolerance)['frontmost']:return False
        ts=[0.,1.]
        if abs(b[1]-a[1])>1e-14:ts +=[(y-a[1])/(b[1]-a[1]) for y in rim[:,1] if min(a[1],b[1])<y<max(a[1],b[1])]
        for q in a+np.array(ts)[:,None]*(b-a):
            zs=[]
            for u,w in zip(rim,np.roll(rim,-1,axis=0)):
                if abs(w[1]-u[1])>1e-14 and min(u[1],w[1])-1e-12<=q[1]<=max(u[1],w[1])+1e-12:zs.append(u[2]+(q[1]-u[1])/(w[1]-u[1])*(w[2]-u[2]))
            if zs and (q[2]<max(zs)-attachment_tolerance if upper else q[2]>min(zs)+attachment_tolerance):return False
        return True
    route_limits={'attachment_tolerance':attachment_tolerance,'route_padding':route_padding,'maximum_route_padding':maximum_route_padding,'route_depth_margin':route_depth_margin}
    preflight=measure_skin_route_requirements(pnew[0,ordered],v,sf,source_canonical_ids,routing,segment_exterior_check=exterior,**route_limits)
    if preflight['required_maximum_route_length']>maximum_route_length:raise ValueError('Measured exterior source route exceeds the declared length bound')
    samples=nearest_triangle_bindings(pnew[0],v,sf[selected]);result=append_skin_transition_strips(pnew,fnew,ordered,v,sf,source_canonical_ids,routing,selected[samples['triangle_indices']],samples['barycentric'],source_double_area_floor=source_double_area_floor,maximum_route_length=maximum_route_length,segment_acceptance=exterior,**route_limits)
    result['post_initial_weld_to_final_vertex_ids']=result['old_to_new'].copy();result['construction_to_final_vertex_ids']=result['old_to_new'][clean['old_to_new']];after_shift=result['poses'][0,result['construction_to_final_vertex_ids'][anchors]]-np.asarray(poses)[0,anchors];result['inner_rail_vertices']=result['old_to_new'][inner];result['exterior_certificate_required']=True;result['refit_report']={'maximum_anchor_displacement':movement,'maximum_anchor_displacement_after_float32':float(np.linalg.norm(after_shift,axis=1).max()),'maximum_lateral_vertical_displacement_after_float32':float(np.linalg.norm(after_shift[:,1:],axis=1).max()),'contact_topology':'Fixed geometric core-strip contact with T-junction subdivisions; not welded or watertight','maximum_lateral_vertical_displacement':yz_movement,'maximum_anchor_refit_limit':float(maximum_anchor_refit),'maximum_lateral_vertical_refit_limit':float(maximum_lateral_vertical_refit),'source_geometry_changed':False,'inner_rail_maximum_change':float(np.abs(result['poses'][:,result['inner_rail_vertices']]-np.asarray(poses)[:,inner_rail_vertices]).max()),'required_route_length':preflight['required_maximum_route_length'],'declared_route_length_limit':float(maximum_route_length),'fitting_triangles':len(selected),'routing_triangles':len(routing),'generated_neutral_coincident_vertices_welded':clean['merged_vertices']};return result
