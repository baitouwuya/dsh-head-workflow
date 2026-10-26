# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Generic topology/geometry observations. No Blender or model data dependency."""
import collections,math
import numpy as np

def observation(value, count, *, applicable=True, reason=None):
    if value is not None and isinstance(value,(float,np.floating)) and not math.isfinite(float(value)):return {'status':'missing','value':None,'observations':int(count),'reason':'Nonfinite observation'}
    status='observed' if applicable and count>0 else 'not_applicable' if not applicable else 'missing'
    return {'status':status,'value':value if status=='observed' else None,'observations':int(count),'reason':reason}

def oriented_key(t):
    t=tuple(t);return min(t,t[1:]+t[:1],t[2:]+t[:2])

def analyze(vertices, faces, triangles, triangle_owners, canonical_ids=None,
            reference_local_vertices=None, local_vertices=None,
            area_epsilon=1e-15, volume_epsilon=1e-12):
    p=np.asarray(vertices,float).reshape(-1,3);t=np.asarray(triangles,int).reshape(-1,3)
    owners=np.asarray(triangle_owners,int);ids=list(range(len(p))) if canonical_ids is None else list(canonical_ids)
    if len(ids)!=len(p) or len(owners)!=len(t):raise ValueError('Topology correspondence length mismatch')
    if len(t) and (t.min()<0 or t.max()>=len(p)):raise ValueError('Triangle index outside vertex array')
    nonfinite=int(np.count_nonzero(~np.isfinite(p).all(axis=1)))
    q=p[t];norm=np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]);area=np.linalg.norm(norm,axis=1)
    valid=np.isfinite(area)&(area>area_epsilon);unit=norm/np.maximum(area[:,None],1e-300)
    polygon_edges=collections.defaultdict(list);loose_faces=[]
    for fi,f in enumerate(faces):
        if len(f)<3:loose_faces.append(fi);continue
        for a,b in zip(f,list(f[1:])+[f[0]]):
            ca,cb=ids[a],ids[b];polygon_edges[tuple(sorted((ca,cb)))].append((fi,ca,cb))
    boundary=[e for e,u in polygon_edges.items() if len(u)==1]
    nonmanifold=[e for e,u in polygon_edges.items() if len(u)>2 or e[0]==e[1]]
    same_direction=[e for e,u in polygon_edges.items() if len(u)==2 and u[0][1:]==u[1][1:]]
    tri_edges=collections.defaultdict(list)
    for i,tri in enumerate(t):
        for a,b in zip(tri,np.roll(tri,-1)):
            ca,cb=ids[int(a)],ids[int(b)];tri_edges[tuple(sorted((ca,cb)))].append(i)
    pairs=np.asarray([u for u in tri_edges.values() if len(u)==2],int).reshape(-1,2)
    good=pairs[valid[pairs[:,0]]&valid[pairs[:,1]]] if len(pairs) else pairs
    angles=np.degrees(np.arccos(np.clip(np.sum(unit[good[:,0]]*unit[good[:,1]],axis=1),-1,1))) if len(good) else np.array([])
    quads=[i for i,f in enumerate(faces) if len(f)==4];byface=collections.defaultdict(list)
    for ti,fi in enumerate(owners):byface[int(fi)].append(ti)
    qa=[];missing_quads=[]
    for fi in quads:
        ti=byface[fi]
        if len(ti)!=2 or not valid[ti].all():missing_quads.append(fi);continue
        qa.append(float(np.degrees(np.arccos(np.clip(unit[ti[0]]@unit[ti[1]],-1,1)))))
    # Every valid triangle has a neutral local normal reference. Object rigid
    # motion is removed; articulated deformation remains deliberately visible.
    reversals=None;reference_count=0
    if reference_local_vertices is not None and local_vertices is not None:
        rp=np.asarray(reference_local_vertices,float);lp=np.asarray(local_vertices,float)
        if rp.shape==lp.shape==p.shape:
            rn=np.cross(rp[t[:,1]]-rp[t[:,0]],rp[t[:,2]]-rp[t[:,0]])
            pn=np.cross(lp[t[:,1]]-lp[t[:,0]],lp[t[:,2]]-lp[t[:,0]])
            ok=(np.linalg.norm(rn,axis=1)>area_epsilon)&(np.linalg.norm(pn,axis=1)>area_epsilon)
            reference_count=int(ok.sum());reversals=int(np.count_nonzero(np.sum(rn[ok]*pn[ok],axis=1)<0))
    # Edge-connected shells, not merely object counts or coordinate clusters.
    parent=list(range(len(faces)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for uses in polygon_edges.values():
        for u in uses[1:]:parent[find(u[0])]=find(uses[0][0])
    components=collections.defaultdict(list)
    for fi in range(len(faces)):components[find(fi)].append(fi)
    shells=[]
    for fis in components.values():
        fset=set(fis);shell_edges={e:u for e,u in polygon_edges.items() if any(v[0] in fset for v in u)}
        shell_vertices={v for e in shell_edges for v in e};ti=np.flatnonzero(np.isin(owners,fis));qq=q[ti]
        volume=float(np.sum(np.einsum('ij,ij->i',qq[:,0],np.cross(qq[:,1],qq[:,2])))/6) if len(ti) else None
        if volume is not None and not math.isfinite(volume):volume=None
        shells.append({'face_ids':fis,'face_count':len(fis),'vertex_count':len(shell_vertices),'edge_count':len(shell_edges),
                       'boundary_edges':sum(len(u)==1 for u in shell_edges.values()),
                       'nonmanifold_edges':sum(len(u)>2 or e[0]==e[1] for e,u in shell_edges.items()),
                       'same_direction_edges':sum(len(u)==2 and u[0][1:]==u[1][1:] for u in shell_edges.values()),
                       'euler_characteristic':len(shell_vertices)-len(shell_edges)+len(fis),
                       'signed_volume_m3':volume,'volume_orientation':None if volume is None or abs(volume)<=volume_epsilon else 'outward' if volume>0 else 'inward'})
    referenced=set(int(x) for x in t.ravel());edge_lengths=[float(np.linalg.norm(p[a]-p[b])) for tri in t for a,b in zip(tri,np.roll(tri,-1))]
    quad=observation(max(qa) if qa else None,len(qa),applicable=bool(quads),reason='No quads; valid triangle coverage is independently required' if not quads else None)
    if missing_quads:quad={'status':'missing','value':None,'observations':len(qa),'reason':'One or more quads have missing/degenerate tessellation','missing_face_ids':missing_quads}
    return {'vertices':len(p),'faces':len(faces),'triangles':len(t),'valid_triangles':int(valid.sum()),
            'nonfinite_vertices':nonfinite,'degenerate_triangles':int((~valid).sum()),'unused_vertices':len(p)-len(referenced),
            'boundary_edges':len(boundary),'nonmanifold_edges':len(nonmanifold),'same_direction_edges':len(same_direction),
            'boundary_edge_ids':boundary,'nonmanifold_edge_ids':nonmanifold,'same_direction_edge_ids':same_direction,
            'shells':shells,'quad_face_count':len(quads),'quad_discrepancy_degrees':quad,
            'adjacent_normal_degrees':observation(float(angles.max()) if len(angles) else None,len(angles)),
            'reference_normal_reversals':observation(reversals,reference_count),
            'maximum_edge_length_m':observation(max(edge_lengths) if edge_lengths else None,len(edge_lengths)),
            'invalid_polygon_faces':loose_faces}


def segment_triangle(a,b,t,eps):
    direction=b-a;e1=t[1]-t[0];e2=t[2]-t[0];h=np.cross(direction,e2);det=float(e1@h)
    if abs(det)<eps:return None
    s=a-t[0];u=float(s@h/det);q=np.cross(s,e1);v=float(direction@q/det);w=float(e2@q/det)
    if u>=-eps and v>=-eps and u+v<=1+eps and -eps<=w<=1+eps:return a+w*direction
    return None

def cross2(a,b):return float(a[0]*b[1]-a[1]*b[0])

def triangle_intersects_beyond_contact(a,b,allowed_points,allowed_edges,eps=1e-8):
    """Exact segment tests plus coplanar 2D clipping; topological contact allowed."""
    na=np.cross(a[1]-a[0],a[2]-a[0]);nb=np.cross(b[1]-b[0],b[2]-b[0]);la=np.linalg.norm(na);lb=np.linalg.norm(nb)
    if la==0 or lb==0:return None
    ua,ub=na/la,nb/lb;hits=[]
    coplanar=np.linalg.norm(np.cross(ua,ub))<1e-8 and abs((b[0]-a[0])@ua)<=eps
    if coplanar:
        axis=int(np.argmax(abs(ua)));keep=[i for i in range(3) if i!=axis];poly=[x[keep] for x in a];bb=b[:,keep];orient=np.sign(cross2(bb[1]-bb[0],bb[2]-bb[0]));orient=1 if orient==0 else orient
        for x,y in zip(bb,np.roll(bb,-1,axis=0)):
            output=[]
            def signed(p):return orient*cross2(y-x,p-x)
            for p,q in zip(poly,poly[1:]+poly[:1]):
                dp,dq=signed(p),signed(q)
                if dp>=-eps:output.append(p)
                if (dp>=-eps)!=(dq>=-eps):output.append(p+(q-p)*dp/(dp-dq))
            poly=output
            if not poly:break
        if len(poly)>=3:
            ar=abs(sum(cross2(x,y) for x,y in zip(poly,poly[1:]+poly[:1])))/2
            if ar>eps*eps:return True
        return False
    for t,other in [(a,b),(b,a)]:
        for p,q in zip(t,np.roll(t,-1,axis=0)):
            hit=segment_triangle(p,q,other,eps*eps)
            if hit is not None:hits.append(hit)
    for hit in hits:
        if any(np.linalg.norm(hit-p)<=eps for p in allowed_points):continue
        on_edge=False
        for p,q in allowed_edges:
            d=q-p;t=np.clip((hit-p)@d/max(d@d,1e-300),0,1)
            if np.linalg.norm(hit-(p+t*d))<=eps:on_edge=True;break
        if not on_edge:return True
    return False

