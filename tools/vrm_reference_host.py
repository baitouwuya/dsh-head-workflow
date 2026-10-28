# SPDX-License-Identifier: GPL-3.0-or-later
"""Private host-only VRM/PD experiment. Return numbers, never reference arrays."""
def eye_width(reference):
    import numpy as np
    from _dsh_pd_reference_task.geometry import boundary_loops,split_lids,frame_for
    v,f=reference.evaluate({},0.)
    slot=next(s for s in reference.desc['slots'] if 'EyeWhite' in s['material'])
    loops=boundary_loops(f[slot['tri_start']:slot['tri_start']+slot['tri_count']])
    return float(np.mean([frame_for(v,split_lids(v,p,1 if v[p,0].mean()>0 else -1)[0])[2] for p in loops]))


def test_imported_vrm(reference,vrm_path,pack_dir):
    import bpy,copy,numpy as np
    from mathutils.kdtree import KDTree
    from mathutils import Vector
    from parametric_deformation.ui import panels as ui
    exp=reference.glb.g['extensions']['VRMC_vrm']['expressions']['preset']['blink']
    if len(exp['morphTargetBinds'])!=1 or exp['morphTargetBinds'][0]['weight']!=1:
        raise ValueError('live importer parity test currently requires one full-weight blink target')
    if ui._state.get('pack') is not None or bpy.context.mode!='OBJECT' or any(o.name.startswith('PD_Avatar') for o in bpy.data.objects):
        raise RuntimeError('UI experiment requires idle PD, no PD_Avatar objects, and Object mode')
    old_scene=bpy.context.window.scene
    old_active=bpy.context.view_layer.objects.active
    old_selected=list(bpy.context.selected_objects)
    kinds=['objects','scenes','collections','meshes','armatures','materials','node_groups',
           'images','actions','textures','worlds','cameras','lights','shape_keys','texts']
    before={k:set(getattr(bpy.data,k)) for k in kinds}
    state=copy.deepcopy(ui._state)
    props={t:set(t.bl_rna.properties.keys()) for t in (bpy.types.Scene,bpy.types.Collection)}
    timer_names=['_param_poll','_flush_timer','_auto_load_pack','_auto_load_preset']
    timers={n:bpy.app.timers.is_registered(getattr(ui,n)) for n in timer_names}
    report={}
    try:
        scene=bpy.data.scenes.new('Private VRM reference compatibility test')
        bpy.context.window.scene=scene
        scene.pd_live_update=False
        status=bpy.ops.import_scene.vrm(filepath=vrm_path,use_addon_preferences=False,
            extract_textures_into_folder=False,make_new_texture_folder=False,
            set_shading_type_to_material_on_import=False,set_view_transform_to_standard_on_import=False,
            enable_mtoon_outline_preview=False)
        name=reference.binding_names[0]
        matches=[o for o in scene.objects if o.type=='MESH' and o.data.shape_keys and name in o.data.shape_keys.key_blocks]
        if len(matches)!=1:raise ValueError('ambiguous imported face')
        face=matches[0]
        arm=next(o for o in scene.objects if o.type=='ARMATURE')
        def coords(obj):
            out=np.empty((len(obj.data.vertices),3))
            obj.data.vertices.foreach_get('co',out.ravel())
            return out
        def evaluated_coords(obj):
            bpy.context.view_layer.update()
            evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh=evaluated.to_mesh()
            try:
                out=np.empty((len(mesh.vertices),3));mesh.vertices.foreach_get('co',out.ravel())
                matrix=np.array(evaluated.matrix_world)
                return out@matrix[:3,:3].T+matrix[:3,3]
            finally:
                evaluated.to_mesh_clear()
        base=coords(face)
        keys=face.data.shape_keys
        width=eye_width(reference)
        report['import']={'finished':status=={'FINISHED'},'vertices':len(base),
                          'shape_keys':len(keys.key_blocks),'blink_present':name in keys.key_blocks}
        # The importer reorders vertices. Match neutral geometry, allowing coincident
        # seam vertices, then compare native morph deltas on that correspondence.
        native=reference.base@reference.axis.T
        delta=reference.delta@reference.axis.T
        key=np.empty_like(base)
        keys.key_blocks[name].data.foreach_get('co',key.ravel())
        tree=KDTree(len(native))
        for i,p in enumerate(native):tree.insert(Vector(p),i)
        tree.balance()
        distances=[];morph_errors=[];ambiguous=0
        for p,d in zip(base,key-base):
            _,i,dist=tree.find(Vector(p))
            distances.append(dist)
            candidates=tree.find_range(Vector(p),max(1e-6,dist+1e-7))
            ambiguous+=len(candidates)>1
            morph_errors.append(min(np.linalg.norm(d-delta[j]) for _,j,_ in candidates))
        exp=arm.data.vrm_addon_extension.vrm1.expressions.preset.blink
        preview=[]
        for w in (0.,.25,.5,.75,1.):
            exp.preview=w;bpy.context.view_layer.update()
            preview.append(float(keys.key_blocks[name].value))
        exp.preview=0.
        imported_evaluated_base=evaluated_coords(face)
        report['native_blink_import_parity']={
            'neutral_max_error_eye_widths':float(max(distances)/width),
            'morph_delta_max_error_eye_widths':float(max(morph_errors)/width),
            'coincident_neutral_matches':ambiguous,'preview_weights':preview,
            'passed':max(distances)/width<.001 and max(morph_errors)/width<1e-5 and np.allclose(preview,[0.,.25,.5,.75,1.])}
        report['pd_load_finished']=bpy.ops.pd.load_pack(pack_path=pack_dir)=={'FINISHED'}
        scene.pd_live_update=False;ui._host().pd_live_update=False
        report['pd_evaluate_finished']=bpy.ops.pd.evaluate()=={'FINISHED'}
        avatar=bpy.data.objects['PD_Avatar'];rest=coords(avatar)
        tests=[]
        controls=['Eye Size Y','Outer Eye Slant (Y)','Move Upper Eyelid Down']
        for control in controls:
            for key_name in controls:setattr(scene,ui._state['prop_names'][key_name],0.)
            setattr(scene,ui._state['prop_names'][control],.5)
            for obj in bpy.context.selected_objects:obj.select_set(False)
            face.select_set(True);bpy.context.view_layer.objects.active=face
            status=bpy.ops.pd.evaluate()
            tests.append({'control':control,'value':.5,'finished':status=={'FINISHED'},
                'template_max_motion_in_reference_eye_widths':float(np.linalg.norm(coords(avatar)-rest,axis=1).max()/width),
                'imported_vrm_max_motion_eye_widths':float(np.linalg.norm(coords(face)-base,axis=1).max()/width),
                'imported_vrm_evaluated_max_motion_eye_widths':float(np.linalg.norm(evaluated_coords(face)-imported_evaluated_base,axis=1).max()/width)})
        adapter=ui._state['adapter']
        neutral=adapter.evaluate({},{});shaped=adapter.evaluate({'Eye Size Y':.5},{})
        driven=np.linalg.norm(np.asarray(shaped.extra['world'])-np.asarray(neutral.extra['world']),axis=(1,2))>1e-7
        joints=neutral.extra['joints']
        g=reference.glb.g
        imported_joints={g['nodes'][i]['name'] for i in g['skins'][g['nodes'][reference.node]['skin']]['joints']}
        report['pd_shaping_trials']=tests
        report['topology']={'imported_face_vertices':len(base),'pd_face_vertices':len(rest),
                            'index_transfer_compatible':False if len(base)!=len(rest) else None}
        report['adjustment_bones']={'driven_by_eye_size_y':int(sum(driven)),
            'missing_in_exported_skin':sum(name not in imported_joints for name,on in zip(joints,driven) if on)}
        report['direct_pd_driving_supported']=False
        report['pd_updates_distinct_template_object']=avatar!=face
        report['test_passed']=bool(report['native_blink_import_parity']['passed'] and
            report['pd_load_finished'] and report['pd_evaluate_finished'] and
            all(t['finished'] and t['template_max_motion_in_reference_eye_widths']>1e-5 and t['imported_vrm_max_motion_eye_widths']==0 and t['imported_vrm_evaluated_max_motion_eye_widths']==0 for t in tests))
    finally:
        for name,was in timers.items():
            f=getattr(ui,name)
            if not was and bpy.app.timers.is_registered(f):bpy.app.timers.unregister(f)
        for t,original in props.items():
            for name in set(t.bl_rna.properties.keys())-original:
                if name.startswith('pd_'):delattr(t,name)
        ui._state.clear();ui._state.update(state)
        bpy.context.window.scene=old_scene
        for kind in kinds:
            collection=getattr(bpy.data,kind)
            for item in list(collection):
                if item not in before[kind]:collection.remove(item,do_unlink=True)
        for obj in bpy.context.selected_objects:obj.select_set(False)
        for obj in old_selected:obj.select_set(True)
        bpy.context.view_layer.objects.active=old_active
        report['datablock_sets_restored']={k:set(getattr(bpy.data,k))==before[k] for k in kinds}
        report['scene_selection_restored']=bpy.context.scene==old_scene and bpy.context.view_layer.objects.active==old_active and set(bpy.context.selected_objects)==set(old_selected)
        report['pd_properties_restored']=all(set(t.bl_rna.properties.keys())==original for t,original in props.items())
    return report


