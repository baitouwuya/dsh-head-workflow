# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Array-side full-look preparation. No Blender, host access, or model export."""
from pathlib import Path
import json,math
import numpy as np


def validate_knots(values):
    a=np.asarray(values)
    if a.ndim!=1 or len(a)<2 or not np.issubdtype(a.dtype,np.number) or a.dtype.kind=='b' or not np.isfinite(a).all() or a[0]!=0 or a[-1]!=1 or not np.all(np.diff(a)>0):
        raise ValueError('Control knots must be finite, strictly increasing, from zero to one')
    return a.astype(float)


def sample_poses(poses,knots,value):
    knots=validate_knots(knots);p=np.asarray(poses,dtype=float)
    if p.shape[0]!=len(knots) or not np.isfinite(p).all() or isinstance(value,bool) or not isinstance(value,(int,float,np.floating)) or not math.isfinite(value) or not 0<=value<=1:
        raise ValueError('Invalid pose samples or control value')
    if value==1:return p[-1].copy()
    index=min(int(np.searchsorted(knots,value,side='right')-1),len(knots)-2);w=(value-knots[index])/(knots[index+1]-knots[index]);return p[index]*(1-w)+p[index+1]*w


def sample_rotations(rotations,knots,value):
    """Polar interpolation keeps supplied world-space rotations orthogonal."""
    raw=sample_poses(rotations,knots,value)
    if raw.ndim!=3 or raw.shape[1:]!=(3,3):raise ValueError('Rotation samples must be KxNx3x3')
    u,_,vh=np.linalg.svd(raw);out=u@vh;bad=np.linalg.det(out)<0
    if bad.any():u[bad,:,-1]*=-1;out=u@vh
    return out


def world_delta_to_local(delta_world,object_matrix_world):
    m=np.asarray(object_matrix_world,dtype=float)
    if m.shape!=(4,4) or not np.isfinite(m).all() or abs(np.linalg.det(m[:3,:3]))<1e-15:raise ValueError('Source object transform is not invertible')
    return np.asarray(delta_world)@np.linalg.inv(m[:3,:3]).T


def rotated_loop_normals_local(normals_local,loop_vertex_ids,rotations_world,object_matrix_world):
    """Rotate source loop normals in world space, then return to object local."""
    m=np.asarray(object_matrix_world,dtype=float)[:3,:3];n=np.asarray(normals_local,dtype=float)@np.linalg.inv(m)
    n=np.einsum('nij,nj->ni',rotations_world[np.asarray(loop_vertex_ids,dtype=int)],n)
    n=n@m;length=np.linalg.norm(n,axis=1)
    if not np.isfinite(n).all():raise ValueError('Invalid rotated source normals')
    valid=length>0;n[valid]/=length[valid,None]
    # Blender uses an inherited zero custom normal as an auto-normal sentinel.
    # Keep that sentinel; it is not a newly introduced invalid surface normal.
    n[~valid]=0
    return n


