# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Read-only whole-segment certificate for fixed geometric T-junction contact.

For each inner strip edge, both endpoints lie within tolerance of the SAME
original core edge. The tolerance capsule of a segment is convex, so the entire
inner edge lies inside it. Both geometries must be exactly fixed at all knots;
LINEAR interpolation then leaves them fixed over every complete control interval.
This makes no manifold, watertight or source-skin attachment claim.
"""
from collections import Counter
import numpy as np

def edge_counts(faces):
    return Counter(tuple(sorted(map(int,e))) for face in faces for e in zip(face,np.roll(face,-1)))

def audit_fixed_core_strip_contact(data,configuration,tolerance=1e-6):
    if not np.isfinite(tolerance) or tolerance<0:raise ValueError('Invalid tolerance')
    construction=configuration['construction'];n=construction['lengthSegments'];m=construction['crossSectionSamples']
    knots=np.asarray(configuration['controls']['blink']['samples'],float)
    if len(knots)<2 or not np.isfinite(knots).all() or np.any(np.diff(knots)<=0):raise ValueError('Invalid control knots')
    original=np.r_[(n-1)*m,np.arange(n-1)*m+m//4,(n-1)*m+1]
    report={}
    names=sorted(k[:-6] for k in data.keys() if k.endswith('_poses'))
    if not names:raise ValueError('No required lid geometry')
    for name in names:
        p=data[name+'_poses'];faces=data[name+'_faces'];domains=data[name+'_face_domains'];mapping=data[name+'_construction_to_final_vertex_ids']
        if p.ndim!=3 or p.shape[0]!=len(knots) or p.shape[2]!=3 or not np.isfinite(p).all():raise ValueError('Invalid poses '+name)
        if faces.ndim!=2 or faces.shape[1]!=3 or not np.issubdtype(faces.dtype,np.integer) or faces.min()<0 or faces.max()>=p.shape[1]:raise ValueError('Invalid faces '+name)
        core=faces[domains==0];strip=faces[domains==1]
        if not len(core) or not len(strip):raise ValueError('Empty required core or strip '+name)
        core_counts=edge_counts(core);strip_counts=edge_counts(strip)
        outer={tuple(sorted(map(int,e))) for e in data[name+'_skin_boundary_edges']}
        inner=np.array([e for e,count in strip_counts.items() if count==1 and e not in outer],int)
        if not len(inner):raise ValueError('Empty strip contact boundary '+name)
        ordered=mapping[original];refs=np.c_[ordered[:-1],ordered[1:]];refs=refs[refs[:,0]!=refs[:,1]]
        if not len(refs):raise ValueError('Empty original core boundary '+name)
        refs_exist=all(tuple(sorted(map(int,e))) in core_counts for e in refs)
        a=p[0,refs[:,0]];direction=p[0,refs[:,1]]-a;den=np.einsum('ij,ij->i',direction,direction)
        if np.any(den<=0):raise ValueError('Degenerate core reference edge '+name)
        witnesses=[];assignments=[]
        for edge in inner:
            q=p[0,edge]
            t=np.clip(np.einsum('kij,ij->ki',q[:,None,:]-a[None,:,:],direction)/den,0,1)
            distance=np.linalg.norm(q[:,None,:]-(a[None,:,:]+t[:,:,None]*direction[None,:,:]),axis=2)
            index=int(np.argmin(distance.max(0)));bound=float(distance[:,index].max())
            assignments.append(index)
            witnesses.append({'strip_edge':edge.tolist(),'core_edge':refs[index].tolist(),'whole_segment_distance_upper_bound':bound,'core_parameters':t[:,index].tolist()})
        referenced=refs[np.unique(assignments)];contact_vertices=np.unique(inner)
        fixed_strip=bool(np.array_equal(p[:,contact_vertices],np.broadcast_to(p[0,contact_vertices],p[:,contact_vertices].shape)))
        fixed_core=bool(np.array_equal(p[:,np.unique(referenced)],np.broadcast_to(p[0,np.unique(referenced)],p[:,np.unique(referenced)].shape)))
        bound=max(row['whole_segment_distance_upper_bound'] for row in witnesses)
        # Reverse projected coverage records whether subdivisions span each
        # contacted original core edge, avoiding an endpoint-only contact claim.
        coverage=[]
        for index in np.unique(assignments):
            intervals=sorted(tuple(sorted(row['core_parameters'])) for k,row in enumerate(witnesses) if assignments[k]==index)
            reach=0.;maxgap=0.
            for lo,hi in intervals:maxgap=max(maxgap,(lo-reach)*np.sqrt(den[index]));reach=max(reach,hi)
            maxgap=max(maxgap,(1-reach)*np.sqrt(den[index]))
            coverage.append({'core_edge':refs[index].tolist(),'maximum_uncovered_projected_length':float(maxgap)})
        reverse_bound=bound+max(row['maximum_uncovered_projected_length'] for row in coverage)
        pass_all=refs_exist and fixed_strip and fixed_core and bound<=tolerance and reverse_bound<=tolerance and bool(np.array_equal(p,p.astype(np.float32).astype(p.dtype)))
        report[name]={'pass':pass_all,'strip_faces':len(strip),'inner_strip_edges':len(inner),'contacted_original_core_edges':len(referenced),'original_reference_edges_exist_in_core':refs_exist,'float32_positions_exact':bool(np.array_equal(p,p.astype(np.float32).astype(p.dtype))),'strip_contact_vertices_fixed_at_all_knots':fixed_strip,'core_contact_vertices_fixed_at_all_knots':fixed_core,'whole_segment_distance_upper_bound':bound,'reverse_core_to_strip_distance_upper_bound':reverse_bound,'continuous_linear_interval_certificate':pass_all,'control_intervals':list(zip(knots[:-1].tolist(),knots[1:].tolist())),'core_strip_shared_topological_edges':len(set(core_counts)&set(strip_counts)),'reverse_projected_coverage':coverage,'segment_witnesses':witnesses}
    return {'pass':all(x['pass'] for x in report.values()),'tolerance':tolerance,'coordinate_frame':'normalized source height; X forward','method':__doc__,'meshes':report,'watertight_claim':False}

