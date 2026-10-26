# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,pathlib,json,numpy as np,math,hashlib,collections
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def tree_for(objects,dg):
    vertices=[];faces=[];owners=[];polygons=[]
    for o in objects:
        ev=o.evaluated_get(dg);m=ev.to_mesh();m.calc_loop_triangles();off=len(vertices)
        vertices.extend([o.matrix_world@v.co for v in m.vertices])
        for t in m.loop_triangles:faces.append(tuple(off+i for i in t.vertices));owners.append(o.name);polygons.append(t.polygon_index)
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(vertices,faces,all_triangles=True),owners,polygons

def prepare(cfg,profile):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root'])
    ref=bpy.data.objects['tripo_node_911d2481'];v=[ref.matrix_world@x.co for x in ref.data.vertices];f=[list(x.vertices) for x in ref.data.polygons];reference=BVHTree.FromPolygons(v,f,all_triangles=True)
    baseline=json.loads((root/'eye-baseline-full-scene-ownership.json').read_text());views=[]
    for yaw in cfg['yaw_degrees']:
        for pitch in cfg['pitch_degrees']:
            y=math.radians(yaw);p=math.radians(pitch);views.append(np.array([math.cos(y)*math.cos(p),math.sin(y)*math.cos(p),math.sin(p)]))
    rays=[];skip=0
    accepted={'INTERNAL_ONLY__SM_000_protected_facial_skin','INTERNAL_ONLY__SM_008_protected_appearance','INTERNAL_ONLY__SM_044_protected_appearance','INTERNAL_ONLY__SM_030_protected_appearance','INTERNAL_ONLY__SM_032_protected_appearance','INTERNAL_ONLY__SM_065_protected_appearance','INTERNAL_ONLY__SM_067_protected_appearance'}
    for group,eye in zip(baseline,profile['character']['eyes']):
        fit=eye['native_fit']
        for row in group['rays']:
            if row['hit'] is None or row['hit_object'] not in accepted:continue
            point=np.array(row['hit']);u=(point[1]-eye['sphere_center'][1])/fit['radius_y'];z=(point[2]-eye['sphere_center'][2])/fit['radius_z'];x=math.sqrt(max(0,1-u*u-z*z))
            for vi,view in enumerate(views):
                origin=point+view*cfg['distance_m'];hit,n,fi,dist=reference.ray_cast(Vector(origin),Vector(-view),cfg['distance_m']+.002)
                if hit is None or abs(dist-cfg['distance_m'])>cfg['reference_visibility_tolerance_m']:skip+=1;continue
                rays.append({'eye':eye['label'],'target':point.tolist(),'origin':origin.tolist(),'direction':(-view).tolist(),'unit_front_x':x,'unit_z':z,'view':vi,'source_object':row['hit_object']})
    contract={'classification':'INTERNAL_ONLY','profile':cfg,'eye_rays':rays,'baseline_occluded_views_recorded':skip,'views':[v.tolist() for v in views]}
    (root/(cfg['revision']+'-probe-contract.json')).write_text(json.dumps(contract,indent=2))
    return contract

