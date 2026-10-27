# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Refine and fairly relax only patch interiors, preserving the full boundary."""
import numpy as np
from collections import Counter

def fair_disk_patch(poses,faces,source_edges,*,subdivisions=2):
    p=np.asarray(poses,float).copy();f=np.asarray(faces);source=np.asarray(source_edges)
    if p.ndim!=3 or p.shape[2]!=3 or not len(p) or not np.isfinite(p).all() or f.ndim!=2 or f.shape[1]!=3 or not np.issubdtype(f.dtype,np.integer) or not len(f) or f.min()<0 or f.max()>=p.shape[1]:raise ValueError('Finite indexed patch required')
    if source.ndim!=2 or source.shape[1]!=2 or not np.issubdtype(source.dtype,np.integer) or not len(source) or source.min()<0 or source.max()>=p.shape[1]:raise ValueError('Source boundary edges required')
    if not isinstance(subdivisions,int) or not 0<=subdivisions<=3:raise ValueError('Unsupported subdivision count')
    for _ in range(subdivisions):
        mid={};extra=[];ff=[]
        def get(a,b):
            key=tuple(sorted((int(a),int(b))))
            if key not in mid:mid[key]=p.shape[1]+len(extra);extra.append((p[:,a]+p[:,b])/2)
            return mid[key]
        for a,b,c in f:
            ab=get(a,b);bc=get(b,c);ca=get(c,a);ff.extend([(a,ab,ca),(ab,b,bc),(ca,bc,c),(ab,bc,ca)])
        source=np.array([pair for a,b in source for pair in [(a,get(a,b)),(get(a,b),b)]],int)
        p=np.concatenate([p,np.stack(extra,axis=1)],axis=1);f=np.array(ff,int)
    counts=Counter(tuple(sorted(map(int,e))) for face in f for e in zip(face,np.roll(face,-1)))
    boundary=np.unique([e for e,count in counts.items() if count==1]);inside=np.setdiff1d(np.arange(p.shape[1]),boundary);lookup={int(v):i for i,v in enumerate(inside)};neighbors=[set() for _ in range(p.shape[1])]
    for a,b in counts:neighbors[a].add(b);neighbors[b].add(a)
    matrix=np.zeros((len(inside),len(inside)));rhs=np.zeros((len(inside),len(p),3))
    for v,row in lookup.items():
        matrix[row,row]=len(neighbors[v])
        for neighbor in neighbors[v]:
            if neighbor in lookup:matrix[row,lookup[neighbor]]-=1
            else:rhs[row]+=p[:,neighbor]
    if len(inside):p[:,inside]=np.linalg.solve(matrix,rhs.reshape(len(inside),-1)).reshape(len(inside),len(p),3).transpose(1,0,2)
    basis=p[0].astype(np.float32);delta=(p-p[0]).astype(np.float32);p=(basis[None]+delta).astype(np.float32).astype(float)
    return {'poses':p,'faces':f,'skin_boundary_edges':source,'skin_boundary_vertices':np.unique(source),'fixed_patch_boundary_vertices':boundary}
