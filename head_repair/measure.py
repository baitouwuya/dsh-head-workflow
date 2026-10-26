# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Raw observations. Acceptance limits are deliberately absent."""
import bpy,math,collections,numpy as np
from .controls import apply,positions

def geometry(profile,manifest):
    body=next(o for o in bpy.context.scene.objects if o.type=='MESH' and 'BodyFace' in o.name)
    audit_attribute=body.data.attributes.get('dsh_repair_audit')
    reference_positions=np.array([v.co[:] for v in body.data.vertices])
    faces=[f for f in body.data.polygons if any(s in body.data.materials[f.material_index].name for s in ['SEM_new_lip','dsh-continuous-eyelid']) or (audit_attribute and audit_attribute.data[f.index].value)]
    body.data.calc_loop_triangles();tessellation={f.index:[] for f in faces}
    for t in body.data.loop_triangles:
        if t.polygon_index in tessellation:tessellation[t.polygon_index].append(tuple(t.vertices))
    triangles=np.array([tuple(t.vertices) for t in body.data.loop_triangles],dtype=int).reshape(-1,3);owners=[t.polygon_index for t in body.data.loop_triangles];edges=collections.defaultdict(list)
    for i,tri in enumerate(triangles):
        for a,b in zip(tri,np.roll(tri,-1)):edges[tuple(sorted((int(a),int(b))))].append(i)
    pairs=[]
    for ids in edges.values():
        if len(ids)!=2 or not any(owners[i] in tessellation for i in ids):continue
        if any('oral-interior' in body.data.materials[body.data.polygons[owners[i]].material_index].name for i in ids):continue
        pairs.append(ids)
    pairs=np.array(pairs,dtype=int).reshape(-1,2)
    poses=[('jaw_'+str(d),{'degrees':d}) for d in profile['sampling']['jaw_degrees']]+[('blink_'+str(w),{'blink':w}) for w in profile['sampling']['blink_weights']]
    rows=[]
    for name,values in poses:
        apply(manifest,values);ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh();p=np.array([v.co[:] for v in me.vertices]);ev.to_mesh_clear();angles=[];flips=[];worst=[];projected_observations=0
        for f in faces:
            normals=[np.cross(p[b]-p[a],p[c]-p[a]) for a,b,c in tessellation[f.index]];n=np.array(normals,dtype=float).reshape(-1,3);length=np.linalg.norm(n,axis=1)
            projected_observations+=int(np.count_nonzero(length>1e-15))
            authored=any(s in body.data.materials[f.material_index].name for s in ['SEM_new_lip','dsh-continuous-eyelid'])
            reference=np.ones(len(n)) if authored else np.array([np.sign(np.cross(reference_positions[b]-reference_positions[a],reference_positions[c]-reference_positions[a])[0]) for a,b,c in tessellation[f.index]])
            if np.any(n[:,0]*reference<-1e-14):flips.append(f.index)
            if len(f.vertices)==4 and len(n)==2 and np.all(length>1e-15):
                angle=math.degrees(math.acos(float(np.clip(np.dot(n[0],n[-1])/(length[0]*length[-1]),-1,1))));angles.append(angle);worst.append((angle,f.index))
        q=p[triangles];norms=np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0]);lengths=np.linalg.norm(norms,axis=1);unit=norms/np.maximum(lengths[:,None],1e-30);valid=(lengths[pairs[:,0]]>1e-15)&(lengths[pairs[:,1]]>1e-15);tested=pairs[valid];dots=np.sum(unit[tested[:,0]]*unit[tested[:,1]],axis=1);adj_angles=np.degrees(np.arccos(np.clip(dots,-1,1)));rank=np.argsort(adj_angles)[-10:][::-1]
        rows.append({'pose':name,'projected_flips':len(flips) if projected_observations else None,'projected_triangle_observations':projected_observations,'flipped_face_ids':flips,'quad_normal_max_degrees':max(angles) if angles else None,'quad_normal_observations':len(angles),'worst_quads':sorted(worst,reverse=True)[:12],'adjacent_triangle_max_degrees':float(adj_angles.max()) if len(adj_angles) else None,'adjacent_triangle_observations':len(adj_angles),'worst_adjacent_faces':[[float(adj_angles[i]),[owners[j] for j in tested[i]]] for i in rank]})
    apply(manifest,{})
    return rows

def controls(profile,manifest):
    apply(manifest,{});base=positions();eyes=[n for n in base if 'closed-globe' in n];rows=[];reset_error=0;nonfinite=0;eye_move=0;jaw_error=0
    poses=[(n,{n:1}) for n in manifest['original_controls']+manifest['added_morphs']]
    poses += [('jaw_'+str(d),{'degrees':d}) for d in profile['sampling']['jaw_degrees']]
    poses += [('blink'+side+'_'+str(w),{'blink'+side:w}) for side in ['','Left','Right'] for w in profile['sampling']['blink_weights']]
    poses += [(n,v) for n,v in manifest['recipes'].items()]
    for name,values in poses:
        apply(manifest,values);p=positions();move={n:float(np.linalg.norm(p[n]-v,axis=1).max()) for n,v in base.items()};nonfinite+=sum(int(np.count_nonzero(~np.isfinite(v))) for v in p.values())
        expected=values.get('degrees',values.get('jawOpen',0)*manifest['jaw']['maximum_degrees']);rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');actual=math.degrees(rig.pose.bones[manifest['jaw']['bone']].rotation_quaternion.angle);jaw_error=max(jaw_error,abs(actual-expected))
        if name.startswith(('blink','jaw_')):eye_move=max(eye_move,max([move[n] for n in eyes],default=0))
        apply(manifest,{});reset=positions();err=max(float(np.max(abs(reset[n]-v))) for n,v in base.items());reset_error=max(reset_error,err);rows.append({'pose':name,'values':values,'movement':move,'reset_error':err,'jaw_degrees_observed':actual})
    return {'rows':rows,'metrics':{'nonfinite':nonfinite,'reset_error':reset_error,'eye_displacement_blink_jaw':eye_move,'jaw_angle_error':jaw_error,'minimum_tested_jaw_degrees':max(profile['sampling']['jaw_degrees'])}}