def sample(cfg,profile,jaw):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);contract=json.loads((root/(cfg['revision']+'-probe-contract.json')).read_text());scene=bpy.data.scenes[cfg['scene']]
    objects=[o for o in scene.objects if o.type=='MESH'];saved_scene=bpy.context.window.scene
    saved={o.name:[k.value for k in o.data.shape_keys.key_blocks] for o in objects if o.data.shape_keys};mouth=bpy.data.objects[cfg['mouth_object']]
    md=json.loads((root/cfg['mouth_report']).read_text());rimids=md['rim_vertices'];cavity_from=md['cavity_faces_from']
    helper={};exec((root/'scripts'/'sm_eye_integration.py').read_text(),helper)
    rows=[];raw=[];owner_legend=[o.name for o in objects];owner_index={name:i for i,name in enumerate(owner_legend)}
    try:
        bpy.context.window.scene=scene
        for left in cfg['samples']:
            for right in cfg['samples']:
                for o in objects:
                    if not o.data.shape_keys:continue
                    for k in o.data.shape_keys.key_blocks:
                        if k.name!='Basis':k.value=0
                    if 'jawOpen' in o.data.shape_keys.key_blocks:o.data.shape_keys.key_blocks['jawOpen'].value=jaw
                    if 'rounded_lid' in o.name:
                        value=right if 'right_' in o.name else left
                        if value:o.data.shape_keys.key_blocks['blink_'+str(int(value*100))].value=1
                bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get()
                tree,owners,polygons=tree_for(objects,dg);fail=0;eye_counts=collections.Counter();flags=[];witness=[]
                for ri,ray in enumerate(contract['eye_rays']):
                    value=right if ray['eye']=='right' else left
                    angles=cfg['open_angles_degrees'][ray['eye']];xx=ray['unit_front_x'];zz=ray['unit_z']
                    covered=zz>=math.tan(math.radians(angles['upper']*(1-value)))*xx or -zz>=math.tan(math.radians(angles['lower']*(1-value)))*xx
                    if value==1:covered=True
                    if value==0:covered=False
                    hit,n,fi,dist=tree.ray_cast(Vector(ray['origin']),Vector(ray['direction']),cfg['distance_m']+.03)
                    owner=owners[fi] if fi is not None else 'EMPTY';is_lid='rounded_lid' in owner and ray['eye'] in owner
                    is_eye=('native_SM_globe' in owner and ray['eye'] in owner) or owner in cfg['glints'][ray['eye']]
                    if owner==mouth.name and hit is not None:
                        is_eye=np.linalg.norm(np.array(hit)-np.array(ray['target']))<cfg['source_sclera_tolerance_m']
                    ok=is_lid if covered else is_eye
                    if not ok:
                        fail+=1
                        if len(witness)<cfg['witness_limit']:witness.append({'ray':ri,'eye':ray['eye'],'expected':'lid' if covered else 'eye','hit_object':owner,'hit':list(hit) if hit else None})
                    eye_counts[('covered_' if covered else 'open_')+('pass' if ok else 'fail')]+=1
                    flags.append([owner_index.get(owner,-1),int(covered),int(not ok)])
                ev=mouth.evaluated_get(dg);em=ev.to_mesh();rim=np.array([list(mouth.matrix_world@em.vertices[i].co) for i in rimids]);ev.to_mesh_clear()
                empty=unwanted=mouth_total=0;mouth_witness=[];mouth_flags=[]
                cy=md['profile']['center_yz'][0];w=md['profile']['half_width']
                for y in np.linspace(cy-w*.85,cy+w*.85,cfg['mouth_columns']):
                    lo,hi=helper['_bounds'](rim,float(y))
                    for frac in cfg['mouth_vertical_fractions']:
                        target=lo*(1-frac)+hi*frac
                        for vi,view in enumerate(contract['views']):
                            view=np.array(view);origin=target+view*cfg['distance_m'];hit,n,fi,dist=tree.ray_cast(Vector(origin),Vector(-view),cfg['distance_m']+.04);mouth_total+=1
                            owner=owners[fi] if fi is not None else 'EMPTY'
                            posterior=hit is None or hit.x<target[0]-cfg['mouth_depth_limit_m']
                            permitted=(owner==mouth.name and polygons[fi]>=cavity_from) if fi is not None else False
                            permitted=permitted or owner in cfg['oral_objects']
                            anterior=hit is not None and hit.x>target[0]-cfg['mouth_front_clearance_m']
                            bad=(not posterior) and (not permitted or anterior)
                            empty+=int(posterior);unwanted+=int(bad)
                            mouth_flags.append([owner_index.get(owner,-1),int(posterior),int(bad)])
                            if (posterior or bad) and len(mouth_witness)<cfg['witness_limit']:mouth_witness.append({'target':target.tolist(),'view':vi,'hit_object':owner,'hit':list(hit) if hit else None,'posterior_or_empty':bool(posterior),'unwanted':bool(bad)})
                rows.append({'jaw':jaw,'left_blink':left,'right_blink':right,'eye_exposed_or_empty':{'status':'observed','value':fail,'observations':len(flags)},'eye_categories':dict(eye_counts),'mouth_empty_or_posterior':{'status':'observed','value':empty,'observations':mouth_total},'mouth_unwanted_occluders':{'status':'observed','value':unwanted,'observations':mouth_total},'eye_failure_examples':witness,'mouth_failure_examples':mouth_witness})
                raw.append((np.array(flags,np.int16),np.array(mouth_flags,np.int16)))
        output={'classification':'INTERNAL_ONLY','status':'MEASURED_NOT_ACCEPTED','contract_sha256':hashlib.sha256((root/(cfg['revision']+'-probe-contract.json')).read_bytes()).hexdigest(),'jaw':jaw,'owner_legend':owner_legend,'poses':rows}
        suffix=str(int(jaw*100));(root/(cfg['revision']+'-probes-jaw'+suffix+'.json')).write_text(json.dumps(output,indent=2));np.savez_compressed(root/(cfg['revision']+'-probes-jaw'+suffix+'.npz'),eye=np.stack([x[0] for x in raw]),mouth=np.stack([x[1] for x in raw]))
        return {'jaw':jaw,'poses':len(rows),'eye_minmax':[min(r['eye_exposed_or_empty']['value'] for r in rows),max(r['eye_exposed_or_empty']['value'] for r in rows)],'mouth_empty':rows[0]['mouth_empty_or_posterior'],'mouth_occluders':rows[0]['mouth_unwanted_occluders']}
    finally:
        for name,values in saved.items():
            for k,value in zip(bpy.data.objects[name].data.shape_keys.key_blocks,values):k.value=value
        bpy.context.window.scene=saved_scene
