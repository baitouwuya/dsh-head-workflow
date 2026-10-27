# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Host/Lab visual diagnostics: static poses, independent colour/normal switches.

No model upload or artifact acceptance. Import bpy only on explicit invocation in
the authorized Blender runtime. Existing scenes, meshes and evidence are retained.
"""
import json
from pathlib import Path
import numpy as np
import full_look_review as review
from full_look_arrays import sample_poses,sample_rotations,rotated_loop_normals_local

ABLATIONS={}


def build(session_id, values, label, colors='measured', normals='explicit', source_normals='rotated'):
    """Freeze actual geometry, then vary only generated colour and shading normals.

    colors: measured or uniform (robust median skin colour, same roughness).
    normals: explicit pose-space core/source-strip normals, or Blender auto normals.
    source_normals: rotated original source normals, or auto normals.
    No shape keys remain on these static diagnostic meshes, removing the possible
    rest-mesh custom-normal/shape-key compensation from this comparison.
    """
    import bpy
    if colors not in ('measured','uniform') or normals not in ('explicit','auto') or source_normals not in ('rotated','auto'):
        raise ValueError('Unknown diagnostic ablation option')
    s=review.SESSIONS[session_id];r=s['request'];review._set_state(s,values)
    if bpy.context.window:bpy.context.window.scene=s['scene']
    bpy.context.view_layer.update();depsgraph=bpy.context.evaluated_depsgraph_get()
    scene=bpy.data.scenes.new(label);scene.world=s['scene'].world
    scene.render.engine=s['scene'].render.engine
    for prop in ('resolution_x','resolution_y','resolution_percentage','fps'):
        setattr(scene.render,prop,getattr(s['scene'].render,prop))
    scene.view_settings.view_transform=s['scene'].view_settings.view_transform
    scene.view_settings.look=s['scene'].view_settings.look
    scene.view_settings.exposure=s['scene'].view_settings.exposure
    scene.view_settings.gamma=s['scene'].view_settings.gamma
    scene.render.image_settings.file_format='PNG';scene.render.use_stamp=True;scene.render.use_stamp_note=True
    for prop in ('use_stamp_date','use_stamp_time','use_stamp_render_time','use_stamp_frame','use_stamp_filename','use_stamp_scene','use_stamp_camera','use_stamp_memory'):
        if hasattr(scene.render,prop):setattr(scene.render,prop,False)
    for obj in s['scene'].objects:
        if obj.type in ('LIGHT','CAMERA'):
            clone=obj.copy();clone.data=obj.data.copy();scene.collection.objects.link(clone)
            if obj==s['camera']:scene.camera=clone
    # The evaluated source preserves its original UV/material attributes and all
    # currently active unrelated controls. Only this copied mesh's normals change.
    source_obj=s['source_object'];evaluated=source_obj.evaluated_get(depsgraph)
    mesh=bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=depsgraph)
    obj=bpy.data.objects.new(label+'-source-static',mesh);scene.collection.objects.link(obj);obj.matrix_world=source_obj.matrix_world.copy()
    if len(mesh.vertices)!=len(s['source']['vertices']) or len(mesh.loops)!=len(s['source']['loop_vertex_ids']):
        raise ValueError('Evaluated source topology changed; cannot bind original corner normals')
    mesh.normals_split_custom_set(np.zeros((len(mesh.loops),3)).tolist())
    if source_normals=='rotated':
        rotation=np.broadcast_to(np.eye(3),(len(mesh.vertices),3,3)).copy()
        for control,spec in r['source_controls'].items():
            if 'rotations_key' in spec:rotation=sample_rotations(s['motion'][spec['rotations_key']],s['knots'],float(values.get(control,0)))@rotation
        n=rotated_loop_normals_local(s['source']['loop_normals_local'],s['source']['loop_vertex_ids'],rotation,s['source_matrix'])
        mesh.normals_split_custom_set(n.tolist())
    median=np.median(np.concatenate([item['colors'] for item in s['created']]),axis=0);median[3]=1
    generated=[]
    for item in s['created']:
        p=sample_poses(item['poses'],s['knots'],float(values.get(item['control'],0)))*s['scale']
        m=bpy.data.meshes.new(label+'-'+item['id']);m.from_pydata(p.tolist(),[],item['faces'].tolist());m.update()
        o=bpy.data.objects.new(m.name,m);scene.collection.objects.link(o)
        for mat in item['object'].data.materials:m.materials.append(mat)
        for face in m.polygons:face.use_smooth=True
        attr=m.color_attributes.new(name='measured_skin_color',type='FLOAT_COLOR',domain='POINT')
        rgba=item['colors'] if colors=='measured' else np.broadcast_to(median,(len(p),4))
        attr.data.foreach_set('color',np.asarray(rgba,np.float32).ravel())
        if normals=='explicit':
            if item.get('normal_mode',('source_static' if item['domain']==1 else 'posed'))=='source_static':
                world=np.asarray(s['source']['loop_normals_local'])@np.linalg.inv(s['source_matrix'][:3,:3]);loops=s['source']['triangle_loops'][item['source_triangle_ids']]
                n=np.einsum('ni,nij->nj',item['source_barycentric'],world[loops]);length=np.linalg.norm(n,axis=1);valid=length>0;n[valid]/=length[valid,None];n[~valid]=0
            else:n=s['area_normals'](p,item['faces'])
            m.normals_split_custom_set_from_vertices(n.tolist())
        # Compare exact evaluated positions, never infer geometric equivalence
        # from unchanged vertex counts alone.
        posed=item['object'].evaluated_get(depsgraph);coords=review._world(review._coords(posed.data),posed.matrix_world)
        error=float(np.linalg.norm(coords-p,axis=1).max())
        generated.append({'id':item['id'],'evaluated_position_max_error':error,'vertices':len(p)})
    out=s['output']/'ablations'/review._slug(label);out.mkdir(parents=True,exist_ok=True)
    report={'label':label,'source_session':session_id,'control_values':dict(values),'colors':colors,'generated_normals':normals,'source_normals':source_normals,'uniform_linear_rgba':median.tolist(),'generated_geometry_comparison':generated,'shape_keys_present':False,'status':'Diagnostic ablation only; no acceptance conclusion','renders':[]}
    ABLATIONS[scene.name]={'scene':scene,'session':s,'report':report,'output':out};(out/'ablation.json').write_text(json.dumps(report,indent=2))
    review._set_state(s,{})
    return {'ablation_id':scene.name,'report':str(out/'ablation.json')}


def render(ablation_id,view_ids=None):
    import bpy
    from mathutils import Vector
    a=ABLATIONS[ablation_id];scene=a['scene'];camera=scene.camera;s=a['session']
    if bpy.context.window:bpy.context.window.scene=scene
    results=[]
    for v in s['request']['views']:
        if view_ids is not None and v['id'] not in view_ids:continue
        path=a['output']/(review._slug(v['id'])+'.png')
        if path.exists():raise FileExistsError('Preserve previous ablation image: '+str(path))
        camera.location=v['position'];camera.rotation_euler=(Vector(v['target'])-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=float(v['ortho_scale'])
        scene.render.stamp_note_text=a['report']['label']+' | '+v['id']+' | '+str(a['report']['control_values']);scene.render.filepath=str(path)
        bpy.ops.render.render(write_still=True,scene=scene.name);results.append({'view':v['id'],'path':str(path)})
    a['report']['renders']+=results;(a['output']/'ablation.json').write_text(json.dumps(a['report'],indent=2))
    return results
