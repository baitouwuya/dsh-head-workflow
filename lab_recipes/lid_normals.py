# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Explicit generated-lid shading normals and sampled glTF normal targets.

This changes no positions or topology and does not repair geometric folds.
Original source normals should be preserved; this helper is for new lid meshes.
"""
import numpy as np

def _positions(value):
    p=np.asarray(value,dtype=np.float64)
    if p.ndim!=2 or p.shape[1]!=3 or not len(p) or not np.isfinite(p).all():
        raise ValueError('nonempty finite Nx3 positions required')
    return p

def _faces(value,vertex_count):
    f=np.asarray(value)
    if f.ndim!=2 or f.shape[1]!=3 or not len(f) or not np.issubdtype(f.dtype,np.integer) or (f<0).any() or (f>=vertex_count).any():
        raise ValueError('nonempty integer triangle indices required')
    return f.astype(np.int64,copy=False)

def _poses(value,minimum_samples):
    p=np.asarray(value,dtype=np.float64)
    if p.ndim!=3 or p.shape[2]!=3 or p.shape[0]<minimum_samples or not p.shape[1] or not np.isfinite(p).all():
        raise ValueError('nonempty finite pose samples required')
    return p


def split_generated_shading_domains(poses,faces,face_domains):
    """Separate generated core/transition normals without moving any geometry.

    A static source-conforming strip can meet a closed hood at a three-face
    contact. Those surfaces need separate shading normals rather than averaging
    opposing faces. The caller supplies explicit construction-domain IDs. Returned
    original-vertex indices also remap COLOR_0 and any other per-vertex attributes.
    Duplicated contact positions retain identical trajectories at every knot.
    """
    p=_poses(poses,1);f=_faces(faces,p.shape[1]);domains=np.asarray(face_domains)
    if p.ndim!=3 or p.shape[2]!=3 or f.ndim!=2 or f.shape[1]!=3 or domains.shape!=(len(f),) or not np.issubdtype(domains.dtype,np.integer) or not np.isfinite(p).all() or (f<0).any() or (f>=p.shape[1]).any():
        raise ValueError('invalid generated shading domain arrays')
    result=[]
    for label in np.unique(domains):
        face_ids=np.flatnonzero(domains==label);selected=f[face_ids];used=np.unique(selected);mapping=np.full(p.shape[1],-1,int);mapping[used]=np.arange(len(used))
        result.append({'domain_id':int(label),'source_face_indices':face_ids,
                       'source_vertex_indices':used,'poses':p[:,used].copy(),
                       'faces':mapping[selected]})
    return {'domains':result,'vertex_positions_changed':False,'triangle_geometry_changed':False}


def orient_closed_generated_mesh(vertices,faces):
    """Orient each consistently wound closed generated component outward.

    This fixes the upper-hood parameterization's reversed winding. It never
    changes source geometry or vertex positions. Open/nonmanifold or internally
    inconsistent meshes are rejected rather than silently guessing orientation.
    Call before adding a source-conforming open transition and retain its edge
    orientation when stitching that transition.
    """
    p=_positions(vertices);f=_faces(faces,len(p))
    if p.ndim!=2 or p.shape[1]!=3 or f.ndim!=2 or f.shape[1]!=3 or not len(f) or not np.isfinite(p).all() or (f<0).any() or (f>=len(p)).any():
        raise ValueError('orientation requires finite positions and valid triangles')
    edges={};parent=np.arange(len(f))
    def root(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for index,face in enumerate(f):
        if len(set(face))!=3:raise ValueError('closed generated mesh contains a zero-index edge')
        for a,b in zip(face,np.roll(face,-1)):
            key=tuple(sorted((int(a),int(b))));edges.setdefault(key,[]).append((index,1 if a<b else -1))
    for incident in edges.values():
        if len(incident)!=2:raise ValueError('generated mesh must be closed and two-manifold before orientation')
        (a,da),(b,db)=incident
        if da==db:raise ValueError('generated mesh has inconsistent adjacent triangle winding')
        parent[root(a)]=root(b)
    components={}
    for i in range(len(f)):components.setdefault(root(i),[]).append(i)
    result=f.copy();report=[]
    for face_ids in components.values():
        face_ids=np.asarray(face_ids);used=np.unique(f[face_ids]);center=p[used].mean(0);t=(p-center)[f[face_ids]]
        volume=float(np.einsum('ij,ij->i',t[:,0],np.cross(t[:,1],t[:,2])).sum()/6)
        scale=float(np.linalg.norm(np.ptp(p[used],axis=0)));floor=64*np.finfo(np.float64).eps*scale**3
        if not np.isfinite(volume) or abs(volume)<=floor:raise ValueError('closed generated component has indeterminate signed volume')
        flipped=volume<0
        if flipped:result[face_ids]=result[face_ids][:,[0,2,1]]
        report.append({'triangles':len(face_ids),'signed_volume_before':volume,'signed_volume_after':abs(volume),'flipped':flipped})
    return {'faces':result,'components':report,'flipped_triangles':sum(x['triangles'] for x in report if x['flipped']),'vertex_positions_changed':False}


def area_weighted_normals(vertices,faces):
    p=_positions(vertices);f=_faces(faces,len(p))
    if p.ndim!=2 or p.shape[1]!=3 or f.ndim!=2 or f.shape[1]!=3 or not np.isfinite(p).all() or (f<0).any() or (f>=len(p)).any():
        raise ValueError('normals require finite positions and valid triangle indices')
    t=p[f];fn=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);n=np.zeros_like(p)
    for corner in range(3):np.add.at(n,f[:,corner],fn)
    length=np.linalg.norm(n,axis=1)
    if (length<=0).any():
        raise ValueError('a generated vertex has no stable accumulated face normal')
    return n/length[:,None]


def build_normal_targets(poses,faces):
    """Return NORMAL basis and differences for the supplied position knots."""
    poses=_poses(poses,2)
    if poses.ndim!=3 or poses.shape[2]!=3 or len(poses)<2:
        raise ValueError('poses must contain at least two Nx3 samples')
    normals=np.array([area_weighted_normals(p,faces) for p in poses])
    return {'base_normals':normals[0].astype(np.float32),
            'target_normal_deltas':(normals[1:]-normals[0]).astype(np.float32),
            'sample_normals':normals.astype(np.float32),
            'geometry_changed':False,'normal_mode':'area-weighted smooth normals on generated topology'}


def audit_normal_interpolation(poses,faces,normals,subsamples=(.25,.5,.75),cancellation_tolerance=1e-12):
    """Compare glTF normalized linear normal interpolation to actual mesh normals.

    Endpoints match by construction. Nonzero interior angular error is reported,
    not silently passed: interpolating shading vectors need not equal recomputing
    normals on linearly moving geometry.
    """
    poses=_poses(poses,2);faces=_faces(faces,poses.shape[1]);normals=np.asarray(normals,dtype=np.float64);subsamples=np.asarray(subsamples,dtype=float);angles=[];cancelled=0
    if normals.shape!=poses.shape or not np.isfinite(normals).all():raise ValueError('normal samples must be finite and match poses')
    if subsamples.ndim!=1 or not len(subsamples) or not np.isfinite(subsamples).all() or (subsamples<=0).any() or (subsamples>=1).any():raise ValueError('normal audit requires nonempty finite interior subsamples')
    if not np.isfinite(cancellation_tolerance) or cancellation_tolerance<=0:raise ValueError('normal cancellation tolerance must be finite and positive')
    endpoint_lengths=np.linalg.norm(normals,axis=2)
    if (endpoint_lengths<=cancellation_tolerance).any():raise ValueError('endpoint normals must be nonzero')
    # A normal vector is linear before shader normalization. Check its true
    # interval minimum too; sparse angle samples cannot certify no cancellation.
    start=normals[:-1];delta=normals[1:]-start;den=np.einsum('sni,sni->sn',delta,delta)
    t=np.clip(np.divide(-np.einsum('sni,sni->sn',start,delta),den,out=np.zeros_like(den),where=den>0),0,1)
    minimum_lengths=np.linalg.norm(start+t[:,:,None]*delta,axis=2)
    for i in range(len(poses)-1):
        for weight in subsamples:
            if not 0<weight<1:raise ValueError('normal audit subsamples must lie inside the interval')
            p=poses[i]*(1-weight)+poses[i+1]*weight
            actual=area_weighted_normals(p,faces);mix=normals[i]*(1-weight)+normals[i+1]*weight;length=np.linalg.norm(mix,axis=1);valid=length>cancellation_tolerance;cancelled+=int((~valid).sum());mix[valid]/=length[valid,None]
            angles.extend(np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i',mix[valid],actual[valid]),-1,1))).tolist())
    return {'sampled_vertex_normal_comparisons':len(angles),'cancelled_interpolated_normals':cancelled,
            'interval_vertex_normal_checks':int(minimum_lengths.size),
            'interval_cancelled_vertex_normals':int((minimum_lengths<=cancellation_tolerance).sum()),
            'minimum_interpolated_normal_length':float(minimum_lengths.min()),
            'endpoint_normal_max_unit_length_error':float(abs(endpoint_lengths-1).max()),
            'cancellation_tolerance':float(cancellation_tolerance),
            'angular_error_degrees_quantiles':np.quantile(angles,[0,.5,.95,.99,1]).tolist() if angles else [],
            'normal_interpolation_is_not_geometric_fold_check':True}


def audit_face_normal_jumps(vertices,faces):
    p=_positions(vertices);f=_faces(faces,len(p));t=p[f];n=np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]);length=np.linalg.norm(n,axis=1);valid=length>0;n[valid]/=length[valid,None]
    edges={};angles=[]
    for i,face in enumerate(f):
        for a,b in zip(face,np.roll(face,-1)):
            edge=tuple(sorted((int(a),int(b))))
            for previous in edges.get(edge,[]):
                if valid[i] and valid[previous]:angles.append(float(np.degrees(np.arccos(np.clip(n[i]@n[previous],-1,1)))))
            edges.setdefault(edge,[]).append(i)
    return {'triangle_count':len(f),'nonmanifold_edges':sum(len(v)>2 for v in edges.values()),'adjacent_face_pairs':len(angles),'face_angle_degrees_quantiles':np.quantile(angles,[0,.5,.95,.99,1]).tolist() if angles else [],'above_60_degrees':sum(a>60 for a in angles),'above_90_degrees':sum(a>90 for a in angles),'interpretation':'Closed shell curvature and geometric steps both contribute; smooth normals do not remove these angles.'}
