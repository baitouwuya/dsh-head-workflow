# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Original whole-band/accessory animation; measurements inform visual review."""
import numpy as np
from .lash_contacts import classify_lash_contacts
from .skin_attachment import nearest_triangle_bindings
from .lash_transfer import RigidLashCurveBinding,audit_lash_edge_strain
from .anchored_lash import AnchoredLashBinding
from .blink_handoff import audit_linear_morph_segments


def roll_ribbon_target(target,neutral_points,neutral_rail,posed_rail,lateral_bounds,angle):
    if not np.isfinite(angle):raise ValueError('Finite runtime ribbon roll required')
    if angle==0:return target
    lo,hi=lateral_bounds;origin=neutral_rail[:-1];edge=neutral_rail[1:]-origin;den=np.sum(edge[:,1:]**2,axis=1);fraction=np.clip(np.einsum('nki,ki->nk',neutral_points[:,None,1:]-origin[None,:,1:],edge[:,1:])/den,0,1);q=origin[None]+fraction[:,:,None]*edge[None];distance=np.linalg.norm(q[:,:,1:]-neutral_points[:,None,1:],axis=2);segment=distance.argmin(1);frac=fraction[np.arange(len(target)),segment];pivot=posed_rail[segment]*(1-frac[:,None])+posed_rail[segment+1]*frac[:,None];axis=posed_rail[segment+1]-posed_rail[segment];axis/=np.linalg.norm(axis,axis=1)[:,None];station=(neutral_points[:,1]-lo)/(hi-lo);u=np.clip(np.minimum(station/.25,(1-station)/.25),0,1);theta=angle*(u*u*(3-2*u));offset=target-pivot;cs=np.cos(theta)[:,None];sn=np.sin(theta)[:,None];return pivot+cs*offset+sn*np.cross(axis,offset)+(1-cs)*axis*np.sum(axis*offset,axis=1)[:,None]


def audit_new_skin_occlusion(neutral_vertices,skin_triangles,band_indices,posed_vertices,*,tolerance=1e-6):
    from .visual_front_surface import front_depth
    v=np.asarray(neutral_vertices,float);band=np.asarray(band_indices,int);poses=np.asarray(posed_vertices,float)
    if not np.isfinite(tolerance) or tolerance<0:raise ValueError('Finite nonnegative occlusion diagnostic tolerance required')
    before=front_depth(v[band],v,skin_triangles)-v[band,0];baseline=before>tolerance;rows=[]
    for p in poses:
        depth=front_depth(p[band],v,skin_triangles)-p[band,0];hidden=depth>tolerance;new=hidden&~baseline;rows.append({'hidden_band_vertices':int(hidden.sum()),'newly_hidden_band_vertices':int(new.sum()),'maximum_new_depth_behind_skin':float(depth[new].max()) if new.any() else 0.})
    return {'band_vertices':len(band),'neutral_hidden_band_vertices':int(baseline.sum()),'tolerance':float(tolerance),'samples':rows,'interpretation':'Actual source-skin depth occlusion; not a topology break or an acceptance gate.'}