def low_frequency_skin_field(reference_yz,reference_rgba,query_yz):
    """Fit a robust first-order skin colour field, independent of mesh density.

    This intentionally does not retain boundary pigment. Outlier rejection is an
    appearance heuristic, not semantic proof that every rejected sample is ink.
    The same spatial samples produce the same field for upper and lower lids.
    """
    yz=np.asarray(reference_yz,dtype=float);rgba=np.asarray(reference_rgba,dtype=float);q=np.asarray(query_yz,dtype=float)
    if yz.ndim!=2 or yz.shape[1:]!=(2,) or len(yz)<3 or rgba.shape!=(len(yz),4) or q.ndim!=2 or q.shape[1:]!=(2,) or not np.isfinite(yz).all() or not np.isfinite(rgba).all() or not np.isfinite(q).all() or (rgba<0).any() or (rgba>1).any():
        raise ValueError('Finite reference YZ/RGBA and query YZ arrays required')
    rgb=rgba[:,:3];lum=rgb@np.array([.2126,.7152,.0722]);median=np.median(rgb,axis=0);lm=float(np.median(lum));mad=float(np.median(abs(lum-lm)))
    # Large dark excursions are not allowed to become painted stripes. Skin
    # shading/chroma outliers are reported honestly along with this heuristic.
    dark=lum < lm-max(3*mad,.22*lm)
    residual=np.linalg.norm(rgb-median,axis=1);rm=float(np.median(residual));rd=float(np.median(abs(residual-rm)))
    unusual=residual>rm+max(4*rd,.15)
    keep=~(dark|unusual)
    if keep.sum()<3:raise ValueError('Insufficient source skin samples after robust appearance filtering')
    center=np.median(yz[keep],axis=0);span=np.ptp(yz[keep],axis=0);span=np.where(span>1e-10,span,1.)
    x=(yz-center)/span;query=(q-center)/span
    # Spatial cells prevent densely tessellated source patches dominating a fit.
    bins=np.floor(x[keep]*12).astype(int);_,inverse,counts=np.unique(bins,axis=0,return_inverse=True,return_counts=True)
    a=np.c_[np.ones(keep.sum()),x[keep]];b=rgb[keep];base=1/counts[inverse];weights=base.copy();penalty=np.diag([0,1e-5,1e-5])
    coef=np.zeros((3,3));coef[0]=np.median(b,axis=0)
    rank=int(np.linalg.matrix_rank(a))
    if rank==3:
        for _ in range(6):
            coef=np.linalg.solve(a.T@(weights[:,None]*a)+penalty,a.T@(weights[:,None]*b))
            error=np.linalg.norm(a@coef-b,axis=1);sigma=max(float(np.median(error))*1.4826,1e-4);weights=base*np.minimum(1.,1.5*sigma/np.maximum(error,1e-12))
    predicted=np.c_[np.ones(len(q)),query]@coef
    # A plane is smooth; bounding by retained reference quantiles prevents
    # extrapolation changing hue or producing artificial highlights at canthi.
    low=np.quantile(b,.05,axis=0);high=np.quantile(b,.95,axis=0);bounded=np.clip(predicted,low,high)
    return {'colors_linear_rgba':np.c_[bounded,np.ones(len(q))].astype(np.float32),'report':{
        'reference_count':len(yz),'retained_reference_count':int(keep.sum()),'dark_reference_outlier_count':int(dark.sum()),'other_reference_outlier_count':int((unusual&~dark).sum()),
        'reference_linear_rgb_variance_before':np.var(rgb,axis=0).tolist(),'reference_linear_rgb_variance_retained':np.var(b,axis=0).tolist(),
        'reference_median_linear_rgb':median.tolist(),'retained_luminance_range':[float(lum[keep].min()),float(lum[keep].max())],
        'fit_rank':rank,'fit_kind':'robust spatially balanced affine YZ field' if rank==3 else 'robust median fallback for rank-deficient samples',
        'coefficient_rows_constant_y_z':coef.tolist(),'bounded_output_vertex_count':int(np.any(abs(predicted-bounded)>1e-8,axis=1).sum()),
        'boundary_pigment_constraint':False,'interpretation':'Rejected dark/color outliers are appearance heuristics; original source pigment and geometry remain unchanged'}}


