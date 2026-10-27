# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Run only INSIDE the native Lab's supplied Blender, after sealing its candidate.

Usage: blender --background --python native_render_verification.py -- request.json
Request paths, transforms, controller names, views and object roles are runtime
measurements supplied by the native adapter. This script never exports a model.
It records the renderer actually provided; it does not install or select a
different Blender version. Source and candidate imports use identical views.
"""
import json,sys,math
from numbers import Real
from pathlib import Path
from blender_runtime_compat import set_render_engine

# Pure request/control validation is importable by ordinary Python tests. The
# supplied Blender runtime is loaded only by main(), which runs inside the Lab.
bpy=None
Matrix=None
Vector=None


def load_native_runtime():
    global bpy,Matrix,Vector
    import bpy as native_bpy
    from mathutils import Matrix as NativeMatrix,Vector as NativeVector
    bpy=native_bpy;Matrix=NativeMatrix;Vector=NativeVector


def validate_controller(mapping):
    """Validate every raw knot before normalizing its order.

    Zero is an implicit neutral basis, not a named morph knot. No invalid raw
    entry is filtered out, coerced from text/bool, or hidden by an absent mesh.
    """
    if not isinstance(mapping,dict):raise ValueError('Runtime controller must be an object')
    result={};owners={}
    for control,knots in mapping.items():
        if not isinstance(control,str) or not control.strip() or not isinstance(knots,list) or not knots:
            raise ValueError('Every runtime control needs a name and a nonempty knot list')
        measured=[];seen=set()
        for knot in knots:
            if not isinstance(knot,dict) or 'value' not in knot or 'name' not in knot:
                raise ValueError('Every morph knot needs an explicit value and name')
            raw=knot['value'];name=knot['name']
            if isinstance(raw,bool) or not isinstance(raw,Real) or not math.isfinite(raw) or not 0<raw<=1:
                raise ValueError('Raw morph knots must be finite numeric weights in (0,1]; zero is implicit neutral')
            if not isinstance(name,str) or not name.strip():raise ValueError('Morph knot names must be nonempty strings')
            weight=float(raw)
            if weight in seen:raise ValueError('Runtime morph knot weights must be unique')
            if name in owners:raise ValueError('A morph name cannot be reused by multiple runtime knots or controls')
            seen.add(weight);owners[name]=control;measured.append((weight,name))
        measured.sort()
        if measured[-1][0]!=1:raise ValueError('Runtime morph knots must end at normalized weight one')
        result[control]=tuple(measured)
    return result


def validate_control_values(mapping,values):
    if not isinstance(values,dict):raise ValueError('Control values must be an object')
    if any(name not in mapping for name in values):raise ValueError('A requested control is absent from the runtime mapping')
    resolved={}
    for name in mapping:
        value=values.get(name,0)
        if isinstance(value,bool) or not isinstance(value,Real) or not math.isfinite(value) or not 0<=value<=1:
            raise ValueError('Control values must be finite numeric values in [0,1]')
        resolved[name]=float(value)
    return resolved


def apply_control_values(objects,mapping,values):
    """Set only configured blink morphs; preserve all unrelated imported values.

    Build and validate the entire assignment plan before changing any key. A mesh
    that participates in a requested nonzero control must have its complete knot
    mapping; a different mesh cannot conceal missing knots on that mesh.
    """
    measured=validate_controller(mapping);values=validate_control_values(measured,values)
    configured={name for knots in measured.values() for weight,name in knots}
    participants={name:0 for name in measured};plan=[]
    for obj in objects:
        if obj.type!='MESH' or not obj.data.shape_keys:continue
        keys=list(obj.data.shape_keys.key_blocks)
        if not keys:continue
        by_name={key.name:key for key in keys}
        if keys[0].name in configured:raise ValueError('The reference basis cannot be a configured blink morph')
        assignments={name:0. for name in configured if name in by_name}
        for control,knots in measured.items():
            names={name for weight,name in knots};present=names.intersection(by_name)
            if not present:continue
            participants[control]+=1
            if values[control]>0 and present!=names:
                raise ValueError('Requested morph mapping is incomplete on imported mesh '+str(getattr(obj,'name','<unnamed>')))
            points=((0.,None),)+knots
            for (lo,ln),(hi,hn) in zip(points[:-1],points[1:]):
                if lo<=values[control]<=hi:
                    t=(values[control]-lo)/(hi-lo)
                    if ln is not None and ln in by_name:assignments[ln]=1-t
                    if hn in by_name:assignments[hn]=t
                    break
        plan.extend((by_name[name],value) for name,value in assignments.items())
    for control,count in participants.items():
        if values[control]>0 and count==0:raise ValueError('Requested morph mapping is absent from the imported candidate')
    for key,value in plan:key.value=value
    return {'configured_morph_assignments':len(plan),'control_mesh_participants':participants,
            'unrelated_morph_values_changed':False}

def import_model(path,transform):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    path=Path(path)
    if path.suffix.lower() in ('.glb','.gltf'):bpy.ops.import_scene.gltf(filepath=str(path))
    elif path.suffix.lower()=='.fbx':bpy.ops.import_scene.fbx(filepath=str(path))
    else:raise ValueError('Unsupported runtime model format for matched rendering')
    frame=Matrix(transform)
    for o in list(bpy.context.scene.objects):
        if o.parent is None:o.matrix_world=frame@o.matrix_world
        if o.animation_data:o.animation_data_clear()
        if o.type=='MESH' and o.data.shape_keys and o.data.shape_keys.animation_data:o.data.shape_keys.animation_data_clear()
    bpy.context.view_layer.update()

def set_controls(mapping,values):
    if bpy is None:raise RuntimeError('Rendering controls require the native Lab runtime')
    result=apply_control_values(bpy.context.scene.objects,mapping,values)
    bpy.context.view_layer.update()
    return result

def setup(request):
    scene=bpy.context.scene
    set_render_engine(scene,request.get('engine',scene.render.engine))
    scene.render.resolution_x=int(request.get('resolution',512));scene.render.resolution_y=int(request.get('resolution',512));scene.render.resolution_percentage=100
    if scene.render.engine=='CYCLES':scene.cycles.samples=int(request.get('samples',16));scene.cycles.seed=0
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard'
    world=bpy.data.worlds.new('matched-review-world');world.use_nodes=True;next(n for n in world.node_tree.nodes if n.bl_idname=='ShaderNodeBackground').inputs[0].default_value=(.35,.35,.35,1);scene.world=world
    for spec in request['lights']:
        bpy.ops.object.light_add(type='AREA',location=spec['position']);light=bpy.context.object;light.data.energy=spec['energy'];light.data.size=spec['size'];light.rotation_euler=(Vector(spec['target'])-light.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add();camera=bpy.context.object;camera.data.type='ORTHO';scene.camera=camera
    return scene,camera

def render_views(scene,camera,views,output,prefix):
    files=[]
    for view in views:
        camera.location=view['position'];camera.rotation_euler=(Vector(view['target'])-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=float(view['ortho_scale']);path=output/(prefix+'-'+view['label']+'.png');scene.render.filepath=str(path);bpy.ops.render.render(write_still=True);files.append(str(path))
    return files

def object_audit():
    out=[]
    for o in bpy.context.scene.objects:
        if o.type!='MESH':continue
        o.data.calc_loop_triangles();p=[o.matrix_world@v.co for v in o.data.vertices];volume=sum(p[t.vertices[0]].dot(p[t.vertices[1]].cross(p[t.vertices[2]])) for t in o.data.loop_triangles)/6
        out.append({'name':o.name,'vertices':len(p),'triangles':len(o.data.loop_triangles),'signed_volume':volume,'smooth_polygons':sum(f.use_smooth for f in o.data.polygons),'color_attributes':[a.name for a in o.data.color_attributes],'materials':[{'name':m.name,'nodes':[n.bl_idname for n in m.node_tree.nodes] if m and m.use_nodes else []} for m in o.data.materials if m]})
    return out

def main(request_path):
    request=json.loads(Path(request_path).read_text())
    mapping=request.get('controller',{});validated=validate_controller(mapping)
    for state in request['states']:validate_control_values(validated,state['values'])
    for ablation in request.get('ablations',[]):validate_control_values(validated,ablation['values'])
    load_native_runtime()
    out=Path(request['output_directory']);out.mkdir(parents=True,exist_ok=True);report={'blender_version':bpy.app.version_string,'version_source':'native Lab provided runtime','request':request,'models':[]}
    for role in ['source','candidate']:
        spec=request[role];import_model(spec['path'],spec['world_to_review']);scene,camera=setup(request);mapping=request.get('controller',{});states=[{'label':'neutral','values':{}}] if role=='source' else request['states'];record={'role':role,'path':spec['path'],'renderer':scene.render.engine,'objects':object_audit(),'renders':[]}
        for state in states:
            control_audit=set_controls(mapping,state['values']);record.setdefault('control_audits',[]).append({'state':state['label'],**control_audit});record['renders']+=render_views(scene,camera,request['views'],out,role+'-'+state['label'])
        report['models'].append(record)
    # Optional shading-only ablations of the same sealed candidate. No geometry
    # reconstruction/retry, export or changes to the sealed candidate occur.
    for ablation in request.get('ablations',[]):
        import_model(request['candidate']['path'],request['candidate']['world_to_review']);scene,camera=setup(request);set_controls(request.get('controller',{}),ablation['values'])
        if ablation['kind']=='reverse_generated_upper_core_winding':
            import bmesh
            for name in request['generated_upper_core_objects']:
                o=bpy.data.objects.get(name)
                if not o or o.type!='MESH':raise ValueError('Measured generated upper-core object is missing')
                bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.reverse_faces(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free();o.data.update()
        elif ablation['kind']=='generated_flat_shading':
            for name in request['generated_lid_objects']:
                o=bpy.data.objects.get(name)
                if not o or o.type!='MESH':raise ValueError('Measured generated lid object is missing')
                for face in o.data.polygons:face.use_smooth=False
        else:raise ValueError('Unknown diagnostic ablation')
        files=render_views(scene,camera,request['views'],out,'ablation-'+ablation['kind']);report.setdefault('ablations',[]).append({'kind':ablation['kind'],'renderer':scene.render.engine,'renders':files,'candidate_file_unchanged':True})
    (out/'native-render-report.json').write_text(json.dumps(report,indent=2))
if __name__=='__main__':main(sys.argv[sys.argv.index('--')+1])
