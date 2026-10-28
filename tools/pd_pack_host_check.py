# SPDX-License-Identifier: GPL-3.0-or-later
"""Runs inside the host Blender through the required bridge; prints no arrays."""
def run(source, output, sources):
    import ast
    import bpy
    import copy
    import hashlib
    import json
    import sys
    from pathlib import Path
    import numpy as np
    from mathutils import Matrix, Quaternion, Vector
    from _pdpack_check.convert import convert
    from _pdpack_check.gltf import GLB
    from parametric_deformation.core.config import load_pack, validate_pack
    from parametric_deformation.tools import load_driver
    from parametric_deformation.ui import panels as ui
    if ui._state.get('pack') is not None or bpy.context.mode != 'OBJECT' or any(o.name.startswith('PD_Avatar') for o in bpy.data.objects):
        raise RuntimeError('real UI check requires an idle PD session with no PD_Avatar objects')
    summary = convert(source, output, runtime_source=sources['runtime'], driver_source=sources['driver'])
    issues = validate_pack(output)
    if issues:
        raise RuntimeError(str(issues))
    pack = load_pack(output); adapter = load_driver(output); adapter.load(pack, output)
    reader = GLB(Path(source).read_bytes()); g = reader.g
    parents = {}
    for i, node in enumerate(g['nodes']):
        for child in node.get('children', []): parents[child] = i
    worlds = {}
    def world(i):
        if i not in worlds:
            node = g['nodes'][i]
            if 'matrix' in node:
                m = Matrix(np.array(node['matrix']).reshape(4, 4).T.tolist())
            else:
                x, y, z, w = node.get('rotation', [0, 0, 0, 1])
                m = Matrix.LocRotScale(Vector(node.get('translation', [0, 0, 0])),
                    Quaternion((w, x, y, z)), Vector(node.get('scale', [1, 1, 1])))
            worlds[i] = (world(parents[i]) @ m) if i in parents else m
        return worlds[i]
    axis = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
    binds = g['extensions']['VRMC_vrm']['expressions']['preset']['blink']['morphTargetBinds']
    def oracle(desc, weight):
        ni, pi = desc['source_node'], desc['source_primitive']
        node = g['nodes'][ni]; mesh = g['meshes'][node['mesh']]; p = mesh['primitives'][pi]
        v = reader.accessor(p['attributes']['POSITION']).astype(float)
        defaults = node.get('weights', mesh.get('weights', [0.] * len(p.get('targets', []))))
        for k, value in enumerate(defaults):
            if value and 'POSITION' in p['targets'][k]: v += value * reader.accessor(p['targets'][k]['POSITION'])
        for b in binds:
            if b['node'] == ni: v += weight * b['weight'] * reader.accessor(p['targets'][b['index']]['POSITION'])
        if 'skin' in node:
            skin = g['skins'][node['skin']]
            ibm = reader.accessor(skin['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1)
            matrices = np.array([np.array(world(j), dtype=float) @ inv for j, inv in zip(skin['joints'], ibm)])
            ids = reader.accessor(p['attributes']['JOINTS_0']); weights = reader.accessor(p['attributes']['WEIGHTS_0'])
            hom = np.column_stack([v, np.ones(len(v))]); result = np.zeros_like(hom)
            for k in range(4): result += weights[:,k,None] * np.einsum('vij,vj->vi', matrices[ids[:,k]], hom)
            v = result[:,:3]
        else:
            v = (np.column_stack([v,np.ones(len(v))]) @ np.array(world(ni)).T)[:,:3]
        selected = np.load(Path(output)/desc['source_vertex_indices']['file'])
        return (v @ axis.T)[selected]
    rest = adapter.evaluate({}, {}).meshes
    all_points = np.concatenate([m[1] for m in rest]); height = float(np.ptp(all_points[:,2]))
    samples = []
    for w in (0., .25, .5, .75, 1.):
        result = adapter.evaluate({'vrm_blink':w}, {})
        errors = []; motions = []; moved = 0
        for desc, (_, points, faces, uv), base in zip(adapter.runtime.meshes, result.meshes, rest):
            want = oracle(desc['desc'],w)
            errors.extend(np.linalg.norm(points-want,axis=1)/height)
            motion = np.linalg.norm(points-base[1],axis=1)/height
            motions.extend(motion); moved += int(sum(motion>1e-7))
        samples.append({'weight':w,'max_error_over_height':float(max(errors)),
                        'rms_error_over_height':float(np.sqrt(np.mean(np.square(errors)))),
                        'max_motion_over_height':float(max(motions)),'moved_vertices':moved})
    assert max(s['max_error_over_height'] for s in samples)<2e-6
    assert samples[-1]['moved_vertices']>0
    # Test the actual operators and viewport writer, not just the Python adapter.
    old_scene = bpy.context.window.scene; old_active = bpy.context.view_layer.objects.active
    selection = list(bpy.context.selected_objects)
    kinds = ['objects','scenes','collections','meshes','armatures','materials','node_groups','images','actions','shape_keys']
    before = {k:set(getattr(bpy.data,k)) for k in kinds}; old_state = copy.deepcopy(ui._state)
    properties = {t:set(t.bl_rna.properties.keys()) for t in (bpy.types.Scene,bpy.types.Collection)}
    flags = ['pd_pack_path','pd_live_update','pd_use_rig','pd_filter','pd_preset_name','pd_preset_path']
    old_flags = {c:{f:getattr(c,f) for f in flags if hasattr(c,f)} for c in before['collections']}
    timers = {n:bpy.app.timers.is_registered(getattr(ui,n)) for n in ('_param_poll','_flush_timer','_auto_load_pack','_auto_load_preset')}
    ui_samples=[]
    try:
        scene=bpy.data.scenes.new('Private converted VRM PD pack proof');bpy.context.window.scene=scene
        scene.pd_live_update=False
        assert bpy.ops.pd.load_pack(pack_path=str(output))=={'FINISHED'}
        ui._host().pd_live_update=False
        for w in (0.,.25,.5,.75,1.):
            setattr(scene,ui._state['prop_names']['vrm_blink'],w)
            assert bpy.ops.pd.evaluate()=={'FINISHED'}
            expected=ui._state['adapter'].evaluate({'vrm_blink':w},{})
            maximum=0.
            for i,(name,points,faces,uv) in enumerate(expected.meshes):
                obj=bpy.data.objects['PD_Avatar' if i==0 else 'PD_Avatar_'+name]
                actual=np.array([v.co[:] for v in obj.data.vertices])
                maximum=max(maximum,float(np.linalg.norm(actual-points,axis=1).max()/height))
            assert maximum<1e-7
            ui_samples.append({'weight':w,'max_viewport_write_error_over_height':maximum})
    finally:
        ui._state['suspending']=True
        for c, values in old_flags.items():
            for f,v in values.items(): setattr(c,f,v)
        for n,was in timers.items():
            if not was and bpy.app.timers.is_registered(getattr(ui,n)):bpy.app.timers.unregister(getattr(ui,n))
        for t,original in properties.items():
            for n in set(t.bl_rna.properties.keys())-original:
                if n.startswith('pd_'):delattr(t,n)
        ui._state.clear();ui._state.update(old_state)
        bpy.context.window.scene=old_scene
        for kind in kinds:
            collection=getattr(bpy.data,kind)
            for item in list(collection):
                if item not in before[kind]:collection.remove(item,do_unlink=True)
        for o in bpy.context.selected_objects:o.select_set(False)
        for o in selection:o.select_set(True)
        bpy.context.view_layer.objects.active=old_active
    restored=all(set(getattr(bpy.data,k))==before[k] for k in kinds)
    assert restored
    addon=Path(sys.modules['parametric_deformation'].__file__).parent
    export_text=(addon/'export/__init__.py').read_text()
    executable=[n for n in ast.parse(export_text).body if not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str))]
    assert not executable
    files=['core/config.py','core/interfaces.py','core/generic.py','core/pipeline.py','tools/__init__.py','ui/panels.py','export/__init__.py']
    return {'passed':True,'blender_version':bpy.app.version_string,'conversion':summary,
            'implementation_sha256':{name:hashlib.sha256(text.encode('utf8')).hexdigest() for name,text in sources.items()},
            'real_validate_pack_issues':issues,'real_driver_class':type(adapter).__name__,
            'numeric_blink_samples':samples,'real_pd_operator_samples':ui_samples,
            'scene_datablocks_restored':restored,'export_module_executable_statements':0,
            'pd_can_emit_vrm':False,'private_pack_published':False,
            'audited_addon_sha256':{f:hashlib.sha256((addon/f).read_bytes()).hexdigest() for f in files}}
