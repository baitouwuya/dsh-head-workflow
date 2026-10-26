# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import numpy as np,collections,math
def refine(vertices,faces,uv,source_faces,allowed,options):
    p=np.asarray(vertices,float);f=np.asarray(faces,int);uv=np.asarray(uv,float);sf=np.asarray(source_faces,int)
    edges=collections.defaultdict(list);neighbors=[set() for x in p]
    for i,t in enumerate(f):
        for a,b in zip(t,np.roll(t,-1)):edges[tuple(sorted((int(a),int(b))))].append(i);neighbors[a].add(int(b));neighbors[b].add(int(a))
    q=p[f];n=np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-30)
    active=set();bad=[]
    for e,u in edges.items():
        if len(u)==2 and n[u[0]]@n[u[1]]<np.cos(np.radians(options['threshold_degrees'])) and any(int(sf[i]) in allowed for i in u):
            bad.append(e);active.update(f[u].ravel())
    newp=p.copy();maxmove=options['step_limit_m']
    for i in active:
        neigh=list(neighbors[i]);valence=len(neigh)
        if valence<3:continue
        beta=3/16 if valence==3 else 3/(8*valence);delta=beta*(p[neigh].sum(axis=0)-valence*p[i])
        delta*=min(1,maxmove/max(np.linalg.norm(delta),1e-30));newp[i]+=delta
    pts=list(newp);mid={}
    for e,u in edges.items():
        a,b=e;co=(p[a]+p[b])/2
        if len(u)==2 and (a in active or b in active) and any(int(sf[i]) in allowed for i in u):
            c=next(int(k) for k in f[u[0]] if k not in e);d=next(int(k) for k in f[u[1]] if k not in e)
            delta=.125*(p[c]+p[d]-p[a]-p[b]);delta*=min(1,maxmove/max(np.linalg.norm(delta),1e-30));co+=delta
        mid[e]=len(pts);pts.append(co)
    out=[];ou=[];os=[]
    for i,(a,b,c) in enumerate(f):
        ab=mid[tuple(sorted((a,b)))];bc=mid[tuple(sorted((b,c)))];ca=mid[tuple(sorted((c,a)))]
        ua,ub,uc=uv[i];uab=(ua+ub)/2;ubc=(ub+uc)/2;uca=(uc+ua)/2
        out.extend([[a,ab,ca],[ab,b,bc],[ca,bc,c],[ab,bc,ca]])
        ou.extend([[ua,uab,uca],[uab,ub,ubc],[uca,ubc,uc],[uab,ubc,uca]]);os.extend([sf[i]]*4)
    return np.array(pts),np.array(out),np.array(ou),np.array(os),{'selected_bad_edges':len(bad),'active_old_vertices':len(active),'step_limit_m':maxmove}
