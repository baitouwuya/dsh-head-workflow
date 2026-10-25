# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Reconstruction stage; invoked by the head workflow runner."""

def run(h):
    import bpy,json,numpy as np,collections
    
    h.controls({})
    # Explicitly normalize the candidate to the four influences supported by the review engine.
    skin_audit=[]
    for obj in h.model_objects:
        if obj.type!='MESH':continue
        changed=0;max_dropped=0
        for vert in obj.data.vertices:
            groups=sorted([(g.group,g.weight) for g in vert.groups if g.weight>1e-8],key=lambda x:-x[1])
            if len(groups)<=4:continue
            dropped=sum(w for gi,w in groups[4:]);total=sum(w for gi,w in groups[:4]);max_dropped=max(max_dropped,dropped);changed+=1
            for gi,w in groups:obj.vertex_groups[gi].remove([vert.index])
            for gi,w in groups[:4]:obj.vertex_groups[gi].add([vert.index],w/total,'REPLACE')
        skin_audit.append({'mesh':obj.name,'normalized_vertices':changed,'max_discarded_weight':max_dropped})
    h.skin_audit=skin_audit
    # Protect actual blue hair/star geometry; eye and mouth pieces share the source node.
    src=h.src_hair;dst=h.hair;source=np.array([v.co[:] for v in src.data.vertices]);basis=np.array([v.co[:] for v in dst.data.shape_keys.key_blocks['Basis'].data])
    editable=set(h.config['editable_eye_components']+h.mouth_hair_components);protected=np.flatnonzero(~np.isin(h.hair_component_indices,list(editable)))
    candidate_faces={tuple(sorted(f.vertices)) for f in dst.data.polygons}
    protected_faces=[f for f in src.data.polygons if all(h.hair_component_indices[i] not in editable for i in f.vertices)]
    h.hair_audit={'protected_source_vertices':len(protected),'max_neutral_displacement':float(np.linalg.norm(basis[protected]-source[protected],axis=1).max()),'protected_source_faces':len(protected_faces),'missing_or_changed_faces':sum(tuple(sorted(f.vertices)) not in candidate_faces for f in protected_faces),'note':'Excludes original eye, lash and compact mouth components that share the hair/star node.'}
    (h.root/'protected-hair-star.json').write_text(json.dumps(h.hair_audit,indent=2));(h.root/'four-influence-audit.json').write_text(json.dumps(skin_audit,indent=2))
    # Create a geometry-only head subset while retaining the integration rig.
    h.head_scene=bpy.data.scenes.new('dsh-original-head-deliverable');h.head_map={}
    for o in h.model_objects:
        if any(token in o.name for token in h.config['garment_name_tokens']):continue
        c=o.copy();c.data=o.data.copy() if o.data else None;c.name=o.name.replace('dsh-HeadWork','dsh-Head');h.head_scene.collection.objects.link(c);h.head_map[o]=c
    for o,c in h.head_map.items():
        if o.parent in h.head_map:c.parent=h.head_map[o.parent]
        for mod in c.modifiers:
            if mod.type=='ARMATURE' and mod.object in h.head_map:mod.object=h.head_map[mod.object]
    h.head_rig=h.head_map[h.rig];h.head_body=h.head_map[h.body]
    old=h.body.data;chosen=[f for f in old.polygons if min(old.vertices[i].co.z for i in f.vertices)>h.config['neck_cut_z']]
    used=sorted(set(i for f in chosen for i in f.vertices));remap={i:j for j,i in enumerate(used)};verts=[old.vertices[i].co[:] for i in used];faces=[[remap[i] for i in f.vertices] for f in chosen]
    new=bpy.data.meshes.new('dsh-original-head-skin');new.from_pydata(verts,[],faces);new.update()
    for m in old.materials:new.materials.append(m)
    uv=new.uv_layers.new(name=old.uv_layers.active.name)
    for f,sf in zip(new.polygons,chosen):
        f.material_index=sf.material_index;f.use_smooth=sf.use_smooth
        for li,sli in zip(f.loop_indices,sf.loop_indices):uv.data[li].uv=old.uv_layers.active.data[sli].uv
    for attr in old.color_attributes:
        if attr.domain!='CORNER':continue
        a=new.color_attributes.new(name=attr.name,type=attr.data_type,domain='CORNER')
        for f,sf in zip(new.polygons,chosen):
            for li,sli in zip(f.loop_indices,sf.loop_indices):a.data[li].color=attr.data[sli].color
    if len(old.color_attributes):
        new.color_attributes.active_color_index=old.color_attributes.active_color_index;new.color_attributes.render_color_index=old.color_attributes.render_color_index
    new.normals_split_custom_set([old.corner_normals[li].vector[:] for f in chosen for li in f.loop_indices])
    h.head_body.data=new
    for key in old.shape_keys.key_blocks:
        k=h.head_body.shape_key_add(name=key.name,from_mix=False);arr=np.array([key.data[i].co[:] for i in used],np.float32);k.data.foreach_set('co',arr.ravel());k.value=0
    for group in h.body.vertex_groups:
        if h.head_body.vertex_groups.get(group.name) is None:h.head_body.vertex_groups.new(name=group.name)
    for ni,oi in enumerate(used):
        for g in old.vertices[oi].groups:h.head_body.vertex_groups[h.body.vertex_groups[g.group].name].add([ni],g.weight,'REPLACE')
    # Remove external bone-widget references from the deliverable copy only.
    for pb in h.head_rig.pose.bones:pb.custom_shape=None
    bpy.context.window.scene=h.head_scene
    for obj in h.head_scene.objects:obj.select_set(True)
    bpy.context.view_layer.objects.active=h.head_rig
    print('HEAD_EXPORT',bpy.ops.export_scene.gltf(filepath=str(h.out/'head.glb'),export_format='GLB',use_selection=True,use_active_scene=True,export_morph=True,export_skins=True,export_animations=False))
    bpy.data.libraries.write(str(h.out/'head.blend'),{h.head_scene},fake_user=True,compress=True)
    # Refresh the integrated export after explicit four-influence normalization.
    bpy.context.window.scene=h.scene
    for obj in h.scene.objects:obj.select_set(obj in h.model_objects)
    bpy.context.view_layer.objects.active=h.rig
    print('INTEGRATED_EXPORT',bpy.ops.export_scene.gltf(filepath=str(h.out/'character-head-integrated.glb'),export_format='GLB',use_selection=True,use_active_scene=True,export_morph=True,export_skins=True,export_animations=False))
    bpy.data.libraries.write(str(h.out/'character-head-integrated.blend'),{h.scene},fake_user=True,compress=True)
    (h.root/'head-subset.json').write_text(json.dumps({'body_source_vertices':len(old.vertices),'head_skin_vertices':len(used),'head_skin_faces':len(chosen),'neck_cut_blender_z':h.config['neck_cut_z'],'rig_bones':len(h.head_rig.data.bones),'note':'Head-only geometry retains the 68-bone integration skeleton. No garment geometry; candidate objects only.'},indent=2))
    print('HAIR',json.dumps(h.hair_audit));print('SKIN',json.dumps(skin_audit))
