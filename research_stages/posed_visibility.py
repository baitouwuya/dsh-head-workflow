# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,pathlib,json,numpy as np,collections,math,hashlib
def initialize(cfg):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);scene=bpy.data.scenes[cfg['scene']];body=bpy.data.objects[cfg['body']];m=body.data
    code={};exec((root/'scripts'/'contract_probes.py').read_text(),code);objects=[o for o in scene.objects if o.type=='MESH'];saved_scene=bpy.context.window.scene
    saved={o.name:[k.value for k in o.data.shape_keys.key_blocks] for o in objects if o.data.shape_keys};f=np.array([list(p.vertices) for p in m.polygons]);edges=collections.defaultdict(list)
    for i,t in enumerate(f):
        for a,b in zip(t,np.roll(t,-1)):edges[tuple(sorted((int(a),int(b))))].append(i)
    if m.attributes.get('native_cap_declared_shell'):
        edges=collections.defaultdict(list);canonical={}
        for fi,t in enumerate(f):
            shell=m.attributes['native_cap_declared_shell'].data[fi].value;ct=[]
            for v in t:
                key=(shell,tuple(m.vertices[int(v)].co));ct.append(canonical.setdefault(key,int(v)))
            for a,b in zip(ct,ct[1:]+ct[:1]):edges[tuple(sorted((a,b)))].append(fi)
    pairs=[(e,u) for e,u in edges.items() if len(u)==2];vertices=[];normals=[]
    try:
        bpy.context.window.scene=scene
        for deg in cfg['degrees']:
            code['apply'](objects,deg,0,0);bpy.context.view_layer.update();ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());em=ev.to_mesh();v=np.array([list(body.matrix_world@x.co) for x in em.vertices]);ev.to_mesh_clear();q=v[f];n=np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]);n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-30);vertices.append(v);normals.append(n)
    finally:
        for name,vals in saved.items():
            for k,value in zip(bpy.data.objects[name].data.shape_keys.key_blocks,vals):k.value=value
        bpy.context.window.scene=saved_scene
    normals=np.array(normals);rows=[]
    for edge,uses in pairs:
        angles=np.degrees(np.arccos(np.clip(np.sum(normals[:,uses[0]]*normals[:,uses[1]],axis=1),-1,1)))
        if (angles>90).any():rows.append({'kind':'fold','edge':edge,'faces':uses,'values':angles.tolist(),'bad_poses':np.flatnonzero(angles>90).tolist(),'reachable':False,'unresolved':0,'observations':0,'blocked_by':{},'pose_evidence':[]})
    for fi in range(len(f)):
        dots=np.sum(normals[:,fi]*normals[0,fi],axis=1)
        if (dots<0).any():rows.append({'kind':'reference_normal_reversal','faces':[fi],'values':dots.tolist(),'bad_poses':np.flatnonzero(dots<0).tolist(),'reachable':False,'unresolved':0,'observations':0,'blocked_by':{},'pose_evidence':[]})
    np.savez_compressed(root/(cfg['revision']+'-geometry.npz'),vertices=np.array(vertices,np.float32),triangles=f,normals=normals)
    report={'classification':'INTERNAL_ONLY','profile':cfg,'rows':rows,'completed_pose_indices':[],'occluder_policy':'All current meshes except eyelids. Removing eyelid occluders conservatively covers every blink state; opaque remaining materials retain actual backface culling.'}
    (root/(cfg['revision']+'-visibility.json')).write_text(json.dumps(report,indent=2));return collections.Counter(x['kind'] for x in rows)
