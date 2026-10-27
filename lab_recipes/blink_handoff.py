# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Input-sized diagnostics for exported eyelid morphs; no hidden quality threshold.

World-normal reversal measures orientation change, not inversion. For linear
morph segments, triangle area minima include interior extrema. Collision,
appearance, visible-eye coverage and anatomical attachment still need their
own checks. Source or canonical vertex IDs may be supplied for seam topology.
"""
import numpy as np

def _positions(value):
    a=np.asarray(value,dtype=float)
    if a.ndim!=2 or a.shape[1]!=3 or len(a)==0 or not np.isfinite(a).all():
        raise ValueError('Expected nonempty finite Nx3 positions')
    return a

def _triangles(value,vertex_count):
    f=np.asarray(value)
    if f.ndim!=2 or f.shape[1]!=3 or len(f)==0 or not np.issubdtype(f.dtype,np.integer):
        raise ValueError('Triangle indices must be a nonempty integer Nx3 array')
    if f.size and (f.min()<0 or f.max()>=vertex_count):raise ValueError('Invalid triangle index')
    return f.astype(np.int64,copy=False)

def audit_neutral_and_near_neutral(evaluate,basis,samples,neutral_tolerance):
    """evaluate(value) must use the actual shipped controller/interpolation."""
    source=_positions(basis);values=sorted(set([0.]+list(samples)))
    if not np.isfinite(neutral_tolerance) or neutral_tolerance<0 or any(not np.isfinite(x) or x<0 or x>1 for x in values):
        raise ValueError('Invalid tolerance or control sample')
    rows=[]
    for value in values:
        p=_positions(evaluate(value))
        if p.shape!=source.shape:raise ValueError('Controller changed topology')
        displacement=np.linalg.norm(p-source,axis=1)
        rows.append({'value':float(value),'maximum_displacement':float(displacement.max(initial=0)),
                     'maximum_displacement_per_control_unit':float(displacement.max(initial=0)/value) if value else None})
    return {'vertex_count':len(source),'neutral_identity_pass':rows[0]['maximum_displacement']<=neutral_tolerance,
            'neutral_tolerance':float(neutral_tolerance),'samples':rows,
            'limitation':'Near-zero samples report controller response; finite sampling alone does not prove continuity.'}

def audit_component_binding(basis,posed,triangles,editable_mask,*,movement_tolerance,
                            minimum_edge_length,stretch_limit=None,canonical_ids=None,
                            canonical_tolerance=None):
    """Report torn masks and edge strain; limits belong to runtime configuration.

    A static/moving edge is not automatically invalid (e.g. a fixed collar).
    A known lash component should not be cropped by an axis-aligned edit mask.
    Canonical IDs require an explicit runtime position/displacement tolerance.
    Unknown sentinel IDs must be omitted, never merged as one canonical vertex.
    Component/mask counts do not establish consistency unless the returned
    canonical_consistency_pass is also true; physical attachment is separate.
    """
    a=_positions(basis);b=_positions(posed);f=_triangles(triangles,len(a));mask=np.asarray(editable_mask,bool)
    if b.shape!=a.shape or mask.shape!=(len(a),) or f.ndim!=2 or f.shape[1]!=3:raise ValueError('Shape mismatch')
    if not np.isfinite([movement_tolerance,minimum_edge_length]).all() or movement_tolerance<0 or minimum_edge_length<0 or (stretch_limit is not None and (not np.isfinite(stretch_limit) or stretch_limit<=0)):raise ValueError('Invalid runtime threshold')
    ids=np.arange(len(a)) if canonical_ids is None else np.asarray(canonical_ids)
    if ids.shape!=(len(a),) or not np.issubdtype(ids.dtype,np.integer) or np.any(ids<0):raise ValueError('Canonical IDs must be nonnegative integers matching positions; omit unknown IDs')
    if canonical_ids is not None and canonical_tolerance is None:raise ValueError('Canonical IDs require an explicit canonical_tolerance')
    if canonical_tolerance is not None and (not np.isfinite(canonical_tolerance) or canonical_tolerance<0):raise ValueError('Invalid canonical_tolerance')
    edges=np.unique(np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1),axis=0)
    before=np.linalg.norm(a[edges[:,0]]-a[edges[:,1]],axis=1);after=np.linalg.norm(b[edges[:,0]]-b[edges[:,1]],axis=1)
    movement=np.linalg.norm(b-a,axis=1);moving=movement>movement_tolerance;valid=before>minimum_edge_length
    ratios=np.divide(after,before,out=np.full(len(edges),np.nan),where=valid)
    split_mask=mask[edges[:,0]]!=mask[edges[:,1]];split_motion=moving[edges[:,0]]!=moving[edges[:,1]]
    canonical_groups={}
    for vertex in np.unique(f):canonical_groups.setdefault(int(ids[vertex]),[]).append(int(vertex))
    def diameter(points):
        maximum=0.
        for index,point in enumerate(points[:-1]):maximum=max(maximum,float(np.linalg.norm(points[index+1:]-point,axis=1).max(initial=0)))
        return maximum
    canonical_rows=[]
    for identifier,vertices in canonical_groups.items():
        if len(vertices)<2:continue
        canonical_rows.append({'canonical_id':identifier,'copies':len(vertices),
            'rest_gap':diameter(a[vertices]),'posed_gap':diameter(b[vertices]),
            'displacement_gap':diameter((b-a)[vertices]),
            'mask_conflict':bool(np.any(mask[vertices]!=mask[vertices[0]]))})
    tolerance=0. if canonical_tolerance is None else canonical_tolerance
    conflict_counts={field:sum(row[field]>tolerance for row in canonical_rows) for field in ('rest_gap','posed_gap','displacement_gap')}
    mask_conflicts=sum(row['mask_conflict'] for row in canonical_rows)
    canonical_pass=not any(conflict_counts.values()) and not mask_conflicts
    canonical_worst=sorted(canonical_rows,key=lambda row:max(row['rest_gap'],row['posed_gap'],row['displacement_gap']),reverse=True)[:10]
    parent={int(i):int(i) for i in np.unique(ids[np.unique(f)])}
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for u,v in edges:
        x,y=find(int(ids[u])),find(int(ids[v]));parent[x]=y
    groups={}
    for vertex in np.unique(f):groups.setdefault(find(int(ids[vertex])),[]).append(int(vertex))
    components=[]
    for vertices in groups.values():
        count=int(mask[vertices].sum());components.append({'vertices':len(vertices),'editable_vertices':count,
             'moving_vertices':int(moving[vertices].sum()),'partially_masked':0<count<len(vertices)})
    worst=np.argsort(np.where(valid,ratios,-1))[-10:][::-1]
    return {'vertex_count':len(a),'referenced_vertex_count':len(np.unique(f)),'triangle_count':len(f),
        'component_count':len(groups),'partially_masked_components':sum(c['partially_masked'] for c in components),
        'canonical_tolerance':canonical_tolerance,'canonical_consistency_pass':canonical_pass,
        'canonical_duplicate_group_count':len(canonical_rows),'canonical_conflict_counts':conflict_counts,
        'canonical_mask_conflict_count':mask_conflicts,'canonical_worst_groups':canonical_worst,
        'components':components,'mask_cut_edges':int(split_mask.sum()),'moving_static_edges':int(split_motion.sum()),
        'maximum_edge_stretch_ratio':float(ratios[valid].max()) if valid.any() else None,
        'stretch_limit':stretch_limit,'stretch_limit_exceedances':int((ratios[valid]>stretch_limit).sum()) if stretch_limit is not None else None,
        'excluded_short_edges':int((~valid).sum()),'minimum_edge_length':minimum_edge_length,
        'worst_edges':[{'vertex_indices':edges[k].tolist(),'canonical_ids':ids[edges[k]].tolist(),
             'source_length':float(before[k]),'stretch_ratio':float(ratios[k]),'mask_cut':bool(split_mask[k]),
             'moving_static_cut':bool(split_motion[k]),'endpoint_displacement':movement[edges[k]].tolist()} for k in worst if valid[k]]}

def linear_triangle_area_minimum(start,end):
    """Exact candidate extrema of double-area along a linear position morph."""
    a=_positions(start);b=_positions(end)
    if a.shape!=(3,3) or b.shape!=(3,3):raise ValueError('Expected two triangles')
    u=a[1]-a[0];v=a[2]-a[0];du=(b[1]-b[0])-u;dv=(b[2]-b[0])-v
    n0=np.cross(u,v);n1=np.cross(du,v)+np.cross(u,dv);n2=np.cross(du,dv)
    polynomial=np.array([n0@n0,2*(n0@n1),n1@n1+2*(n0@n2),2*(n1@n2),n2@n2])
    derivative=np.trim_zeros((polynomial[1:]*np.arange(1,5))[::-1],trim='f')
    roots=np.roots(derivative) if len(derivative)>1 else []
    times=[0.,1.]+[float(z.real) for z in roots if abs(z.imag)<1e-9 and 0<z.real<1]
    normals=[n0+n1*t+n2*t*t for t in times];areas=[float(np.linalg.norm(n)) for n in normals];i=int(np.argmin(areas))
    endpoint=np.cross(b[1]-b[0],b[2]-b[0]);base=float(np.linalg.norm(n0))
    return {'minimum_double_area':areas[i],'at':times[i],
            'minimum_area_ratio':areas[i]/base if base>0 else None,
            'reference_normal_reversal':bool(n0@endpoint<0),
            'initial_double_area':base,'final_double_area':float(np.linalg.norm(endpoint))}

def audit_linear_morph_segments(basis,triangles,sample_values,sample_positions,*,
                               source_double_area_floor,collapse_area_ratio):
    """Find source-valid faces collapsing inside actual LINEAR morph intervals.

    The runtime supplies both numerical tolerances. This checks geometry from
    the actual controller at its interpolation knots; it does not certify an
    arbitrary nonlinear controller from sparse samples. Inherited source
    degenerates are counted separately and excluded from newly-collapsed faces.
    """
    base=_positions(basis);f=_triangles(triangles,len(base));values=np.asarray(sample_values,float)
    samples=np.asarray(sample_positions,float)
    if values.ndim!=1 or len(values)<2 or not np.isfinite(values).all() or np.any(np.diff(values)<=0) or values[0]<0 or values[-1]>1:raise ValueError('Expected strictly increasing normalized control values')
    if samples.shape!=(len(values),len(base),3) or not np.isfinite(samples).all():raise ValueError('Invalid sampled controller positions')
    if not np.isfinite([source_double_area_floor,collapse_area_ratio]).all() or source_double_area_floor<0 or not 0<collapse_area_ratio<1:raise ValueError('Invalid area thresholds')
    triangles0=base[f];normal0=np.cross(triangles0[:,1]-triangles0[:,0],triangles0[:,2]-triangles0[:,0]);source_area=np.linalg.norm(normal0,axis=1)
    source_valid=source_area>source_double_area_floor;events=[];segments=[]
    if not source_valid.any():raise ValueError('No source-valid triangles remain above the configured area floor')
    for segment,(low,high) in enumerate(zip(values[:-1],values[1:])):
        a=samples[segment][f];b=samples[segment+1][f];na=np.cross(a[:,1]-a[:,0],a[:,2]-a[:,0]);nb=np.cross(b[:,1]-b[:,0],b[:,2]-b[:,0])
        changed=np.any(a!=b,axis=(1,2));already_small=np.linalg.norm(na,axis=1)<=source_area*collapse_area_ratio
        candidates=np.flatnonzero(source_valid&(changed|already_small));segment_events=0
        for index in candidates:
            r=linear_triangle_area_minimum(a[index],b[index])
            if r['minimum_double_area']<=source_area[index]*collapse_area_ratio:
                events.append({'triangle_index':int(index),'segment_index':segment,
                    'control_value':float(low+(high-low)*r['at']),
                    'segment_fraction':r['at'],'minimum_double_area':r['minimum_double_area'],
                    'source_double_area':float(source_area[index]),
                    'minimum_area_ratio_to_source':float(r['minimum_double_area']/source_area[index])})
                segment_events+=1
        segments.append({'start':float(low),'end':float(high),'source_valid_changed_or_small_faces':len(candidates),
            'collapse_events':segment_events,
            'reference_normal_reversals_diagnostic_only':int(((na*nb).sum(1)<0).sum())})
    return {'source_face_count':len(f),'source_valid_face_count':int(source_valid.sum()),
        'checked_control_range':[float(values[0]),float(values[-1])],
        'source_double_area_floor':float(source_double_area_floor),'collapse_area_ratio':float(collapse_area_ratio),
        'inherited_source_degenerate_faces':int((~source_valid).sum()),
        'newly_collapsed_face_count':len({e['triangle_index'] for e in events}),
        'collapse_events':events,'segments':segments}
