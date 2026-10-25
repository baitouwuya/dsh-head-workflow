# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Run the seven stages plus the dependencies formerly held in a live session."""
import importlib
import json
import math
import time
import types
from pathlib import Path

from .config import load, sha256, validate_input


def stage(h, name):
    started = time.perf_counter()
    importlib.import_module('.stages.' + name, __package__).run(h)
    record = {'stage': name, 'seconds': time.perf_counter() - started}
    h.steps.append(record)
    with (h.root / 'log.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record) + '\n')


def require_one(objects, predicate, label):
    matches = [obj for obj in objects if predicate(obj)]
    if len(matches) != 1:
        raise ValueError('Expected one ' + label + '; found ' + str(len(matches)))
    return matches[0]


def setup(h, input_path):
    import bpy
    import numpy as np
    from mathutils import Matrix
    h.source_scene = bpy.data.scenes.new('dsh-head-source-reference')
    bpy.context.window.scene = h.source_scene
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(input_path))
    h.sources = [o for o in bpy.data.objects if o not in before]
    h.src_body = require_one(h.sources, lambda o: o.type == 'MESH' and o.name.startswith(h.config['body_prefix']), 'body')
    h.src_hair = require_one(h.sources, lambda o: o.type == 'MESH' and o.name.startswith(h.config['hair_prefix']), 'hair')
    h.src_rig = require_one(h.sources, lambda o: o.type == 'ARMATURE', 'armature')
    if h.config['head_bone'] not in h.src_rig.data.bones:
        raise ValueError('Head bone missing')
    for obj in [h.src_body, h.src_hair]:
        if max(abs(obj.matrix_world[i][j] - Matrix.Identity(4)[i][j]) for i in range(4) for j in range(4)) > 1e-5:
            raise ValueError('Input must use identity mesh world transforms in the documented canonical frame')
        if not obj.data.uv_layers.active or not obj.data.shape_keys:
            raise ValueError('Input meshes need UVs and shape keys')
        if any(len(f.vertices) != 3 for f in obj.data.polygons):
            raise ValueError('Input source meshes must be triangulated')
        missing = set(h.config['original_controls']) - set(obj.data.shape_keys.key_blocks.keys())
        if missing:
            raise ValueError('Missing original controls: ' + ', '.join(sorted(missing)))
    h.scene = bpy.data.scenes.new('dsh-head-build')
    h.copymap = {}
    for obj in h.sources:
        copy = obj.copy()
        copy.data = obj.data.copy() if obj.data else None
        copy.name = 'dsh-work-' + obj.name
        h.scene.collection.objects.link(copy)
        h.copymap[obj] = copy
    for obj, copy in h.copymap.items():
        if obj.parent in h.copymap:
            copy.parent = h.copymap[obj.parent]
        for modifier in copy.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object in h.copymap:
                modifier.object = h.copymap[modifier.object]
        if copy.animation_data:
            copy.animation_data_clear()
    h.body, h.hair, h.rig = [h.copymap[o] for o in (h.src_body, h.src_hair, h.src_rig)]
    for obj in h.sources:
        obj.name = 'dsh-reference-' + obj.name
    h.body.name, h.hair.name, h.rig.name = 'dsh-HeadWork_BodyFace', 'dsh-HeadWork_BlueHairStar', 'dsh-HeadWork_Rig'
    h.eyes = h.config['eyes']
    h.lip = h.config['lip']
    h.socket_rims = []
    bpy.context.window.scene = h.scene


def apertures(h):
    import numpy as np
    cy = sum(h.lip['y_range']) / 2
    ry = (h.lip['y_range'][1] - h.lip['y_range'][0]) / 2
    polygon = []
    for index in range(48):
        theta = 2 * math.pi * index / 48
        y = cy + ry * math.cos(theta)
        z = float(np.polyval(h.lip['fit_z_of_y_coefficients'], y)) + .00012 * math.sin(theta)
        polygon.append([y, z])
    h.mouth_region = {'label': 'mouth', 'polygon': h.hull(polygon), 'back': .004}
    h.all_regions = h.eyes + [h.mouth_region]
    h.rebuild_apertures(h.src_body, h.body, h.all_regions)
    h.rebuild_apertures(h.src_hair, h.hair, h.all_regions)