def sample(revision,index):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);path=root/(revision+'-visibility.json');report=json.loads(path.read_text());cfg=report['profile'];data=np.load(root/(revision+'-geometry.npz'));v=data['vertices'][index].astype(float);f=data['triangles'];normals=data['normals'][index]
    if index in report['completed_pose_indices']:raise RuntimeError('Pose already recorded')
    ns={};exec((root/'scripts'/'contract_probes.py').read_text(),ns);scene=bpy.data.scenes[cfg['scene']];objects=[o for o in scene.objects if o.type=='MESH'];occluders=[o for o in objects if 'rounded_lid' not in o.name];body=bpy.data.objects[cfg['body']]
    dirs=[]
    for i in range(cfg['directions']):
        z=1-2*(i+.5)/cfg['directions'];phi=i*np.pi*(3-np.sqrt(5));r=np.sqrt(1-z*z);dirs.append([r*np.cos(phi),r*np.sin(phi),z])
    dirs.extend([[x,y,z] for x in [-1,0,1] for y in [-1,0,1] for z in [-1,0,1] if x*x+y*y+z*z]);dirs=np.array(dirs);dirs/=np.linalg.norm(dirs,axis=1)[:,None]
    saved_scene=bpy.context.window.scene;saved={o.name:[k.value for k in o.data.shape_keys.key_blocks] for o in objects if o.data.shape_keys}
    try:
        bpy.context.window.scene=scene;ns['apply'](objects,cfg['degrees'][index],0,0);bpy.context.view_layer.update();tree,names,fis,bp,vv,ff,culling=ns['evaluate'](occluders,bpy.context.evaluated_depsgraph_get(),body.name)
        if np.max(np.abs(bp-v))>1e-8:raise RuntimeError('Pose cache differs from evaluated body')
        for row in report['rows']:
            if row['reachable'] or index not in row['bad_poses']:continue
            blocked=collections.Counter();observed=missing=0;clearance_min=1e10;witness=None
            for fi in row['faces']:
                tri=v[f[fi]];center=tri.mean(axis=0);points=[center]
                if row['kind']=='fold':
                    a,b=v[row['edge']];points.extend([.95*(a*(1-t)+b*t)+.05*center for t in cfg['edge_parameters']])
                else:
                    points.extend([.8*x+.2*center for x in tri])
                mat=body.data.materials[body.data.polygons[fi].material_index]
                view_ids=np.flatnonzero(dirs@normals[fi]>0) if mat.use_backface_culling else np.arange(len(dirs))
                for point in points:
                    for di in view_ids:
                        direction=dirs[di];origin=point+direction*cfg['distance_m'];hit,n,face,dist,skips=ns['rendered_hit'](tree,vv,ff,culling,origin,-direction,cfg['distance_m']+cfg['tolerance_m'])
                        if face is None:missing+=1;continue
                        clearance=cfg['distance_m']-dist
                        if abs(clearance)<=cfg['tolerance_m']:
                            observed+=1;witness={'degrees':cfg['degrees'][index],'point':point.tolist(),'view_direction':direction.tolist(),'triangle':fi,'first_hit_object':names[face],'first_hit_face':fis[face],'clearance_m':clearance};break
                        if clearance>cfg['tolerance_m']:observed+=1;blocked[names[face]]+=1;clearance_min=min(clearance_min,clearance)
                        else:missing+=1
                    if witness:break
                if witness:break
            row['observations']+=observed;row['unresolved']+=missing
            for name,count in blocked.items():row['blocked_by'][name]=row['blocked_by'].get(name,0)+count
            row['pose_evidence'].append({'degrees':cfg['degrees'][index],'observations':observed,'unresolved':missing,'minimum_blocker_clearance_m':None if clearance_min==1e10 else clearance_min})
            if witness:row['reachable']=True;row['witness']=witness
        report['completed_pose_indices'].append(index)
        for row in report['rows']:
            row['classification']='reachable' if row['reachable'] else ('indeterminate' if row['unresolved'] or not row['observations'] else 'hidden_in_sampled_views')
        report['counts']={kind:{cl:sum(x['kind']==kind and x['classification']==cl for x in report['rows']) for cl in ['reachable','hidden_in_sampled_views','indeterminate']} for kind in ['fold','reference_normal_reversal']}
        path.write_text(json.dumps(report,indent=2));return report['counts']
    finally:
        for name,values in saved.items():
            for k,value in zip(bpy.data.objects[name].data.shape_keys.key_blocks,values):k.value=value
        bpy.context.window.scene=saved_scene
