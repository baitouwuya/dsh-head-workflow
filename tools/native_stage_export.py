# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Export only a Lab-built full-look session; never export host diagnostic assets.

This source is sent to the native Lab with repository code. Its geometry arrays
must have been constructed there from the incoming asset. No upload/publish call
is made here; the Lab must visually verify its own reimport before publishing.
"""
from pathlib import Path
import hashlib,json,struct
from native_glb_clips import append_blink_cycles,unpack_glb,embedded_image_hashes


def _require_native(session):
    if session['request'].get('mode')!='native_stage_build':
        raise ValueError('Host precheck assets cannot be exported as pipeline deliverables')
    provenance=session['request'].get('native_build_provenance')
    if not isinstance(provenance,dict) or not all(provenance.get(k) for k in ('input_artifact_id','repository_commit','construction_report_path')):
        raise ValueError('Native input artifact, runtime repository commit and construction report provenance required')
    return provenance


def _preserve_hierarchy(session):
    """Copy ancestor/armature/constraint dependencies with their local hierarchy.

    Mesh UV, material, existing morphs and armature bone names remain intact.
    Arbitrary scripted drivers need an explicit adapter; do not silently claim
    their preservation. The current measured source is unrigged and has none.
    """
    source=session['original_source_object'];clone=session['source_object'];scene=session['scene'];objects={source};todo=[source]
    while todo:
        obj=todo.pop();deps=[obj.parent]
        deps += [getattr(m,'object',None) for m in obj.modifiers]
        deps += [getattr(c,'target',None) for c in obj.constraints]
        for dep in deps:
            if dep is not None and dep not in objects:objects.add(dep);todo.append(dep)
    copies={source:clone}
    for original in objects:
        if original.animation_data and original.animation_data.drivers:raise ValueError('Source object drivers require an explicit native preservation adapter')
        if original==source:continue
        copied=original.copy()
        if original.data:copied.data=original.data.copy()
        scene.collection.objects.link(copied);copies[original]=copied
    for original,copied in copies.items():
        matrix=original.matrix_world.copy();copied.parent=copies.get(original.parent);copied.parent_type=original.parent_type;copied.parent_bone=original.parent_bone;copied.matrix_parent_inverse=original.matrix_parent_inverse.copy();copied.matrix_world=matrix
        for m in copied.modifiers:
            if getattr(m,'object',None) in copies:m.object=copies[m.object]
        for c in copied.constraints:
            if getattr(c,'target',None) in copies:c.target=copies[c.target]
    session['_source_hierarchy_copies']=copies
    return [{'source_object':o.name,'export_object':c.name,'type':o.type,'parent_source':o.parent.name if o.parent else None,'parent_type':o.parent_type,'bones':[b.name for b in o.data.bones] if o.type=='ARMATURE' else []} for o,c in copies.items()]


def plan_head_assembly(hierarchy,generated_names,binding=None):
    """Pure attachment contract; a common rigid root is not a rig binding."""
    if not hierarchy:raise ValueError('Source hierarchy records required')
    by_source={record['source_object']:record for record in hierarchy}
    if len(by_source)!=len(hierarchy):raise ValueError('Source hierarchy names must be unambiguous')
    if len(generated_names)!=len(set(generated_names)):raise ValueError('Generated object names must be unique')
    if any(record.get('parent_source') is not None and record['parent_source'] not in by_source for record in hierarchy):raise ValueError('Source dependency hierarchy is incomplete')
    roots=[record['export_object'] for record in hierarchy if record.get('parent_source') is None]
    if not roots:raise ValueError('Source dependency hierarchy has no root')
    rigged=any(record.get('type')=='ARMATURE' or record.get('parent_type')=='BONE' for record in hierarchy)
    if rigged:
        if not isinstance(binding,dict) or binding.get('kind')!='bone' or not isinstance(binding.get('evidence_path'),str) or not binding['evidence_path'].strip():
            raise ValueError('Rigged input requires measured native_generated_binding with kind=bone, source_armature, bone and evidence_path; a rigid assembly root is not a substitute')
        armature=by_source.get(binding.get('source_armature'));bone=binding.get('bone')
        if armature is None or armature.get('type')!='ARMATURE' or not isinstance(bone,str) or bone not in armature.get('bones',[]):raise ValueError('Measured generated attachment must identify an existing source armature bone')
        attachment={'kind':'bone','parent_object':armature['export_object'],'bone':bone,'evidence_path':binding['evidence_path']}
    else:
        if binding is not None:raise ValueError('Unrigged input uses common rigid assembly; unexpected bone binding supplied')
        attachment={'kind':'rigid_assembly','parent_object':None,'bone':None}
    return {'source_dependency_roots':roots,'generated_objects':list(generated_names),'generated_attachment':attachment,'source_rigged':rigged,'scope':'Rigid grouping plus the explicitly measured generated bone attachment when required; no automatic skin weighting'}


def _assemble_rigid_head(session,hierarchy,provenance):
    """Group every source dependency root and generated patch without moving it."""
    import bpy
    from mathutils import Matrix
    scene=session['scene'];copies=session['_source_hierarchy_copies'];generated=[item['object'] for item in session['created']]
    plan=plan_head_assembly(hierarchy,[obj.name for obj in generated],session['request'].get('native_generated_binding'))
    by_name={obj.name:obj for obj in copies.values()};before={obj:obj.matrix_world.copy() for obj in list(copies.values())+generated};parents_before={obj:obj.parent for obj in copies.values()};names_before={obj:obj.name for obj in copies.values()}
    root=bpy.data.objects.new('HeadAssembly',None);scene.collection.objects.link(root);root.matrix_world=Matrix.Identity(4);root.empty_display_type='PLAIN_AXES'
    root['native_controller_json']=json.dumps(session['mapping']);root['native_build_provenance_json']=json.dumps(provenance);root['native_assembly_scope']=plan['scope']
    for name in plan['source_dependency_roots']:
        obj=by_name[name];obj.parent=root;obj.parent_type='OBJECT';obj.parent_bone='';obj.matrix_parent_inverse=Matrix.Identity(4);obj.matrix_world=before[obj]
    attachment=plan['generated_attachment']
    for obj in generated:
        obj.parent=root if attachment['kind']=='rigid_assembly' else by_name[attachment['parent_object']]
        obj.parent_type='OBJECT' if attachment['kind']=='rigid_assembly' else 'BONE';obj.parent_bone=attachment['bone'] or '';obj.matrix_parent_inverse=Matrix.Identity(4)
    # Bone-parent transforms depend on evaluated pose matrices; update before
    # restoring world matrices so the unchanged neutral placement is explicit.
    scene.view_layers[0].update()
    for obj in generated:obj.matrix_world=before[obj]
    scene.view_layers[0].update()
    maximum=max(abs(obj.matrix_world[row][column]-matrix[row][column]) for obj,matrix in before.items() for row in range(4) for column in range(4))
    if maximum>1e-6:raise RuntimeError('Assembly parenting changed world transforms; retain native evidence and repair the measured binding')
    for obj,parent in parents_before.items():
        if parent is not None and obj.parent is not parent:raise RuntimeError('Source internal hierarchy was changed')
        if obj.name!=names_before[obj]:raise RuntimeError('Source internal object name was changed')
    root['native_generated_attachment_json']=json.dumps(attachment)
    return {**plan,'root_object':root.name,'root_type':'EMPTY','root_initial_matrix_world':[list(row) for row in root.matrix_world],'world_transform_max_change':float(maximum),'source_internal_hierarchy_and_names_preserved':True,'original_armature_bone_names_preserved':True,'controller':session['mapping'],'provenance':provenance}


def export_native_session(session_id,output_directory,stem='character'):
    """Seal GLB + editable BLEND and cycle clips, then require native verification.

    RNA filtering accommodates the Lab-provided Blender version. Essential GLB,
    selection and morph switches must exist. Original embedded image bytes are
    checked exactly after export. No result is declared visually accepted here.
    """
    import full_look_review as review
    session=review.SESSIONS[session_id];provenance=_require_native(session)
    # The mode/provenance checks happen before importing the Blender runtime.
    import bpy
    request=session['request'];out=Path(output_directory);out.mkdir(parents=True,exist_ok=True)
    if Path(stem).name!=stem or not stem or stem in ('.','..'):raise ValueError('A simple artifact stem is required')
    raw_path=out/(stem+'-before-clips.glb');sealed_path=out/(stem+'.glb');blend_path=out/(stem+'.blend');record_path=out/(stem+'-export.json')
    if any(p.exists() for p in (raw_path,sealed_path,blend_path,record_path)):raise FileExistsError('Preserve existing export evidence; use a fresh native output directory')
    hierarchy=_preserve_hierarchy(session);review._set_state(session,{})
    assembly=_assemble_rigid_head(session,hierarchy,provenance)
    scene=session['scene']
    if bpy.context.window:bpy.context.window.scene=scene
    import uuid
    for obj in scene.objects:
        obj.select_set(obj.type not in ('LIGHT','CAMERA'))
        if obj.type=='MESH' and not obj.get('native_animation_binding'):obj['native_animation_binding']=str(uuid.uuid4())
    bpy.context.view_layer.objects.active=session['source_object'];bpy.context.view_layer.update()
    desired={'filepath':str(raw_path),'export_format':'GLB','use_selection':True,'use_active_scene':True,'export_skins':True,'export_morph':True,'export_morph_normal':True,'export_normals':True,'export_animations':False,'export_apply':False,'export_image_format':'AUTO','export_keep_originals':True,'export_all_vertex_colors':True,'export_extras':True}
    rna=bpy.ops.export_scene.gltf.get_rna_type();available={p.identifier:p for p in rna.properties};required={'filepath','export_format','use_selection','export_skins','export_morph','export_normals','export_extras'}
    if not required.issubset(available):raise RuntimeError('Lab exporter lacks required GLB/skin/morph switches: '+str(sorted(required-set(available))))
    selected={};skipped={}
    for key,value in desired.items():
        if key not in available:skipped[key]='unavailable';continue
        prop=available[key]
        if prop.type=='ENUM' and value not in {item.identifier for item in prop.enum_items}:
            if key in required:raise RuntimeError('Required export option unsupported: '+key)
            skipped[key]='enum value unavailable';continue
        selected[key]=value
    bpy.ops.export_scene.gltf(**selected)
    raw=raw_path.read_bytes();document,binary,_=unpack_glb(raw);image_hashes=embedded_image_hashes(document,binary);expected=set(session['report']['original_packed_images'].values());actual={row['sha256'] for row in image_hashes}
    if not expected.issubset(actual):raise RuntimeError('Exporter changed or omitted original encoded image bytes; preserve raw evidence and repair exporter configuration before sealing')
    fps=float(request.get('fps',12));times=[i/fps for i in range(len(request['cycle_values']))]
    sealed,clip_report=append_blink_cycles(raw,session['mapping'],request['scenarios'],request['cycle_values'],times)
    sealed_path.write_bytes(sealed)
    scene['native_controller_json']=json.dumps(session['mapping']);scene['native_build_provenance_json']=json.dumps(provenance);scene['native_export_status']='Sealed; own export/reimport visual verification still required'
    bpy.data.libraries.write(str(blend_path),{scene},fake_user=True,compress=True)
    record={'status':'SEALED_PENDING_NATIVE_VISUAL_VERIFICATION','mode':request['mode'],'blender_version':bpy.app.version_string,'provenance':provenance,'controller':session['mapping'],'hierarchy':hierarchy,'exporter_options':selected,'unavailable_optional_options':skipped,'clip_report':clip_report,'artifacts':{p.name:{'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (raw_path,sealed_path,blend_path)},'original_embedded_images_preserved':True,'original_source_materials_unchanged':True,'limitations':['Generated normal interpolation must be reviewed on the native sealed reimport.','Source animation actions are retained in editable dependencies when present; this GLB adds the requested blink cycles and does not certify unrelated source animation export.'],'publish_rule':'Publish and select only this native-built GLB after visual review of this sealed file imported in the Lab.'}
    record['head_assembly']=assembly
    record_path.write_text(json.dumps(record,indent=2));return {'glb':str(sealed_path),'blend':str(blend_path),'report':str(record_path),'status':record['status']}


def cycle_verification_request(session_id,sealed_candidate,output_directory):
    """Create the own-sealed-GLB video request from measured native scene settings."""
    import full_look_review as review
    session=review.SESSIONS[session_id];provenance=_require_native(session);r=session['request']
    if not r.get('native_source_render_spec'):raise ValueError('Measured native source path and world_to_review are required')
    clip_fps=r.get('fps',12);requested_fps=r.get('verification_fps',2*clip_fps)
    if any(isinstance(f,bool) or not isinstance(f,int) or f<=0 for f in (clip_fps,requested_fps)):raise ValueError('Positive integer clip and verification frame rates required')
    return {'mode':'native_stage_build','native_build_provenance':provenance,'repo_root':r['repo_root'],'source':r['native_source_render_spec'],'candidate':{'path':str(sealed_candidate),'world_to_review':[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]},'output_directory':str(output_directory),'clip_names':[s['id'] for s in r['scenarios']],'views':r['views'],'lights':r['lights'],'engine':r.get('engine',session['scene'].render.engine),'resolution':r.get('resolution',512),'view_transform':r.get('view_transform','Standard'),'clip_fps':clip_fps,'fps':max(2*clip_fps,requested_fps)}
