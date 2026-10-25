# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Reconstruction stage; invoked by the head workflow runner."""

def run(h):
    import bpy,math,json,numpy as np
    from mathutils import Vector
    
    h.set_jaw(0)
    cy=sum(h.lip['y_range'])/2;ry=(h.lip['y_range'][1]-h.lip['y_range'][0])/2;cz=float(np.polyval(h.lip['fit_z_of_y_coefficients'],cy))
    poly=h.mouth_region['polygon'];center=poly.mean(0)
    # The source has several overlapping facial sheets. Use the full aperture envelope,
    # not the smaller closed sub-loop found on one sheet.
    ids=sorted(set(i for p in h.boundaries[h.body.name]['mouth'] if p['mean_x']>.020 for i in p['ids']))
    points=np.array([h.body.data.vertices[i].co[:] for i in ids]);design=np.array([points[:,1]*0+1,points[:,1]-cy,points[:,2]-cz]).T
    coef=np.linalg.lstsq(design,points[:,0],rcond=None)[0]
    N=h.config['oral_rim_samples'];rim=[];rimweights=[];source_samples=[]
    def smooth(x):
        x=max(0,min(1,x));return x*x*(3-2*x)
    for j in range(N):
        angle=2*math.pi*j/N;direction=np.array([math.cos(angle)*ry,math.sin(angle)*.001]);hits=[]
        for a,b in zip(poly,np.roll(poly,-1,axis=0)):
            mat=np.column_stack((direction,a-b))
            if abs(np.linalg.det(mat))<1e-12:continue
            t,u=np.linalg.solve(mat,a-center)
            if t>0 and -.00001<=u<=1.00001:hits.append(t)
        t=min(hits);yz=center+direction*t*1.06;y,z=yz;x=float(np.dot(coef,[1,y-cy,z-cz]))-.00010
        rim.append([x,y,z])
        line=float(np.polyval(h.lip['fit_z_of_y_coefficients'],y))
        local=smooth((line+.00008-z)/.00040)
        base=smooth((cz+.003-z)/.016);influence=math.exp(-((y-cy)/(ry*1.65))**4)*math.exp(-((z-cz)/.012)**4)
        rimweights.append(base*(1-influence)+local*influence)
        source_samples.append(h.sample(h.src_body,y,z))
    rim=np.array(rim);verts=[];weights=[];rings=h.config['oral_rings']
    for row in range(rings):
        t=row/(rings-1)
        for j,p in enumerate(rim):
            q=p.copy();q[0]-=h.config['oral_depth']*t;q[1]=cy+(p[1]-cy)*(1+.45*math.sin(math.pi*t)-.2*t)
            mid=float(np.polyval(h.lip['fit_z_of_y_coefficients'],p[1]))
            q[2]+=(1 if p[2]>=mid else -1)*.0035*math.sin(math.pi*t*.75)
            verts.append(q.tolist());weights.append(rimweights[j]*(1-.2*t)+.4*.2*t)
    faces=[]
    for row in range(rings-1):
        for j in range(N):faces.append([row*N+j,row*N+(j+1)%N,(row+1)*N+(j+1)%N,(row+1)*N+j])
    cap=len(verts);verts.append(np.mean(np.array(verts[-N:]),axis=0).tolist());weights.append(.4)
    for j in range(N):faces.append([(rings-1)*N+j,(rings-1)*N+(j+1)%N,cap])
    oldmat=h.oral.data.materials[0];mesh=bpy.data.meshes.new('dsh-full-envelope-oral-lining');mesh.from_pydata(verts,[],faces);mesh.update();mesh.materials.append(oldmat);h.oral.data=mesh
    for f in mesh.polygons:f.use_smooth=True
    h.oral.vertex_groups.clear()
    hg=h.oral.vertex_groups.new(name=h.config['head_bone']);jg=h.oral.vertex_groups.new(name='dsh_Jaw')
    for i,w in enumerate(weights):hg.add([i],1-w,'REPLACE');jg.add([i],w,'REPLACE')
    h.oral.shape_key_add(name='Basis',from_mix=False)
    for name in h.old_controls:
        d=[]
        ks=h.src_body.data.shape_keys.key_blocks
        for sample in source_samples:
            delta=sum((np.array(ks[name].data[i].co)-np.array(ks['Basis'].data[i].co))*w for i,w in zip(sample['ids'],sample['weights'])) if sample else np.zeros(3)
            d.append(delta)
        d=np.array(d);arr=np.array(verts,np.float32)
        for row in range(rings):arr[row*N:(row+1)*N]+=d*(1-.5*row/(rings-1))
        arr[-1]+=d.mean(0)*.5;key=h.oral.shape_key_add(name=name,from_mix=False);key.data.foreach_set('co',arr.ravel());key.value=0
    h.jaw_range=h.config['jaw_max_degrees']
    (h.root/'oral-envelope-repair.json').write_text(json.dumps({'reason':'Initial closed sub-loop covered only part of the multi-sheet source aperture and exposed the back of the head. Rebuilt over the full source cut envelope.','rim_vertices':N,'vertices':len(verts),'depth':.018,'jaw_range_degrees':h.jaw_range,'front_rim_fit':'Full convex-cut envelope expanded 6 percent under the lip skin; coordinate-fit overlap, not a single welded skin boundary.'},indent=2))
    h.set_jaw(1);h.render('jaw-open',views={'front':h.views['front'],'left45':h.views['left45']});h.set_jaw(0)
    print('ORAL_ENVELOPE_REPAIRED')