def run(vrm_path,addon_dir,pack_dir):
    import bpy,sys,numpy as np
    from pathlib import Path
    from _dsh_pd_reference_task.vrm import VRMReference
    from _dsh_pd_reference_task.pd_adapter import PDReference
    from _dsh_pd_reference_task.fit import validate,fit_lid_profile
    from _dsh_pd_reference_task.quality import source_quality
    if not addon_dir:
        addon_dir=str(Path(sys.modules['parametric_deformation'].__file__).parent)
    reference=VRMReference(vrm_path)
    profile=validate(reference.extract())
    pd=PDReference(addon_dir,pack_dir)
    validate(pd.extract())  # Regression: the shared extraction still supports PD packs.
    native=source_quality(reference);surrogate=source_quality(pd)
    width=eye_width(reference)
    side_expressions={}
    unilateral=[]
    for name in ('blinkLeft','blinkRight'):
        ref=VRMReference(vrm_path,name)
        unilateral.append(ref.delta)
        side_expressions[name]={label:float(np.linalg.norm(ref.delta[ref.base[:,0]*side>0],axis=1).max()/width)
                                for side,label in ((1,'positive_x'),(-1,'negative_x'))}
    sum_error=float(np.linalg.norm(reference.delta-sum(unilateral),axis=1).max()/width)
    live=test_imported_vrm(reference,vrm_path,str(pd.pack_dir))
    report={'blender_version':bpy.app.version_string,'private_input_sha256':reference.glb.sha256,
            'installed_pd_code_sha256':pd.addon_sha256,'native_blink':native,'pd_eye_joy':surrogate,
            'unilateral_max_motion_eye_widths':side_expressions,
            'bilateral_minus_left_plus_right_max_error_eye_widths':sum_error,'live_experiment':live,
            'preferred_lid_reference':'base-vrm.json',
            'recommendation':'Use the native blink for lid motion; retain geometric eyeline-band and open-sheet limitations. Direct PD identity shaping requires a new transfer or template adapter.'}
    if not live['test_passed'] or not all(live['datablock_sets_restored'].values()) or not live['scene_selection_restored'] or not live['pd_properties_restored']:
        raise RuntimeError('live VRM/PD verification or state restoration failed')
    return {'profile':profile,'fit':fit_lid_profile(profile),'verification':report}
