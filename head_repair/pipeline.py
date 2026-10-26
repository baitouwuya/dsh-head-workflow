# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,json,numpy as np,hashlib
from .config import write
from .audit import evaluate,aggregate_geometry,aggregate_semantic
from .controls import apply

def fingerprint(o,protected_faces=None):
    h=hashlib.sha256()
    h.update(np.array([v.co[:] for v in o.data.vertices],np.float32).tobytes())
    faces=[tuple(sorted(f.vertices)) for f in o.data.polygons]
    if protected_faces is not None:faces=[f for f in faces if f in protected_faces]
    h.update(str(sorted(faces)).encode())
    if o.data.shape_keys:
        for k in o.data.shape_keys.key_blocks:h.update(k.name.encode());h.update(np.array([v.co[:] for v in k.data],np.float32).tobytes())
    return h.hexdigest()

def run(profile,inputs,out):
    log=[]
    def event(message):
        print(message,flush=True);log.append(message);(out/'log.txt').write_text('\n'.join(log)+'\n')
    event('Opening immutable input copy');bpy.ops.wm.open_mainfile(filepath=str(inputs['blend']));scene=bpy.context.scene
    protected_faces={tuple(sorted(f)) for f in json.loads((inputs['source']/'refinement_source/protected_source_face_indices.json').read_text())}
    protected={o.name:fingerprint(o,protected_faces) for o in scene.objects if o.type=='MESH' and 'Hair' in o.name and not o.get('refinement_excluded_reference')}
    body=next(o for o in scene.objects if o.type=='MESH' and 'BodyFace' in o.name);original={k.name:np.array([v.co[:] for v in k.data]) for k in body.data.shape_keys.key_blocks};source_count=len(body.data.vertices)
    if profile['stages']['mouth']:
        from .mouth import build
        event('Rebuilding mouth from profile');manifest,construction,mouth=build(inputs['source'],str(inputs['mouth_color']),profile['geometry']['mouth']);write(out/'mouth-build.json',mouth)
    else:
        manifest=json.loads((inputs['source']/'control_manifest.json').read_text());construction=json.loads((inputs['source']/'evidence/head/construction.json').read_text())
    manifest['jaw']['maximum_degrees']=profile['geometry']['mouth']['poses'][-1];manifest['jaw']['supported_maximum_degrees']=None
    appearance_report=None
    if profile['stages']['eyes']:
        from .legacy import remove_eye_planes
        event('Removing obsolete eye-plane components; protecting original hair faces');write(out/'legacy-eye-planes.json',remove_eye_planes(json.loads(inputs['hair_components'].read_text()),profile['geometry']['eyes']['remove_legacy_eye_components'],protected_faces))
        from .eyes import build
        event('Rebuilding continuous eyelid strips');regions=build(profile['character'],profile['geometry']['eyes'],profile['appearance'],inputs['face_atlas'],json.loads(inputs['face_atlas'].with_suffix('.png.json').read_text()));write(out/'eye-construction.json',regions)
        if profile['stages']['appearance']:
            from .appearance import apply as color
            event('Fitting source-derived eyelid albedo');appearance_report=color(regions,str(inputs['face_atlas']),str(inputs['skin_fit']),profile['appearance'],out);write(out/'appearance.json',appearance_report)
        if profile['geometry']['fairing']['enabled']:
            from .fairing import run as fair
            event('Solving continuous eyelid and collar depth');write(out/'fairing.json',fair(profile,regions))
        if profile['geometry']['subdivision']['levels']:
            from .subdivision import run as subdivide
            event('Refining the continuous eye surface');write(out/'subdivision.json',subdivide(profile))
    body=next(o for o in scene.objects if o.type=='MESH' and 'BodyFace' in o.name);keys=body.data.shape_keys.key_blocks;base=np.array([v.co[:] for v in keys['Basis'].data])[:source_count]
    delta_error=max(float(np.max(abs((np.array([v.co[:] for v in keys[n].data])[:source_count]-base)-(original[n]-original['Basis'])))) for n in manifest['original_controls'])
    metrics={'protected_hair_changes':sum(fingerprint(bpy.data.objects[n],protected_faces)!=digest for n,digest in protected.items()),'original_control_delta_error':delta_error}
    if appearance_report:metrics['image_pixel_space_error']=appearance_report['pixelSpaceError']
    write(out/'control_manifest.json',manifest);write(out/'construction.json',construction)
    from .measure import geometry,controls
    event('Measuring edited surface geometry');geometry_rows=geometry(profile,manifest);write(out/'geometry-measurements.json',geometry_rows);geometry_summary=aggregate_geometry(profile,geometry_rows);metrics.update(geometry_summary['metrics']);coverage={'geometry':geometry_summary['coverage']}
    apply(manifest,{});bpy.ops.wm.save_as_mainfile(filepath=str(out/'head.blend'));rig=next(o for o in scene.objects if o.type=='ARMATURE')
    for o in scene.objects:o.select_set(o.type in ['MESH','ARMATURE'] and not o.get('refinement_excluded_reference') and 'Icosphere' not in o.name)
    bpy.context.view_layer.objects.active=rig;bpy.ops.export_scene.gltf(filepath=str(out/'head.glb'),export_format='GLB',use_selection=True,use_active_scene=True,export_skins=True,export_morph=True,export_animations=False,export_vertex_color=profile['export']['vertex_color'],export_vertex_color_name=profile['export']['vertex_color_name'],export_all_vertex_colors=False)
    event('Reimporting actual GLB for semantic and control checks')
    semantic=None
    if profile['stages']['semantic']:
        from .semantic import measure
        semantic=measure(profile,manifest,construction,out);write(out/'semantic-measurements.json',semantic)
    else:bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(out/'head.glb'))
    semantic_summary=aggregate_semantic(profile,semantic);metrics.update(semantic_summary['metrics']);coverage['semantic']=semantic_summary['coverage'];write(out/'observability.json',coverage)
    observation=controls(profile,manifest);write(out/'control-measurements.json',observation);metrics.update(observation['metrics']);write(out/'measurements.json',metrics);write(out/'audit.json',evaluate(profile,metrics))
    if profile['stages']['render']:
        from .render import render
        event('Rendering fixed profile camera views');render(profile,manifest,out/'renders')
    event('Candidate complete; visual review remains required. No acceptance claimed.')