def stitches(h):
    import bpy
    import numpy as np
    for number, spec in enumerate(h.config['stitches']):
        eye = next(e for e in h.eyes if e['label'] == spec['eye'])
        y0, z1 = spec['y'], spec['closed_z']
        limits = h.vertical_limits(eye, y0)
        if not limits:
            raise ValueError('Corrective stitch lies outside its eye aperture')
        z0 = limits[1] + .00045
        half_w, half_h = spec['width'] / 2, spec['height'] / 2
        vertices, uvs = [], []
        for dy, dz in [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]:
            y, z = y0 + dy, z0 + dz
            sample = h.sample(h.src_body, y, z)
            if sample is None:
                raise ValueError('Corrective stitch cannot sample the source skin')
            vertices.append([h.globe_x(eye, y, z) + .00065, y, z])
            uvs.append(sample['uv'])
        mesh = bpy.data.meshes.new('dsh-lid-stitch-' + str(number))
        mesh.from_pydata(vertices, [], [(0, 1, 2, 3)])
        mesh.update()
        obj = bpy.data.objects.new(mesh.name, mesh)
        h.scene.collection.objects.link(obj)
        sample = h.sample(h.src_body, y0, z0)
        mi = h.src_body.data.polygons[sample['face']].material_index
        mesh.materials.append(h.src_body.data.materials[mi])
        uv = mesh.uv_layers.new(name='UVMap')
        for li in range(4):
            uv.data[li].uv = uvs[mesh.loops[li].vertex_index]
        for name in ['Color', 'Color.001']:
            attr = mesh.color_attributes.new(name=name, type='BYTE_COLOR', domain='CORNER')
            for item in attr.data:
                item.color = (1, 1, 1, 1)
        obj.shape_key_add(name='Basis', from_mix=False)
        for weight in [.25, .5, .75, 1]:
            coords = []
            for point in vertices:
                y, z = point[1], point[2] + (z1 - z0) * weight
                coords.append([h.globe_x(eye, y, z) + .00065, y, z])
            key = obj.shape_key_add(name='blink' + spec['eye'].capitalize() + '_' + str(int(weight * 100)), from_mix=False)
            key.data.foreach_set('co', np.array(coords, np.float32).ravel())
            key.value = 0
        obj.parent = h.rig
        group = obj.vertex_groups.new(name=h.config['head_bone'])
        group.add([0, 1, 2, 3], 1, 'REPLACE')
        modifier = obj.modifiers.new('dsh-lid-skin', 'ARMATURE')
        modifier.object = h.rig
        h.socket_rims.append(obj)


def build(input_path, config_path, output_path, render=False):
    import bpy
    input_path, output_path = Path(input_path).resolve(), Path(output_path).resolve()
    config = load(config_path)
    input_hash = validate_input(input_path, config)
    if output_path.exists():
        raise FileExistsError('Output directory must be new: ' + str(output_path))
    if bpy.context.mode != 'OBJECT':
        raise ValueError('Start in Object mode')
    original_scene = bpy.context.scene
    original_active = bpy.context.view_layer.objects.active
    original_selection = list(bpy.context.selected_objects)
    original_frame = original_scene.frame_current
    original_names = {o: o.name for o in bpy.data.objects}
    output_path.mkdir(parents=True)
    h = types.SimpleNamespace(config=config, root=output_path / 'evidence', out=output_path / 'assets',
                              original_scene=original_scene, render_enabled=render, steps=[])
    h.root.mkdir()
    status = 'failed'
    error = None
    try:
        setup(h, input_path)
        stage(h, 'components')
        stage(h, 'head_helpers')
        h.render('source', h.source_scene)
        apertures(h)
        stage(h, 'build_eyes')
        stage(h, 'fit_lids_and_blink')
        stage(h, 'boundaries')
        stage(h, 'build_jaw_mouth')
        stage(h, 'repair_oral_envelope')
        stitches(h)
        stage(h, 'expressions_and_export')
        stage(h, 'head_subset_and_export')
        stage(h, 'anatomy')
        stage(h, 'dense_closure')
        anatomy = json.loads((h.root / 'anatomy-occlusion-audit.json').read_text())
        if any(r['visible_globe_rays'] for r in h.dense_closure):
            raise RuntimeError('Closed-eye verification failed; inspect dense-closure-audit.json')
        if any(r['boundary_edges'] or r['nonmanifold_edges'] for r in anatomy['closed_eyeballs']):
            raise RuntimeError('Eyeball topology verification failed')
        if anatomy['mouth_probe']['back_head_or_empty_rays']:
            raise RuntimeError('Mouth visibility verification failed')
        if h.hair_audit['max_neutral_displacement'] > 1e-7 or h.hair_audit['missing_or_changed_faces']:
            raise RuntimeError('Protected hair changed')
        (h.out / 'viewer.json').write_text(json.dumps(config['viewer'], indent=2))
        status = 'passed_blender_checks'
        return h
    except Exception as exc:
        error = str(exc)
        raise
    finally:
        bpy.context.window.scene = original_scene
        bpy.context.view_layer.objects.active = original_active
        original_scene.frame_set(original_frame)
        for obj in original_scene.objects:
            obj.select_set(obj in original_selection)
        unchanged = sha256(input_path) == input_hash
        records = []
        for file in sorted(output_path.rglob('*')):
            if file.is_file():
                records.append({'path': file.relative_to(output_path).as_posix(), 'sha256': sha256(file)})
        result = {'status': status, 'error': error, 'input_sha256': input_hash, 'input_unchanged': unchanged,
                  'blender_version': bpy.app.version_string, 'original_objects_retained': all(o.name == name for o, name in original_names.items()),
                  'steps': h.steps, 'files': records, 'web_engine_verification': 'Run the included browser harness separately'}
        (output_path / 'manifest.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        (output_path / 'sha256.txt').write_text(''.join(r['sha256'] + '  ' + r['path'] + '\n' for r in records), encoding='utf-8')
