# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Optional altitude-bounded feasible-descent dihedral repair. Original solver unchanged."""

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

        qr=np.asarray(reference_vertices,float)[t]*1000

        cr=np.cross(qr[:,1]-qr[:,0],qr[:,2]-qr[:,0]);reference_area=np.linalg.norm(cr,axis=1)

        if np.any(reference_area<=0):raise ValueError('Degenerate reference triangles')

        ref=cr/reference_area[:,None]

    else:ref=c0/area0[:,None]

    mov=np.asarray(movable,bool);caps=np.asarray(caps_m,float)*1000

    caps=np.where(mov,caps,0.);x=base.copy();m=np.zeros_like(x);s=np.zeros_like(x)

    target=np.deg2rad(profile.get('target_degrees',88));lr=profile.get('learning_rate_mm',.03)

    eps=profile.get('adam_epsilon',1e-9);area_fraction=profile.get('minimum_area_fraction',.1)

    orientation_floor=profile.get('minimum_reference_dot',.01)

    def evaluate(x,gradient=False):

        q=x[t];u=q[:,1]-q[:,0];v=q[:,2]-q[:,0];c=np.cross(u,v);ar=np.linalg.norm(c,axis=1);n=c/np.maximum(ar[:,None],1e-20)

        dot=np.clip(np.einsum('ij,ij->i',n[a],n[b]),-1+1e-12,1-1e-12);ang=np.arccos(dot);h=np.maximum(ang-target,0)

        rd=np.einsum('ij,ij->i',n,ref);oh=np.maximum(orientation_floor-rd,0);ah=np.maximum(area_fraction-ar/area0,0)

        loss=float((h*h).sum()+profile.get('orientation_weight',10)*(oh*oh).sum()+profile.get('area_weight',10)*(ah*ah).sum()+profile.get('tether_weight',1e-5)*((x-base)**2).sum())

        stats={'bad_pairs':int((ang>np.pi/2).sum()),'max_degrees':float(np.rad2deg(ang.max())),'minimum_reference_dot':float(rd.min()),'minimum_area_ratio':float((ar/area0).min()),'loss':loss,'maximum_displacement_m':float(np.linalg.norm(x-base,axis=1).max()/1000)}

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

    hard_ref=profile.get('hard_minimum_reference_dot',1e-6)

    hard_area=profile.get('hard_minimum_area_ratio',.1)

    altitude_fraction=profile.get('maximum_altitude_step_fraction',.1)

    if not 0<altitude_fraction<=.2:raise ValueError('Altitude step fraction must be in (0,.2]')

    if hard_ref<=0 or hard_area<.1:raise ValueError('Hard feasibility requires positive reference dot and area ratio >=.1')

    def feasible(stats):

        return (np.isfinite(list(stats.values())).all() and

                stats['minimum_reference_dot']>hard_ref and stats['minimum_area_ratio']>hard_area)

    def projected_step(x, direction):

        delta=x+direction-base;length=np.linalg.norm(delta,axis=1)

        return base+delta*np.minimum(1,caps/np.maximum(length,1e-30))[:,None]

    def altitude_bounds(x):

        q=x[t];cross=np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]);twice_area=np.linalg.norm(cross,axis=1)

        maxedge=np.max(np.linalg.norm(q-np.roll(q,-1,axis=1),axis=2),axis=1)

        tri_alt=twice_area/np.maximum(maxedge,1e-30)

        per_vertex=np.full(len(x),np.inf)

        for j in range(3):np.minimum.at(per_vertex,t[:,j],tri_alt)

        per_vertex[~np.isfinite(per_vertex)]=0

        return altitude_fraction*per_vertex

    def bounded(direction, bounds):

        norm=np.linalg.norm(direction,axis=1)

        return direction*np.minimum(1,bounds/np.maximum(norm,1e-30))[:,None]

    initial=evaluate(x)

    if not feasible(initial):

        raise ValueError('Input infeasible against hard reference/area constraints; no feasible step sequence can be claimed: '+str(initial))

    best=None;best_stats=None;history=[];start=time.perf_counter();accepted=0;rejected=0;fallbacks=0;reason='step_budget'

    def consider(x):

        q=(x/1000).astype(np.float32).astype(float);stats=evaluate(q*1000)

        if not feasible(stats):return None,stats

        return q,stats

    best,best_stats=consider(x)

    if best is None:best_stats=None

    for it in range(1,profile.get('steps',2500)+1):

        stats,g=evaluate(x,True);m=.9*m+.1*g;s=.999*s+.001*g*g

        bounds=altitude_bounds(x)

        adam=-lr*(m/(1-.9**it))/(np.sqrt(s/(1-.999**it))+eps)

        # A stale Adam momentum need not be descent; retry diagonal gradient if needed.

        diagonal=-lr*g/(np.sqrt(s/(1-.999**it))+eps)

        accepted_here=False

        for kind,direction in [('adam',adam),('diagonal_gradient',diagonal)]:

            direction=bounded(direction,bounds)

            alpha=1.

            for bt in range(profile.get('maximum_backtracks',24)):

                candidate=projected_step(x,alpha*direction)

                cand=evaluate(candidate)

                if feasible(cand) and cand['loss']<=stats['loss']:

                    travel=float(np.max(np.linalg.norm(candidate-x,axis=1)))

                    if travel<=profile.get('minimum_step_mm',1e-12):break

                    x=candidate;accepted+=1;accepted_here=True

                    if kind!='adam':fallbacks+=1;m.fill(0)

                    break

                rejected+=1;alpha*=.5

            if accepted_here:break

        if not accepted_here:

            reason='no_feasible_descent_step';break

        if it%profile.get('checkpoint_steps',100)==0 or it==1:

            stats=evaluate(x);stats['step']=it;stats['accepted_alpha']=alpha;stats['direction']=kind;history.append(stats)

            q,qs=consider(x)

            if q is not None and (best_stats is None or (qs['bad_pairs'],round(qs['max_degrees'],6),qs['loss'])<(best_stats['bad_pairs'],round(best_stats['max_degrees'],6),best_stats['loss'])):best=q.copy();best_stats=qs.copy()

            if callback:callback(stats)

    q,qs=consider(x)

    if q is not None and (best_stats is None or (qs['bad_pairs'],round(qs['max_degrees'],6),qs['loss'])<(best_stats['bad_pairs'],round(best_stats['max_degrees'],6),best_stats['loss'])):best=q.copy();best_stats=qs.copy()

    return best,{'initial':initial,'selected':best_stats,'float32':best_stats,'history':history,

                 'seconds':time.perf_counter()-start,'accepted_steps':accepted,'backtracks':rejected,'gradient_fallbacks':fallbacks,

                 'termination':reason,'hard_feasible_float32_candidate':best is not None,

                 'reference_vertices_supplied':reference_vertices is not None,

                 'area_ratio_reference':'input vertices; normal reference may be separately supplied',

                 'movable_vertices':int(mov.sum()),'fixed_vertices':int((~mov).sum()),'topology_changed':False,'uv_changed':False,

                 'constraints_are_optimizer_only':'Actual full pose, intersection, closure, silhouette and texture audits still required'}





