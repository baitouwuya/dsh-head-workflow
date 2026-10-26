# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,bmesh,numpy as np,pathlib,json,math,collections
from mathutils import Matrix,Vector
def build(cfg):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);src=bpy.data.objects[cfg['source']]
    scene=bpy.data.scenes.new('INTERNAL_ONLY_integrated_'+cfg['revision'])
    for o in bpy.data.scenes[cfg['reference_scene']].objects:
        if o.name!=cfg['replace_object']:scene.collection.objects.link(o)
    mesh=src.data.copy();scale=cfg.get('storage_units_per_m',1.0);origin=cfg.get('storage_origin',[0,0,0]);world_matrix=Matrix.Translation(Vector(origin))@Matrix.Scale(1/scale,4);M=np.array(world_matrix,float);invM=np.linalg.inv(M);sourceM=np.array(src.matrix_world,float);sourceP=np.array([list(v.co) for v in src.data.vertices]);worldP=sourceP@sourceM[:3,:3].T+sourceM[:3,3];localP=worldP@invM[:3,:3].T+invM[:3,3];mesh.vertices.foreach_set('co',localP.astype(np.float32).ravel());body=bpy.data.objects.new('INTERNAL_ONLY_SM_boolean_mouth_'+cfg['revision'],mesh);body.matrix_world=world_matrix;scene.collection.objects.link(body)
    material=bpy.data.materials.get('INTERNAL_ONLY_own_oral_dark_mouth-002.001') or next(m for m in bpy.data.materials if m.name.startswith('INTERNAL_ONLY_own_oral_dark'))
    if len(mesh.materials)==1:mesh.materials.append(material)
    cy,cz=cfg['center_yz'];n=cfg['angular_segments'];verts=[];faces=[];rings=[]
    inner_width=cfg.get('neck_inner_half_width',cfg['mouth_half_width'])
    profiles=[(cfg['outside_front_x'],cfg['mouth_half_width'],cfg['mouth_half_height'])]
    if cfg.get('neck_front_x'):profiles.append((cfg['neck_front_x'],cfg['mouth_half_width'],cfg['mouth_half_height']))
    profiles.append((cfg['narrow_until_x'],inner_width,cfg['mouth_half_height']))
    for j in range(1,cfg['depth_rows']+1):
        t=j/cfg['depth_rows'];x=cfg['narrow_until_x']+(cfg['rear_x']-cfg['narrow_until_x'])*t
        swell=math.sin(math.pi*t);ry=inner_width*(1-t)+cfg['interior_half_width']*swell
        rz=cfg['mouth_half_height']*(1-t)+cfg['interior_half_height']*swell
        if j==cfg['depth_rows']:continue
        profiles.append((x,ry,rz))
    for x,ry,rz in profiles:
        ring=[]
        for i in range(n):
            a=2*math.pi*i/n;ring.append(len(verts));verts.append([x,cy+ry*math.cos(a),cz+rz*math.sin(a)])
        rings.append(ring)
    front=len(verts);verts.append([cfg['outside_front_x'],cy,cz])
    for i in range(n):faces.append([front,rings[0][i],rings[0][(i+1)%n]])
    for a,b in zip(rings,rings[1:]):
        for i in range(n):
            j=(i+1)%n;faces.extend([[a[j],a[i],b[i]],[a[j],b[i],b[j]]])
    rear=len(verts);verts.append([cfg['rear_x'],cy,cz])
    for i in range(n):faces.append([rings[-1][(i+1)%n],rings[-1][i],rear])
    cm=bpy.data.meshes.new('INTERNAL_ONLY_cavity_cutter_'+cfg['revision']);cm.from_pydata((np.array(verts)@invM[:3,:3].T+invM[:3,3]).tolist(),[],faces);cm.update()
    bm=bmesh.new();bm.from_mesh(cm);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(cm);bm.free();cm.materials.append(mesh.materials[0]);cm.materials.append(material)
    for f in cm.polygons:f.material_index=1
    cutter=bpy.data.objects.new('INTERNAL_ONLY_cavity_cutter_'+cfg['revision'],cm);cutter.matrix_world=world_matrix;scene.collection.objects.link(cutter)
    saved=bpy.context.window.scene
    try:
        bpy.context.window.scene=scene;bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
        mod=body.modifiers.new('Local anatomical cavity','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter;mod.use_self=cfg.get('solve_self_intersections',False)
        bpy.ops.object.modifier_apply(modifier=mod.name)
        scene.collection.objects.unlink(cutter)
        m=body.data;bm=bmesh.new();bm.from_mesh(m)
        if cfg.get('cleanup_tolerance_m',0)>0:
            bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=cfg['cleanup_tolerance_m']*scale)
            bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=cfg['cleanup_tolerance_m'])
        bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(m);bm.free();m.update()
        local_base=np.array([list(v.co) for v in m.vertices]);base=local_base@M[:3,:3].T+M[:3,3];fs=[list(f.vertices) for f in m.polygons]
        lining=[f.index for f in m.polygons if f.material_index==1];edges=collections.defaultdict(list)
        for i,f in enumerate(fs):
            for a,b in zip(f,f[1:]+f[:1]):edges[tuple(sorted((a,b)))].append(i)
        seam=[e for e,uses in edges.items() if len(uses)==2 and (m.polygons[uses[0]].material_index==1)!=(m.polygons[uses[1]].material_index==1)]
        rim=sorted({v for e in seam for v in e})
        if not rim:raise RuntimeError('Boolean produced no source/lining entrance seam')
        # Use the actual cutting-volume boundary, not a rear surface, for all probes.
        u=(base[:,1]-cy)/cfg['mouth_half_width'];smooth=lambda t:np.clip(t,0,1)**2*(3-2*np.clip(t,0,1))
        side=smooth((np.abs(base[:,1]-cy)-cfg['mouth_half_width']*.75)/(cfg['mouth_half_width']*.5))
        band=np.maximum(cfg['mouth_half_height']*np.sqrt(np.maximum(0,1-u*u)),.00002)+.003*side
        weight=smooth((cz+band-base[:,2])/(2*band))*(1-smooth((np.abs(base[:,1]-cy)-.02)/.02))*smooth((base[:,2]-.84)/.015)
        pivot=np.array(cfg['jaw_pivot']);ang=np.radians(cfg['jaw_degrees']);rel=base-pivot;rot=rel.copy();rot[:,0]=np.cos(ang)*rel[:,0]+np.sin(ang)*rel[:,2];rot[:,2]=-np.sin(ang)*rel[:,0]+np.cos(ang)*rel[:,2]
        if cfg.get('jaw_anterior_only'):weight*=smooth((base[:,0]+.015)/.02)
        target=base+(rot+pivot-base)*weight[:,None]
        body.shape_key_add(name='Basis');key=body.shape_key_add(name='jawOpen');key.value=0;key.data.foreach_set('co',(target@invM[:3,:3].T+invM[:3,3]).astype(np.float32).ravel())
        for f in m.polygons:f.use_smooth=True
        audits=[]
        for deg in cfg['jaw_samples_degrees']:
            v=base+(target-base)*(deg/cfg['jaw_degrees']);a=bpy.app.driver_namespace['dsh_private_topology_core']['analyze'](v,fs,fs,np.arange(len(fs)),reference_local_vertices=base,local_vertices=v)
            audits.append({'degrees':deg,**{k:a[k] for k in ['boundary_edges','nonmanifold_edges','same_direction_edges','degenerate_triangles','adjacent_normal_degrees','reference_normal_reversals']}})
        report={'classification':'INTERNAL_ONLY','status':'UNACCEPTED','profile':cfg,'object':body.name,'scene':scene.name,'lining_faces':lining,'entrance_vertices':rim,'entrance_edges':seam,'audit':audits,'cutter':cutter.name}
        (root/(cfg['revision']+'-boolean-mouth.json')).write_text(json.dumps(report,indent=2));return report
    finally:bpy.context.window.scene=saved
