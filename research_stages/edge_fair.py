# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import numpy as np,collections,math
def repair(v,f,options):
    p=np.array(v,float).copy();source=p.copy();f=np.array(f,int);edges=collections.defaultdict(list)
    vertex_faces=[set() for x in p]
    for i,tri in enumerate(f):
        for a in tri:vertex_faces[a].add(i)
        for a,b in zip(tri,np.roll(tri,-1)):edges[tuple(sorted((int(a),int(b))))].append(i)
    keys=[];pairs=[]
    for e,u in edges.items():
        if len(u)==2:keys.append(e);pairs.append(u)
    pairs=np.array(pairs,int);face_pairs=[set() for _ in f]
    for i,(a,b) in enumerate(pairs):face_pairs[a].add(i);face_pairs[b].add(i)
    target=np.cos(np.radians(options['target_degrees']))
    def normals(points,faces):
        q=points[faces];n=np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]);ar=np.linalg.norm(n,axis=1);return n/np.maximum(ar[:,None],1e-30),ar
    norm,areas=normals(p,f);history=[]
    for iteration in range(options['passes']):
        dots=np.sum(norm[pairs[:,0]]*norm[pairs[:,1]],axis=1)
        bad=np.flatnonzero(dots<target);bad=bad[np.argsort(dots[bad])]
        changes=0
        for pi in bad:
            ia,ib=pairs[pi];a,b=keys[pi];c=next(k for k in f[ia] if k not in (a,b));d=next(k for k in f[ib] if k not in (a,b))
            edge=p[b]-p[a];length=np.linalg.norm(edge)
            if length<1e-12:continue
            axis=edge/length;cv=p[c]-p[a];dv=p[d]-p[a];cp=cv-axis*(cv@axis);dp=dv-axis*(dv@axis);cl=np.linalg.norm(cp);dl=np.linalg.norm(dp)
            if min(cl,dl)<1e-12:continue
            direction=cp/cl-dp/dl;direction_length=np.linalg.norm(direction)
            if direction_length<1e-10:continue
            direction/=direction_length
            tc=p[a]+axis*(cv@axis)+direction*cl;td=p[a]+axis*(dv@axis)-direction*dl
            affected=np.array(sorted(vertex_faces[c]|vertex_faces[d]),int);pp=np.array(sorted(set.union(*(face_pairs[k] for k in affected))),int)
            old=float(np.maximum(target-np.sum(norm[pairs[pp,0]]*norm[pairs[pp,1]],axis=1),0)@np.maximum(target-np.sum(norm[pairs[pp,0]]*norm[pairs[pp,1]],axis=1),0))
            best=None;bestcost=old
            for which in [0,1,2]:
                for amount in [1.,.5,.2,.05]:
                    ids=[c,d];trial=p[ids].copy()
                    if which!=1:trial[0]+=amount*(tc-p[c])
                    if which!=0:trial[1]+=amount*(td-p[d])
                    displacement=trial-source[ids];lens=np.linalg.norm(displacement,axis=1)
                    trial=source[ids]+displacement*np.minimum(1,np.array([options.get('anterior_max_displacement_m',options['max_displacement_m']) if source[i,0]>0 and source[i,2]>.86 else options['max_displacement_m'] for i in ids])/np.maximum(lens,1e-30))[:,None]
                    oldpos=p[ids].copy();p[ids]=trial
                    nn,aa=normals(p,f[affected]);p[ids]=oldpos
                    if aa.min()<options['minimum_double_area_m2']:continue
                    trialn=norm.copy();trialn[affected]=nn
                    dd=np.maximum(target-np.sum(trialn[pairs[pp,0]]*trialn[pairs[pp,1]],axis=1),0);cost=float(dd@dd)
                    if cost<bestcost-1e-12:bestcost=cost;best=(trial,nn)
            if best is not None:p[[c,d]]=best[0];norm[affected]=best[1];changes+=1
        dots=np.sum(norm[pairs[:,0]]*norm[pairs[:,1]],axis=1)
        history.append({'pass':iteration,'changes':changes,'above_90':int((dots<0).sum()),'above_target':int((dots<target).sum()),'max_angle':float(np.degrees(np.arccos(np.clip(dots.min(),-1,1))))})
        if changes==0 or not (dots<0).any():break
    return p,{'history':history,'displacement_max_m':float(np.linalg.norm(p-source,axis=1).max()),'final':history[-1]}
