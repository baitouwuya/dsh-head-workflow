# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Full textured review assembly; execute on authorized host or inside native Lab.

No runtime installation, network access, native-job submission, or model upload.
Host scenes are diagnostic only. Native acceptance requires the Lab to build and
seal its own model, then render that exported/reimported artifact in the Lab.
"""
from pathlib import Path
import json,sys,hashlib,re,time
import numpy as np
from full_look_arrays import load_request,validate_knots,sample_poses,sample_rotations,world_delta_to_local,rotated_loop_normals_local,prepare_skin_fields
from blender_runtime_compat import set_render_engine

SESSIONS={}

def _slug(value):return re.sub(r'[^A-Za-z0-9_.-]+','_',str(value)).strip('._') or 'review'
def _hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _coords(mesh):
    a=np.empty((len(mesh.vertices),3));mesh.vertices.foreach_get('co',a.ravel());return a
def _world(points,matrix):return (np.c_[points,np.ones(len(points))]@np.asarray(matrix).T)[:,:3]


def assemble(request_path):
    """Load original materials, preserve existing scenes, create a new review scene."""
    import bpy
    from mathutils import Matrix,Vector
    request=load_request(request_path);repo=Path(request['repo_root']);sys.path.insert(0,str(repo))
    from lab_recipes.lid_normals import area_weighted_normals
    source=dict(np.load(request['source_npz']));lids=dict(np.load(request['lid_npz']));motion=dict(np.load(request['source_motion_npz']));roles=json.loads(Path(request['roles_json']).read_text());scale=float(request['source_scale']);knots=validate_knots(request['knots']);out=Path(request['output_directory']);out.mkdir(parents=True,exist_ok=True)
    original_scene=bpy.context.window.scene if bpy.context.window else bpy.context.scene
    with bpy.data.libraries.load(str(Path(request['input_blend'])),link=False) as (available,loaded):loaded.scenes=list(available.scenes)
    objects={o for scene in loaded.scenes if scene for o in scene.objects};matches=[]
    for obj in objects:
        if obj.type!='MESH' or len(obj.data.vertices)!=len(source['vertices']):continue
        error=float(np.linalg.norm(_world(_coords(obj.data),obj.matrix_world)-source['vertices'],axis=1).max())
        if error<=request.get('source_correspondence_tolerance',scale*1e-6):matches.append((obj,error))
    if len(matches)!=1:raise ValueError('Measured source correspondence must identify exactly one input mesh; candidates='+str([(o.name,e) for o,e in matches]))
    original,error=matches[0];material_index=int(request['appearance']['source_material_index'])
    if not 0<=material_index<len(original.data.materials):raise ValueError('Measured appearance material index is absent')
    source_material=original.data.materials[material_index];bsdf=next((n for n in source_material.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
    if bsdf is None:raise ValueError('Selected source material has no measured Principled shading parameters')
    material_scalars={'doubleSided':not source_material.use_backface_culling,'pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'roughnessFactor':float(bsdf.inputs['Roughness'].default_value),'metallicFactor':float(bsdf.inputs['Metallic'].default_value)}}
    image_path=Path(request['appearance']['encoded_image_path']);encoded_hash=_hash(image_path)
    packed_before={im.name:hashlib.sha256(bytes(im.packed_file.data)).hexdigest() for mat in original.data.materials if mat and mat.use_nodes for node in mat.node_tree.nodes if node.type=='TEX_IMAGE' and (im:=node.image) and im.packed_file}
    if encoded_hash not in packed_before.values():raise ValueError('Appearance image bytes do not match an original packed source image')
    decoder=bpy.data.images.load(str(image_path),check_existing=False);decoder.colorspace_settings.name='Non-Color';width,height=decoder.size;pixels=np.empty(width*height*4,dtype=np.float32);decoder.pixels.foreach_get(pixels);rgb=pixels.reshape(height,width,4)[::-1,:,:3].copy()
    fields,appearance_report=prepare_skin_fields(source,lids,roles,request['lids'],rgb,request['appearance']['uv_origin'],material_index,material_scalars,scale,repo,visual_color_mode=request['appearance'].get('visual_color_mode','measured_boundary'))
    scene=bpy.data.scenes.new(request['label']);scene['review_mode']=request['mode'];scene['previous_scene_preserved']=original_scene.name;scene['not_native_acceptance']=request['mode']=='host_precheck'
    clone=original.copy();clone.data=original.data.copy();clone.name=request['label']+'-textured-source';clone.parent=None;clone.matrix_world=original.matrix_world.copy();scene.collection.objects.link(clone);clone.hide_render=False
    if clone.animation_data:clone.animation_data_clear()
    if clone.data.shape_keys and clone.data.shape_keys is original.data.shape_keys:raise ValueError('Review mesh unexpectedly shares the original source key data')
    if clone.data.shape_keys and clone.data.shape_keys.animation_data:clone.data.shape_keys.animation_data_clear()
    if not clone.data.shape_keys:clone.shape_key_add(name='Basis')
    base_local=_coords(clone.data);source_matrix=np.array(clone.matrix_world);mapping={};created=[]
    for control,spec in request['source_controls'].items():
        p=np.asarray(motion[spec['poses_key']]);
        if p.shape!=(len(knots),len(base_local),3):raise ValueError('Source motion array has a different measured topology')
        neutral_error=float(np.linalg.norm(p[0]*scale-source['vertices'],axis=1).max())
        if neutral_error>request.get('source_correspondence_tolerance',scale*1e-6):raise ValueError('Source motion neutral does not match the original input')
        mapping[control]=[]
        for k,value in enumerate(knots[1:],1):
            name='review_'+_slug(control)+'_'+format(value,'.8g');key=clone.shape_key_add(name=name,from_mix=False);key.data.foreach_set('co',(base_local+world_delta_to_local((p[k]-p[0])*scale,source_matrix)).ravel());key.value=0;mapping[control].append({'value':float(value),'name':key.name})
    skin_material=bpy.data.materials.new(request['label']+'-measured-skin');skin_material.use_nodes=True;skin_material.use_backface_culling=not material_scalars['doubleSided'];new_bsdf=next(n for n in skin_material.node_tree.nodes if n.type=='BSDF_PRINCIPLED');new_bsdf.inputs['Roughness'].default_value=material_scalars['pbrMetallicRoughness']['roughnessFactor'];new_bsdf.inputs['Metallic'].default_value=material_scalars['pbrMetallicRoughness']['metallicFactor'];color_node=skin_material.node_tree.nodes.new('ShaderNodeVertexColor');color_node.layer_name='measured_skin_color';skin_material.node_tree.links.new(color_node.outputs['Color'],new_bsdf.inputs['Base Color'])
    for field in fields:
        p=field['poses']*scale;f=field['faces'];mesh=bpy.data.meshes.new(request['label']+'-'+field['id']);mesh.from_pydata(p[0].tolist(),[],f.tolist());mesh.update();obj=bpy.data.objects.new(mesh.name,mesh);scene.collection.objects.link(obj);mesh.materials.append(skin_material)
        for face in mesh.polygons:face.use_smooth=True
        attr=mesh.color_attributes.new(name='measured_skin_color',type='FLOAT_COLOR',domain='POINT');attr.data.foreach_set('color',np.asarray(field['colors'],np.float32).ravel());obj.shape_key_add(name='Basis')
        for k,knot in enumerate(mapping[field['control']],1):key=obj.shape_key_add(name=knot['name'],from_mix=False);key.data.foreach_set('co',p[k].ravel());key.value=0
        created.append({'object':obj,**field})
    set_render_engine(scene,request.get('engine'));scene.render.resolution_x=int(request.get('resolution',512));scene.render.resolution_y=int(request.get('resolution',512));scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.render.fps=int(request.get('fps',12));scene.view_settings.view_transform=request.get('view_transform','Standard');scene.render.use_stamp=True;scene.render.use_stamp_note=True
    for name in ('use_stamp_date','use_stamp_time','use_stamp_render_time','use_stamp_frame','use_stamp_filename','use_stamp_scene','use_stamp_camera'):setattr(scene.render,name,False)
    scene.world=bpy.data.worlds.new(request['label']+'-world');scene.world.use_nodes=True;next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND').inputs[0].default_value=tuple(request.get('world_color',[.35,.35,.35,1]))
    for spec in request['lights']:
        light_data=bpy.data.lights.new(request['label']+'-review-light','AREA');light_data.energy=spec['energy'];light_data.size=spec['size'];light=bpy.data.objects.new(light_data.name,light_data);scene.collection.objects.link(light);light.location=spec['position'];light.rotation_euler=(Vector(spec['target'])-light.location).to_track_quat('-Z','Y').to_euler()
    camera_data=bpy.data.cameras.new(request['label']+'-review-camera');camera_data.type='ORTHO';camera=bpy.data.objects.new(camera_data.name,camera_data);scene.collection.objects.link(camera);scene.camera=camera
    if bpy.context.window:bpy.context.window.scene=scene
    report={'mode':request['mode'],'status':'assembled for visual motion review; not accepted','blender_version':bpy.app.version_string,'source_blend_sha256':_hash(request['input_blend']),'array_hashes':{key:_hash(request[key]) for key in ['source_npz','lid_npz','source_motion_npz']},'source_object':original.name,'source_vertex_match_max_error':error,'source_matrix_world':source_matrix.tolist(),'original_packed_images':packed_before,'appearance_image_sha256':encoded_hash,'decoded_image_colorspace':decoder.colorspace_settings.name,'uv_origin':request['appearance']['uv_origin'],'source_zero_corner_normal_sentinels':int((np.linalg.norm(source['loop_normals_local'],axis=1)==0).sum()),'appearance_diagnostics':appearance_report,'previous_scene':original_scene.name,'review_scene':scene.name,'renders':[],'acceptance':'Visual review of the Lab own build and own export/reimport renders is required. Host results are diagnosis only.'}
    session={'request':request,'scene':scene,'source_object':clone,'original_source_object':original,'source':source,'motion':motion,'created':created,'mapping':mapping,'knots':knots,'scale':scale,'source_matrix':source_matrix,'camera':camera,'report':report,'output':out,'area_normals':area_weighted_normals}
    SESSIONS[scene.name]=session;(out/'full-look-review.json').write_text(json.dumps(report,indent=2));return {'session_id':scene.name,'scene':scene.name,'source_objects_preserved':True,'generated_review_domains':len(created),'report':str(out/'full-look-review.json')}


def initialize_rest_normals(session_id,generated_mode=None):
    """Set Basis normals once; Blender evaluates them with the shape-key mesh.

    Passing posed normals to the undeformed Basis every frame applies deformation
    compensation twice. Static-pose host ablations reproduced that error. Source
    original local loop normals (including zero sentinels) are restored exactly.
    """
    import bpy
    session=SESSIONS[session_id];request=session['request'];mode=generated_mode or request.get('generated_rest_normal_mode','neutral_custom')
    if mode not in ('neutral_custom','auto'):raise ValueError('Unknown generated rest-normal mode')
    sys.path.insert(0,str(Path(request['repo_root'])/'tools'))
    from native_render_verification import apply_control_values
    apply_control_values(session['scene'].objects,session['mapping'],{})
    bpy.context.view_layer.update()
    source_obj=session['source_object']
    source_obj.data.normals_split_custom_set(np.asarray(session['source']['loop_normals_local']).tolist())
    for item in session['created']:
        mesh=item['object'].data
        if mode=='auto':
            mesh.normals_split_custom_set(np.zeros((len(mesh.loops),3)).tolist());continue
        try:
            if item.get('normal_mode',('source_static' if item['domain']==1 else 'posed'))=='source_static':
                world=np.asarray(session['source']['loop_normals_local'])@np.linalg.inv(session['source_matrix'][:3,:3]);loops=session['source']['triangle_loops'][item['source_triangle_ids']];n=np.einsum('ni,nij->nj',item['source_barycentric'],world[loops]);length=np.linalg.norm(n,axis=1);valid=length>0;n[valid]/=length[valid,None];n[~valid]=0
            else:n=session['area_normals'](item['poses'][0],item['faces'])
            mesh.normals_split_custom_set_from_vertices(n.tolist())
        except ValueError as error:
            mesh.normals_split_custom_set(np.zeros((len(mesh.loops),3)).tolist())
            session['report'].setdefault('normal_diagnostics',[]).append({'object':item['object'].name,'normal_diagnostic':str(error),'rendering':'Blender auto normals on generated mesh; visual review still proceeds'})
    session['rest_normals_initialized']=True
    session['report']['normal_policy']={'source':'Original Basis local loop normals preserved; no per-frame posed-normal writes','generated':mode,'evaluation':'Blender evaluates shape-key geometry and normal compensation once','native_acceptance':'Own sealed export/reimport shading still requires review'}
    bpy.context.view_layer.update()
    return session['report']['normal_policy']


def _set_state(session,values):
    import bpy
    request=session['request'];sys.path.insert(0,str(Path(request['repo_root'])/'tools'))
    from native_render_verification import apply_control_values
    if not session.get('rest_normals_initialized'):initialize_rest_normals(session['scene'].name)
    apply_control_values(session['scene'].objects,session['mapping'],values)
    # Never write posed custom normals onto the rest mesh here. Generated and
    # original-source normals must undergo Blender shape evaluation only once.
    bpy.context.view_layer.update()


def render_batch(session_id,scenario_id,view_id,frame_indices=None):
    """Render a close/reopen PNG sequence in bounded caller-chosen batches."""
    import bpy
    from mathutils import Vector
    session=SESSIONS[session_id];request=session['request'];scene=session['scene'];camera=session['camera'];scenario=next(s for s in request['scenarios'] if s['id']==scenario_id);view=next(v for v in request['views'] if v['id']==view_id)
    if bpy.context.window:bpy.context.window.scene=scene
    camera.location=view['position'];camera.rotation_euler=(Vector(view['target'])-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=float(view['ortho_scale']);out=session['output']/_slug(scenario_id)/_slug(view_id);out.mkdir(parents=True,exist_ok=True);frames=range(len(request['cycle_values'])) if frame_indices is None else frame_indices;records=[]
    for i in frames:
        value=float(request['cycle_values'][i]);values={c:value if c in scenario['controls'] else 0 for c in request['source_controls']};_set_state(session,values);path=out/(str(i).zfill(3)+'.png')
        if path.exists() and not request.get('overwrite_review_frames',False):raise FileExistsError('Preserve prior review frame: '+str(path))
        scene.render.stamp_note_text=request['label']+' | '+scenario_id+' | '+view_id+' | frame '+str(i)+' | '+str(values);scene.render.filepath=str(path);bpy.ops.render.render(write_still=True,scene=scene.name);row={'scenario':scenario_id,'view':view_id,'cycle_index':i,'control_values':values,'path':str(path)};records.append(row);session['report']['renders'].append(row)
    _set_state(session,{})
    packed_after={im.name:hashlib.sha256(bytes(im.packed_file.data)).hexdigest() for mat in session['original_source_object'].data.materials if mat and mat.use_nodes for node in mat.node_tree.nodes if node.type=='TEX_IMAGE' and (im:=node.image) and im.packed_file};session['report']['source_packed_images_unchanged']=packed_after==session['report']['original_packed_images'];session['report']['source_blend_file_unchanged']=_hash(request['input_blend'])==session['report']['source_blend_sha256'];(session['output']/'full-look-review.json').write_text(json.dumps(session['report'],indent=2));return {'session_id':session_id,'rendered_frames':records,'report':str(session['output']/'full-look-review.json')}


def native_verification_request(session_id,sealed_candidate,output_directory):
    """Build a request for the repo's exported/reimported native render verifier.

    The Lab must create and seal its own candidate; no host geometry/array payload
    is a native input. This function does not export, upload or publish anything.
    """
    session=SESSIONS[session_id];r=session['request']
    if r['mode']!='native_stage_build':raise ValueError('Host precheck is never native artifact verification')
    states=[]
    for scenario in r['scenarios']:
        for i,w in enumerate(r['cycle_values']):states.append({'label':_slug(scenario['id'])+'-'+str(i).zfill(3),'values':{c:float(w) if c in scenario['controls'] else 0 for c in r['source_controls']}})
    return {'source':r['native_source_render_spec'],'candidate':{'path':str(sealed_candidate),'world_to_review':np.eye(4).tolist()},'output_directory':str(output_directory),'controller':session['mapping'],'states':states,'views':[{'label':v['id'],**{k:x for k,x in v.items() if k!='id'}} for v in r['views']],'lights':r['lights'],'resolution':r.get('resolution',512),'engine':session['scene'].render.engine}


def encode_cycle(session_id,scenario_id,view_id):
    """Encode an already rendered complete cycle with the host/Lab Blender VSE."""
    import bpy
    session=SESSIONS[session_id];request=session['request'];folder=session['output']/_slug(scenario_id)/_slug(view_id);paths=[folder/(str(i).zfill(3)+'.png') for i in range(len(request['cycle_values']))]
    missing=[str(p) for p in paths if not p.is_file()]
    if missing:raise ValueError('Render the complete close/reopen sequence before encoding: '+str(missing))
    target=session['output']/(_slug(scenario_id)+'-'+_slug(view_id)+'-cycle.mp4')
    if target.exists() and not request.get('overwrite_review_frames',False):raise FileExistsError('Preserve prior review video: '+str(target))
    scene=bpy.data.scenes.new(request['label']+'-encode-'+scenario_id+'-'+view_id);editor=scene.sequence_editor_create();strips=getattr(editor,'strips',None)
    if strips is None:strips=editor.sequences
    strip=strips.new_image(name='Rendered close and reopen',filepath=str(paths[0]),channel=1,frame_start=1)
    for path in paths[1:]:strip.elements.append(path.name)
    strip.frame_final_duration=len(paths);scene.view_settings.view_transform=request.get('view_transform','Standard')
    scene.frame_start=1;scene.frame_end=len(paths);scene.render.resolution_x=int(request.get('resolution',512));scene.render.resolution_y=int(request.get('resolution',512));scene.render.resolution_percentage=100;scene.render.fps=int(request.get('fps',12))
    if hasattr(scene.render.image_settings,'media_type'):scene.render.image_settings.media_type='VIDEO'
    scene.render.image_settings.file_format='FFMPEG';scene.render.ffmpeg.format='MPEG4';scene.render.ffmpeg.codec='H264';scene.render.ffmpeg.constant_rate_factor='MEDIUM';scene.render.filepath=str(target)
    bpy.ops.render.render(animation=True,scene=scene.name)
    record={'scenario':scenario_id,'view':view_id,'frames':len(paths),'fps':scene.render.fps,'path':str(target),'source':'Actual rendered PNG sequence; no generated/interpolated image frames'};session['report'].setdefault('videos',[]).append(record);(session['output']/'full-look-review.json').write_text(json.dumps(session['report'],indent=2));return record
