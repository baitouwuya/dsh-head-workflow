# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
def relax_folds(vertices, triangles, options):
    import numpy as np,collections
    p=np.asarray(vertices,float).copy();t=np.asarray(triangles,int);edges=collections.defaultdict(list);adj=[set() for _ in p]
    for fi,f in enumerate(t):
        for a,b in zip(f,np.roll(f,-1)):
            edges[tuple(sorted((int(a),int(b))))].append(fi);adj[a].add(int(b));adj[b].add(int(a))
    pairs=np.asarray([u for u in edges.values() if len(u)==2],int)
    neighbors=[np.array(sorted(a),int) for a in adj]
    limit=float(options['target_degrees'])
    floor=np.cos(np.radians(limit))
    def measure(v):
        q=v[t];n=np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]);areas=np.linalg.norm(n,axis=1);n/=np.maximum(areas[:,None],1e-30)
        d=np.clip(np.sum(n[pairs[:,0]]*n[pairs[:,1]],axis=1),-1,1)
        return d,areas
    history=[]
    original=p.copy()
    for step in range(options['iterations']):
        dots,areas=measure(p);bad=np.flatnonzero(dots<floor)
        if not len(bad):break
        energy=float(np.sum(np.maximum(floor-dots,0)**2))
        active=np.unique(t[pairs[bad]].ravel())
        movement=np.array([p[neighbors[i]].mean(axis=0)-p[i] for i in active])
        accepted=False
        for rate in [0.25,0.1,0.03,0.01]:
            trial=p.copy();trial[active]+=movement*rate
            d,a=measure(trial);en=float(np.sum(np.maximum(floor-d,0)**2))
            if en<energy and a.min()>1e-15:
                p=trial;accepted=True;break
        history.append({'iteration':step,'violating_pairs':len(bad),'max_angle':float(np.degrees(np.arccos(dots.min()))),'energy':energy,'accepted':accepted})
        if not accepted:break
    dots,areas=measure(p)
    return p,{'steps':history,'max_angle':float(np.degrees(np.arccos(dots.min()))),'remaining_over_90':int((dots<0).sum()),'min_double_area_m2':float(areas.min()),'max_displacement_m':float(np.linalg.norm(p-original,axis=1).max())}