def build_original_lash_motion(source,lid_arrays,probes,roles,configuration,source_scale):
    s=source;g=lid_arrays;pr=probes;cfg=configuration;scale=float(source_scale);parameters=cfg.get('lashFit',{});v=np.asarray(s['vertices'],float)/scale;f=np.asarray(s['faces']);co=np.asarray(s['component']);knots=cfg['controls']['blink']['samples'];out={};reports={};floor=(np.linalg.norm(np.ptp(v,axis=0))*np.finfo(np.float32).eps)**2
    for side,bands in roles['lash_bands'].items():
        band=np.flatnonzero(np.isin(co,bands));index=np.full(len(v),-1,int);index[band]=np.arange(len(band));faces=index[f[np.all(np.isin(co[f],bands),axis=1)]];points=pr[side+'_visible']/scale;height=np.ptp(points[:,2]);width=np.ptp(points[:,1]);rail=g[side+'-upper_poses'][:,g[side+'-upper_inner_rail_vertices']];skin=np.unique(pr[side+'_exterior_skin_face_ids']);access=[np.flatnonzero(co==c) for c in roles['lash_accessories'][side]];limits=dict(contact_tolerance=cfg['verification']['lashContactLimitRelativeToMeasuredApertureHeight']*height,corner_fraction=.2,minimum_front_normal_x=0.,minimum_dynamic_motion=.01*height,minimum_moving_roots=3,minimum_moving_span=.5*width);contacts=classify_lash_contacts(v,f,s['canonical_vertex_ids'],band,skin,access,rail,(points[:,1].min(),points[:,1].max()),query_nearest_triangles=nearest_triangle_bindings,support_diagnostics_only=True,**limits);fixed=np.unique(np.r_[index[contacts['static_vertices']],index[contacts['moving_vertices']]]);moving_pos=np.searchsorted(fixed,index[contacts['moving_vertices']]);segments=contacts['moving_segments'];fractions=contacts['moving_fractions'];offset=contacts['moving_neutral_offset'];binding=RigidLashCurveBinding(v[band],rail[0],influence_radius=height*parameters.get('curveInfluenceOverApertureHeight',.25));solver=AnchoredLashBinding(v[band],faces,fixed,target_strength=parameters.get('targetStrength',.001),max_iterations=parameters.get('maximumIterations',512),convergence_tolerance=parameters.get('convergenceTolerance',1e-7),maximum_vertices=parameters.get('maximumCanonicalVertices',1024));poses=np.repeat(v[None],len(knots),axis=0);rotations=np.broadcast_to(np.eye(3),(len(knots),len(v),3,3)).copy();steps=[]
        for k in range(len(knots)):
            target=binding.evaluate(rail[k]);target=roll_ribbon_target(target,v[band],rail[0],rail[k],(points[:,1].min(),points[:,1].max()),parameters.get('ribbonRollRadians',0.)*knots[k]);carrier=v[band[fixed]].copy()
            if k:carrier[moving_pos]=rail[k,segments]*(1-fractions[:,None])+rail[k,segments+1]*fractions[:,None]+offset
            p,rotation=solver.evaluate(target,carrier_points=carrier);poses[k,band]=v[band]+(p-v[band]).astype(np.float32);rotations[k,band]=rotation;steps.append(dict(value=knots[k],**solver.last_report))
        accessory_reports=[]
        for group,contact in zip(access,contacts['accessories']):
            local=np.full(len(v),-1,int);local[group]=np.arange(len(group));af=local[f[np.all(np.isin(f,group),axis=1)]];fixedlocal=local[contact['source_vertices']];parent=contact['carrier_vertices'];delta=v[contact['source_vertices']]-v[parent];a_solver=AnchoredLashBinding(v[group],af,fixedlocal,target_strength=parameters.get('targetStrength',.001),max_iterations=parameters.get('accessoryMaximumIterations',256),convergence_tolerance=parameters.get('convergenceTolerance',1e-7),maximum_vertices=parameters.get('maximumCanonicalVertices',1024));areport=[]
            for k in range(len(knots)):
                parentR=rotations[k,parent];carriers=poses[k,parent]+np.einsum('nij,nj->ni',parentR,delta);center=v[parent].mean(0);newcenter=poses[k,parent].mean(0);u,_,vt=np.linalg.svd(parentR.mean(0));rotation=u@vt;target=(v[group]-center)@rotation.T+newcenter
                if k==0:target=v[group].copy();carriers=v[contact['source_vertices']].copy()
                p,rr=a_solver.evaluate(target,carrier_points=carriers);poses[k,group]=v[group]+(p-v[group]).astype(np.float32);rotations[k,group]=rr;areport.append(dict(value=knots[k],**a_solver.last_report))
            accessory_reports.append({'vertices':len(group),'roots':len(fixedlocal),'solver':areport})
        moved=np.r_[band,*access];mfaces=f[np.all(np.isin(f,moved),axis=1)];ia=audit_linear_morph_segments(v,mfaces,knots,poses,source_double_area_floor=floor,collapse_area_ratio=1e-6);strain=[audit_lash_edge_strain(v,pp,mfaces,minimum_edge_length=1e-10,minimum_ratio=.5,maximum_ratio=1.6) for pp in poses];rootgaps=[]
        for k in range(len(knots)):
            movingcarrier=rail[k,segments]*(1-fractions[:,None])+rail[k,segments+1]*fractions[:,None];rootgaps.append(float(np.linalg.norm(poses[k,contacts['moving_vertices']]-movingcarrier,axis=1).max()) if len(segments) else None)
        out[side+'_source_poses']=poses;out[side+'_source_rotations']=rotations;reports[side]={'band_vertices':len(band),'moving_contacts':len(contacts['moving_vertices']),'support_diagnostics':contacts['support_diagnostics'],'moving_span':contacts['moving_span'],'static_contacts':len(contacts['static_vertices']),'moving_root_gap_by_knot':rootgaps,'band_solver':steps,'accessories':accessory_reports,'strain':strain,'continuous_area':ia,'neutral_source_error':float(abs(poses[0]-v).max()),'protected_source_error':float(abs(poses[:,np.setdiff1d(np.arange(len(v)),moved)]-v[np.setdiff1d(np.arange(len(v)),moved)]).max()),'numeric_results_are_diagnostics_visual_motion_is_acceptance':True,'source_skin_occlusion':audit_new_skin_occlusion(v,f[co[f[:,0]]==roles['skin_component']],band,poses,tolerance=parameters.get('skinOcclusionDiagnosticTolerance',1e-6))}
    return {"arrays":out,"report":reports}
