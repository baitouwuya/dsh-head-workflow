# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Fit generated neutral upper margins to whole original source lash bands."""
import numpy as np
from .neutral_band_rail import fit_tapered_neutral_band_rail,apply_neutral_rail_fit
from .blink_handoff import audit_linear_morph_segments


def fit_source_band_margins(source,boundaries,probes,roles,configuration,source_scale):
    scale=float(source_scale)
    if not np.isfinite(scale) or scale<=0:raise ValueError('Positive measured source scale required')
    v=np.asarray(source['vertices'],float)/scale;f=np.asarray(source['faces']);component=np.asarray(source['component']);knots=np.asarray(configuration['controls']['blink']['samples'],float);parameters=configuration.get('lashFit',{});result={k:np.asarray(x).copy() for k,x in boundaries.items()};reports={}
    for side,band_components in roles['lash_bands'].items():
        name=side+'-upper';band=np.flatnonzero(np.isin(component,band_components));bf=f[np.all(np.isin(component[f],band_components),axis=1)];inner=result[name+'_inner_rail_vertices'];poses=result[name+'_poses'];rail=poses[:,inner];points=np.asarray(probes[side+'_visible'])/scale;bounds=(points[:,1].min(),points[:,1].max());fit=fit_tapered_neutral_band_rail(rail[0],v,bf,bounds,taper_outer_fraction=parameters.get('outerTaperFraction',.1),taper_inner_fraction=parameters.get('innerTaperFraction',.25));new=apply_neutral_rail_fit(poses,result[name+'_construction_to_final_vertex_ids'],configuration['construction']['crossSectionSamples'],fit['positions'],inner,knots);basis=new[0].astype(np.float32);delta=(new-new[0]).astype(np.float32);new=(basis[None]+delta).astype(np.float32).astype(float);floor=(np.linalg.norm(np.ptp(v,axis=0))*np.finfo(np.float32).eps)**2;area=audit_linear_morph_segments(new[0],result[name+'_faces'],knots,new,source_double_area_floor=floor,collapse_area_ratio=1e-6);boundary=result[name+'_skin_boundary_vertices'];report={'source_band_vertices':len(band),'maximum_generated_neutral_refit':fit['maximum_refit_distance'],'outer_boundary_change':float(np.abs(new[:,boundary]-poses[:,boundary]).max()),'full_closed_encoding_change':float(np.abs(new[-1]-poses[-1]).max()),'interval_area_diagnostics':area,'original_source_geometry_changed':False,'contact_tolerances_changed':False,'acceptance':'Matched rendered blink motion; numerical results remain diagnostics'};reports[side]=report;result[name+'_poses']=new;result[name+'_neutral_band_source_triangle_ids']=np.flatnonzero(np.all(np.isin(component[f],band_components),axis=1))[fit['triangle_indices']];result[name+'_neutral_band_barycentric']=fit['barycentric'];result[name+'_neutral_band_taper_weights']=fit['taper_weights']
    return {'arrays':result,'report':reports}
