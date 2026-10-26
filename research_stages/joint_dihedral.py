# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Pure NumPy bounded joint dihedral repair; no topology/UV changes. Not an audit."""

import numpy as np

import time



def adjacency(triangles):

    edges={}

    for i,t in enumerate(triangles):

        for a,b in zip(t,np.roll(t,-1)):

            edges.setdefault(tuple(sorted((int(a),int(b)))),[]).append(i)

    return edges,np.array([x for x in edges.values() if len(x)==2],dtype=np.int64).reshape(-1,2)



def optimize(vertices, triangles, movable, caps_m, profile, callback=None, reference_vertices=None):

    # Work in mm to keep optimizer scales explicit; return meters.

    base=np.asarray(vertices,float)*1000;t=np.asarray(triangles,np.int64)

    edges,pairs=adjacency(t);a,b=pairs.T

    q0=base[t];c0=np.cross(q0[:,1]-q0[:,0],q0[:,2]-q0[:,0]);area0=np.linalg.norm(c0,axis=1)

    if np.any(area0<=0):raise ValueError('Degenerate input triangles require explicit topology repair first')

    if reference_vertices is not None:
        rq=(np.asarray(reference_vertices,float)*1000)[t];c0=np.cross(rq[:,1]-rq[:,0],rq[:,2]-rq[:,0]);area0=np.linalg.norm(c0,axis=1)
        if np.any(area0<=0):raise ValueError('Degenerate reference geometry')
    ref=c0/area0[:,None];reference_weights=np.ones(len(t));reference_weights[int(profile.get('reference_constraint_face_count',len(t))):]=0
    mov=np.asarray(movable,bool);caps=np.asarray(caps_m,float)*1000

    caps=np.where(mov,caps,0.);x=base.copy();m=np.zeros_like(x);s=np.zeros_like(x)

    target=np.deg2rad(profile.get('target_degrees',88));lr=profile.get('learning_rate_mm',.03)

    eps=profile.get('adam_epsilon',1e-9);area_fraction=profile.get('minimum_area_fraction',.1)

    orientation_floor=profile.get('minimum_reference_dot',.01)

    def evaluate(x,gradient=False):

        q=x[t];u=q[:,1]-q[:,0];v=q[:,2]-q[:,0];c=np.cross(u,v);ar=np.linalg.norm(c,axis=1);n=c/np.maximum(ar[:,None],1e-20)

        dot=np.clip(np.einsum('ij,ij->i',n[a],n[b]),-1+1e-12,1-1e-12);ang=np.arccos(dot);h=np.maximum(ang-target,0)

        rd=np.einsum('ij,ij->i',n,ref);oh=np.maximum(orientation_floor-rd,0)*reference_weights;ah=np.maximum(area_fraction-ar/area0,0)

        loss=float((h*h).sum()+profile.get('orientation_weight',10)*(oh*oh).sum()+profile.get('area_weight',10)*(ah*ah).sum()+profile.get('tether_weight',1e-5)*((x-base)**2).sum())

        stats={'bad_pairs':int((ang>np.pi/2).sum()),'max_degrees':float(np.rad2deg(ang.max())),'minimum_reference_dot':float(rd.min()),'minimum_reference_dot_constrained':float(rd[reference_weights>0].min()) if np.any(reference_weights>0) else None,'minimum_area_ratio':float((ar/area0).min()),'loss':loss,'maximum_displacement_m':float(np.linalg.norm(x-base,axis=1).max()/1000)}

        if not gradient:return stats

        gn=np.zeros_like(n);coef=-2*h/np.sqrt(np.maximum(1-dot*dot,1e-12))

        np.add.at(gn,a,coef[:,None]*n[b]);np.add.at(gn,b,coef[:,None]*n[a])

        gn-=2*profile.get('orientation_weight',10)*oh[:,None]*ref

        gc=(gn-n*np.einsum('ij,ij->i',gn,n)[:,None])/np.maximum(ar[:,None],1e-20)

        gc-=2*profile.get('area_weight',10)*(ah/area0)[:,None]*n

        gb=np.cross(v,gc);gd=np.cross(gc,u);ga=-gb-gd

        g=np.zeros_like(x)

        for j,term in enumerate((ga,gb,gd)):

            for k in range(3):g[:,k]+=np.bincount(t[:,j],weights=term[:,k],minlength=len(x))

        g+=2*profile.get('tether_weight',1e-5)*(x-base);g[~mov]=0

        return stats,g

    initial=evaluate(x);best=x.copy();best_stats=initial;history=[];start=time.perf_counter()

    for it in range(1,profile.get('steps',2500)+1):

        stats,g=evaluate(x,True);m=.9*m+.1*g;s=.999*s+.001*g*g

        step=lr*(m/(1-.9**it))/(np.sqrt(s/(1-.999**it))+eps)

        x-=step;delta=x-base;length=np.linalg.norm(delta,axis=1);x=base+delta*np.minimum(1,caps/np.maximum(length,1e-30))[:,None]

        if it%profile.get('checkpoint_steps',100)==0 or it==1:

            stats=evaluate(x);stats['step']=it;history.append(stats)

            if (stats['minimum_reference_dot_constrained'] is None or stats['minimum_reference_dot_constrained']>0) and stats['minimum_area_ratio']>.01 and (stats['bad_pairs'],round(stats['max_degrees'],6),stats['loss'])<(best_stats['bad_pairs'],round(best_stats['max_degrees'],6),best_stats['loss']):best=x.copy();best_stats=stats.copy()

            if callback:callback(stats)

    out=(best/1000).astype(np.float32).astype(float)

    return out,{'initial':initial,'selected':best_stats,'float32':evaluate(out*1000),'history':history,'seconds':time.perf_counter()-start,'movable_vertices':int(mov.sum()),'fixed_vertices':int((~mov).sum()),'topology_changed':False,'uv_changed':False,'constraints_are_optimizer_only':'Actual full pose, intersection, closure, silhouette and texture audits still required'}



