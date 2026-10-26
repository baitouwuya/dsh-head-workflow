# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Positive-weight harmonic depth solve with a fixed rim and eyeball obstacle."""
import bpy,collections,numpy as np
from .eyes import globe,hull

def run(profile,construction):
    cfg=profile['geometry']['fairing'];obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and 'BodyFace' in o.name);mesh=obj.data
    source_keys={k.name:np.array([v.co[:] for v in k.data]) for k in mesh.shape_keys.key_blocks};canonical={};representatives=[];inverse=[]
    for i,p in enumerate(source_keys['Basis']):
        token=tuple(np.round(p,7))
        if token not in canonical:canonical[token]=len(representatives);representatives.append(i)
        inverse.append(canonical[token])
    inverse=np.array(inverse,int);representatives=np.array(representatives,int);keys={n:v[representatives] for n,v in source_keys.items()};base=keys['Basis'];N=len(base);mesh.calc_loop_triangles();tri=inverse[np.array([tuple(t.vertices) for t in mesh.loop_triangles])];tri=tri[(tri[:,0]!=tri[:,1])&(tri[:,0]!=tri[:,2])&(tri[:,1]!=tri[:,2])];adj=collections.defaultdict(set)
    source_signs=[float(np.sign(f.normal.x)) for f in mesh.polygons]
    for edge in mesh.edges:
        a,b=inverse[list(edge.vertices)]
        if a!=b:adj[a].add(b);adj[b].add(a)
    domains=[];middle=np.mean([e['center_yz'][0] for e in profile['character']['eyes']])
    for original_region in construction['regions']:
        region=dict(original_region);region['new_vertices']=sorted(set(inverse[region['new_vertices']]));region['outer']=sorted(set(inverse[region['outer']]));values={}
        for i,t in original_region['vertex_t'].items():
            j=str(int(inverse[int(i)]));values[j]=min(values.get(j,1),t)
        region['vertex_t']=values
        inside=set(region['new_vertices']);domain=inside|set(region['outer']);frontier=set(region['outer'])
        for _ in range(cfg['collar_rings']):
            frontier=set().union(*(adj[i] for i in frontier))-domain;frontier={i for i in frontier if base[i,0]>0 and ((base[i,1]>middle)==(region['eye']=='left'))};domain|=frontier
        outer=set().union(*(adj[i] for i in domain))-domain
        domains.append({'region':region,'domain':domain,'outer':outer,'inside':inside,'eye':next(e for e in profile['character']['eyes'] if e['label']==region['eye'])})
    common=domains[0]['domain']&domains[1]['domain']
    for domain in domains:domain['domain']-=common
    report={'poses':[],'shared_fixed_vertices':len(common)};total=set().union(*(d['domain'] for d in domains));neutral=base.copy()
    def solve(coords,domain,label):
        eye=domain['eye'];region=domain['region'];active=np.array(sorted(domain['domain']),int);mask=np.zeros(N,bool);mask[active]=True
        triangles=tri if cfg['energy']=='biharmonic' else tri[np.any(mask[tri],axis=1)];yz=coords[:,1:];edge_weights=collections.defaultdict(float)
        for ia,ib,ic in triangles:
            for a,b,c in [(ia,ib,ic),(ib,ic,ia),(ic,ia,ib)]:
                u=yz[a]-yz[c];v=yz[b]-yz[c];area=abs(u[0]*v[1]-u[1]*v[0]);weight=min(cfg['maximum_edge_weight'],max(float(np.dot(u,v)/max(area,1e-20)),cfg['minimum_edge_weight']));edge_weights[tuple(sorted((int(a),int(b))))]+=weight
        edges=np.array(list(edge_weights),int);a,b=edges.T;w=np.array(list(edge_weights.values()));degree=np.bincount(a,w,minlength=N)+np.bincount(b,w,minlength=N);fidelity=np.zeros(N);fidelity[active]=degree[active]*cfg['surface_fidelity'];collar=np.array(sorted(domain['domain']-domain['inside']),int);fidelity[collar]=degree[collar]*cfg['collar_fidelity']
        polygon=hull(np.array(eye['rim_xyz'])[:,1:]);inside_eye=np.array([i for i in active if all(np.cross(v-u,yz[i]-u)>=-1e-12 for u,v in zip(polygon,np.roll(polygon,-1,axis=0)))],int);floor=np.full(N,-np.inf)
        for i in inside_eye:floor[i]=globe(eye,*yz[i])+profile['geometry']['eyes']['globe_clearance']
        rim=np.array([int(i) for i,t in region['vertex_t'].items() if t==1 and polygon[:,0].min()-1e-10<=coords[int(i),1]<=polygon[:,0].max()+1e-10 and int(i) in domain['domain']],int)
        x=coords[:,0].copy();fixed=~mask
        for i in rim:x[i]=globe(eye,*yz[i])+profile['geometry']['eyes']['globe_clearance']
        fixed[rim]=True;initial=x.copy();iterations=0;residual=None
        def lap(v):
            d=w*(v[a]-v[b]);return np.bincount(a,d,minlength=N)-np.bincount(b,d,minlength=N)
        def energy(v):return lap(lap(v)/np.maximum(degree,1e-30)) if cfg['energy']=='biharmonic' else lap(v)
        energy_diagonal=degree.copy()
        if cfg['energy']=='biharmonic':energy_diagonal+=np.bincount(a,w*w/np.maximum(degree[b],1e-30),minlength=N)+np.bincount(b,w*w/np.maximum(degree[a],1e-30),minlength=N)
        for active_pass in range(cfg['obstacle_passes']):
            free=~fixed;boundary=np.where(fixed,x,0);rhs=(fidelity*initial-energy(boundary))*free;diagonal=np.maximum(energy_diagonal+fidelity,1e-30)
            def operator(v):return (energy(v*free)+fidelity*v)*free
            solution=np.where(free,x,0);r=(rhs-operator(solution))*free;z=r/diagonal;p=z.copy();rz=float(np.dot(r,z))
            for iteration in range(cfg['max_iterations']):
                ap=operator(p);den=float(np.dot(p,ap))
                if den<=1e-30:break
                alpha=rz/den;solution+=alpha*p;r-=alpha*ap;iterations+=1
                if float(np.max(abs(r)/diagonal))<cfg['tolerance']:break
                z=r/diagonal;new_rz=float(np.dot(r,z));p=z+(new_rz/max(rz,1e-300))*p;rz=new_rz
            x=np.where(free,solution,x);residual=float(np.max(abs(rhs-operator(solution))/diagonal));violating=free&(x<floor-cfg['tolerance'])
            if not np.any(violating):break
            x[violating]=floor[violating];fixed[violating]=True
        report['poses'].append({'eye':eye['label'],'pose':label,'vertices':len(active),'iterations':iterations,'normalized_residual':residual,'maximum_x_shift':float(np.max(abs(x[active]-coords[active,0]))),'obstacle_violations':int(np.count_nonzero(mask&(x<floor-cfg['tolerance'])))})
        print('FAIRING_POSE',report['poses'][-1],flush=True)
        result=coords.copy();result[active,0]=x[active]
        count=np.bincount(a,minlength=N)+np.bincount(b,minlength=N);movable=mask.copy();movable[rim]=False;anchors=result.copy()
        for _ in range(cfg['tangential_iterations']):
            for strength in [cfg['tangential_lambda'],cfg['tangential_mu']]:
                average=np.column_stack([(np.bincount(a,result[b,axis],minlength=N)+np.bincount(b,result[a,axis],minlength=N))/np.maximum(count,1) for axis in range(3)])
                result[movable]+=strength*(average[movable]-result[movable]);result[~movable]=anchors[~movable]
            yz_now=result[active,1:];covered=np.ones(len(active),bool)
            for u,v in zip(polygon,np.roll(polygon,-1,axis=0)):covered&=((v[0]-u[0])*(yz_now[:,1]-u[1])-(v[1]-u[1])*(yz_now[:,0]-u[0]))>=-1e-12
            ids=active[covered];gx,gy,gz=eye['sphere_center'];radius=eye['sphere_radius'];affine=eye['affine_globe'];yy=result[ids,1]-gy;zz=result[ids,2]-gz;minimum=gx+affine['depth_scale']*np.sqrt(np.maximum(radius*radius*.02,radius*radius-yy*yy-zz*zz))+affine['shear_y']*yy+affine['shear_z']*zz+profile['geometry']['eyes']['globe_clearance'];result[ids,0]=np.maximum(result[ids,0],minimum)
        report['poses'][-1]['tangential_maximum_shift']=float(np.max(np.linalg.norm(result-anchors,axis=1)))
        return result
    for domain in domains:neutral=solve(neutral,domain,'Basis')
    delta=neutral-base;updated={name:values+delta for name,values in keys.items()}
    for domain in domains:
        for percent in [25,50,75,100]:
            name='blink'+domain['eye']['label'].capitalize()+'_'+str(percent)
            if name in updated:updated[name]=solve(updated[name],domain,name)
    expanded={}
    for name,values in updated.items():
        arr=source_keys[name].copy();arr+=(values-keys[name])[inverse];expanded[name]=arr
    for key in mesh.shape_keys.key_blocks:key.data.foreach_set('co',expanded[key.name].astype(np.float32).ravel());key.value=0
    mesh.vertices.foreach_set('co',expanded['Basis'].astype(np.float32).ravel());normals=[tuple(n.vector) for n in mesh.corner_normals];attribute=mesh.attributes.new(name='dsh_repair_audit',type='BOOLEAN',domain='FACE');reference=mesh.attributes.new(name='dsh_source_projection_sign',type='FLOAT',domain='FACE');changed=[]
    for face in mesh.polygons:
        reference.data[face.index].value=source_signs[face.index]
        if any(inverse[i] in total for i in face.vertices):
            attribute.data[face.index].value=True;changed.append(face.index)
            for li in face.loop_indices:normals[li]=(0,0,0)
    mesh.normals_split_custom_set(normals);mesh.update();bpy.context.view_layer.update();report['changed_faces']=len(changed);report['maximum_neutral_shift']=float(np.max(abs(delta)));report['source_vertices']=len(inverse);report['coupled_positions']=N;return report