def prepare_skin_fields(source,lids,roles,lid_specs,image_rgb,uv_origin,material_index,material_scalars,scale,repo_root,visual_color_mode='measured_boundary'):
    """Reuse the tested appearance/normal helpers on this runtime's own arrays.

    Face IDs here refer to the measured input, never a fixed exporter ordering.
    Appearance diagnostics are reported; they are not visual acceptance gates.
    """
    import sys
    sys.path.insert(0,str(repo_root))
    from lab_recipes.aperture_contract import construction_envelope_from_samples
    from lab_recipes.skin_attachment import nearest_triangle_bindings
    from lab_recipes.skin_appearance import transfer_skin_colors,interpolate_skin_color_strip,blend_skin_boundary_colors
    from lab_recipes.lid_normals import split_generated_shading_domains
    vertices=np.asarray(source['vertices'])/scale;faces=source['faces'];component=source['component'];uv=source['uv_0'];uv_faces=source['triangle_loops']
    skin_role=roles['skin_component'];skin_roles=skin_role if isinstance(skin_role,list) else [skin_role]
    skin=np.flatnonzero(np.all(np.isin(component[faces],skin_roles),axis=1))
    if 'triangle_material_ids' in source:skin=skin[np.asarray(source['triangle_material_ids'])[skin]==material_index]
    if not len(skin):raise ValueError('No measured source-skin triangles use the selected appearance material')
    if visual_color_mode not in ('measured_boundary','low_frequency_skin'):raise ValueError('Unknown visual_color_mode')
    result=[];reports=[];side_references={}
    def inside(q,rim):
        yz=np.asarray(rim)[:,1:];e=np.roll(yz,-1,axis=0)-yz;d=q[:,None,:]-yz;c=e[None,:,0]*d[:,:,1]-e[None,:,1]*d[:,:,0];return np.all(c>=-1e-12,axis=1)|np.all(c<=1e-12,axis=1)
    for spec in lid_specs:
        prefix=spec['array_prefix'];side=spec['control'];poses=np.asarray(lids[prefix+'_poses']);f=lids[prefix+'_faces'];tri=lids[prefix+'_source_sample_triangle_ids'];bary=lids[prefix+'_source_sample_barycentric'];boundary=np.asarray(lids.get(prefix+'_skin_boundary_vertices',[]),dtype=int);inner=np.asarray(lids.get(prefix+'_inner_rail_vertices',[]),dtype=int);warnings=[]
        if spec.get('normal_mode') not in (None,'posed','source_static'):raise ValueError('Unknown normal_mode')
        if visual_color_mode=='measured_boundary' and (not len(boundary) or not len(inner)):raise ValueError('Measured-boundary mode requires source boundary and inner rail indices')
        raw=transfer_skin_colors(uv_faces,uv,image_rgb,tri,bary,skin,material_scalars,uv_origin=uv_origin)
        color=raw['colors_linear_rgba'];clean_report=None
        # This envelope is an appearance exclusion area, not an anatomical rim.
        parts=list(roles['eye_components'][side])+list(roles['lash_bands'][side])+list(roles.get('lash_accessories',{}).get(side,[]))
        rim=construction_envelope_from_samples(vertices[np.isin(component,parts)])
        outside=~inside(vertices[:,1:],rim);allowed=skin[np.all(outside[faces[skin]],axis=1)]
        if visual_color_mode=='low_frequency_skin':
            if side not in side_references:
                # Nearby actual source skin, outside the projected eye/lash
                # envelope. Do not use new geometry colours as reference data.
                c=vertices[faces[allowed]].mean(axis=1);rmin=np.min(rim,axis=0);rmax=np.max(rim,axis=0);mid=(rmin+rmax)/2;extent=np.maximum(rmax-rmin,1e-6)
                local=(abs(c[:,1]-mid[1])<=extent[1]*.9)&(abs(c[:,2]-mid[2])<=extent[2]*1.5)&(abs(c[:,0]-mid[0])<=max(extent[1],extent[2])*.7)
                selected=allowed[local]
                if len(selected)<6:raise ValueError('Insufficient nearby source skin outside eye/lash exclusion for low-frequency colour')
                weights=np.full((len(selected),3),1/3);reference=transfer_skin_colors(uv_faces,uv,image_rgb,selected,weights,selected,material_scalars,uv_origin=uv_origin)
                side_references[side]=(vertices[faces[selected]].mean(axis=1)[:,1:],reference['colors_linear_rgba'])
            ref_yz,ref_rgba=side_references[side];field=low_frequency_skin_field(ref_yz,ref_rgba,poses[0,:,1:]);previous=color;color=field['colors_linear_rgba'];clean_report=field['report']
            clean_report['replaced_bound_color_vertex_count']=int(np.any(abs(color-previous)>1e-4,axis=1).sum())
            clean_report['boundary_color_max_change']=float(abs(color[boundary]-previous[boundary]).max()) if len(boundary) else None
            clean_report['direct_bound_dark_vertex_count']=int(((previous[:,:3]@np.array([.2126,.7152,.0722]))<.25*np.median(ref_rgba[:,:3]@np.array([.2126,.7152,.0722]))).sum())
        elif len(allowed):
            border=poses[0,boundary];ys=np.unique(border[:,1]);stations=np.array([[np.median(border[border[:,1]==y,0]),y,np.median(border[border[:,1]==y,2])] for y in ys]);count=max(3,len(inner)+2);qy=np.linspace(poses[0,:,1].min(),poses[0,:,1].max(),count);query=np.c_[np.interp(qy,ys,stations[:,0]),qy,np.interp(qy,ys,stations[:,2])]
            bind=nearest_triangle_bindings(query,vertices,faces[allowed]);reference=transfer_skin_colors(uv_faces,uv,image_rgb,allowed[bind['triangle_indices']],bind['barycentric'],allowed,material_scalars,uv_origin=uv_origin)
            field=interpolate_skin_color_strip(qy,reference['colors_linear_rgba'],poses[0,:,1]);blend=blend_skin_boundary_colors(poses[0],f,boundary,inner,color,field['colors_linear_rgba']);color=blend['colors_linear_rgba'];clean_report={'reference_samples':len(query),'references_inside_exclusion':int(inside(bind['positions'][:,1:],rim).sum()),'parameter_clamps':field['clamped_query_count'],'boundary_color_error':float(abs(color[boundary]-raw['colors_linear_rgba'][boundary]).max())}
        else:warnings.append('No outside-envelope clean-skin reference; rendered direct bound skin colors')
        for domain in split_generated_shading_domains(poses,f,lids[prefix+'_face_domains'])['domains']:
            used=domain['source_vertex_indices'];result.append({'id':spec['id']+'-domain-'+str(domain['domain_id']),'lid_id':spec['id'],'control':side,'domain':domain['domain_id'],'normal_mode':spec.get('normal_mode') or ('source_static' if domain['domain_id']==1 else 'posed'),'poses':domain['poses'],'faces':domain['faces'],'colors':color[used],'source_triangle_ids':np.asarray(tri)[used],'source_barycentric':np.asarray(bary)[used],'material':raw['material']})
        reports.append({'lid':spec['id'],'generated_vertices':len(poses[0]),'visual_color_mode':visual_color_mode,'clean_color_field':clean_report,'warnings':warnings,'appearance_decision':'Requires textured motion review; diagnostics do not accept or reject the candidate'})
    return result,reports


def load_request(path):
    request=json.loads(Path(path).read_text());validate_knots(request['knots'])
    if not isinstance(request['source_scale'],(int,float)) or isinstance(request['source_scale'],bool) or not math.isfinite(request['source_scale']) or request['source_scale']<=0:raise ValueError('Measured source_scale must be positive')
    cycle=request['cycle_values']
    if not isinstance(cycle,list) or len(cycle)<3 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in cycle) or cycle[0]!=0 or cycle[-1]!=0 or 1 not in cycle:raise ValueError('Review cycle must include opening, full closure and reopening')
    if request.get('mode') not in ('host_precheck','native_stage_build'):raise ValueError('Declare host_precheck or native_stage_build; host is never final acceptance')
    if not request.get('lids') or not request.get('source_controls') or not request.get('views') or not request.get('scenarios'):raise ValueError('Runtime lids, controls, views and scenarios are required')
    return request
