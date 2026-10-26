# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Private INTERNAL-ONLY extraction of observed VRoid structural source parts.

Run extract() inside the approved Blender connection. The only disk data read or
written are under bpy.app.driver_namespace['dsh_internal_research_root'].
No exports, source image/UV/material copies, outer facial skin, or shared paths.
Extracted sheets remain OPEN and UNACCEPTED; this is not a completed assembly.
"""
from pathlib import Path
import collections
import hashlib
import json
import math
import os
import struct

SOURCE_SCENE = 'INTERNAL_ONLY__VRoid_SourceReference'
TARGET_SCENE = 'INTERNAL_ONLY__SM_Assembly'
STAGING = 'INTERNAL_ONLY__STRUCTURAL_STAGING'


def _private_root(bpy):
    value = bpy.app.driver_namespace.get('dsh_internal_research_root')
    if not isinstance(value, (str, os.PathLike)):
        raise RuntimeError('Missing private root in bpy.app.driver_namespace')
    root = Path(value).resolve(strict=True)
    base = (Path(os.environ['LOCALAPPDATA']) / 'dsh' / 'internal-research').resolve()
    if root == base or base not in root.parents or str(root).startswith('\\\\'):
        raise RuntimeError('Research root must be a private local run directory below LOCALAPPDATA/dsh/internal-research')
    if not root.is_dir():
        raise RuntimeError('Private research root is not a directory')
    return root


def _observed_groups(document, face_count):
    if document.get('method') != 'Exact float32 position and all stored shape deltas; no proximity welding':
        raise RuntimeError('Unexpected component method; exact deformation-compatible ancestry required')
    labels = {}
    for row in document.get('groups', []):
        label = row.get('label')
        if label in labels:
            raise RuntimeError('Duplicate component group label')
        labels[label] = row.get('groups', [])
    mouth = labels.get('mouth_all', [])
    eyes = labels.get('eye_white', [])
    if sorted(r.get('faces') for r in mouth) != [384, 384, 448, 480]:
        raise RuntimeError('Observed four mouth-part counts changed')
    if len(eyes) != 2 or [r.get('faces') for r in eyes] != [264, 264]:
        raise RuntimeError('Observed two inner-lid source-sheet counts changed')
    used = set()
    for row in mouth + eyes:
        ids = row.get('face_ids')
        if not isinstance(ids, list) or len(ids) != row['faces'] or len(set(ids)) != len(ids):
            raise RuntimeError('Missing, duplicated or incomplete source face IDs')
        if any(type(i) is not int or not 0 <= i < face_count for i in ids):
            raise RuntimeError('Invalid source face index')
        if used.intersection(ids):
            raise RuntimeError('Structural source selections overlap')
        used.update(ids)
    # Deliberately never return the skin group.
    return mouth, eyes


def _hash_source(obj):
    digest = hashlib.sha256()
    def xyz(co):
        digest.update(struct.pack('<3f', *map(float, co)))
    for vertex in obj.data.vertices:
        xyz(vertex.co)
        for membership in vertex.groups:
            digest.update(struct.pack('<If', membership.group, membership.weight))
    for face in obj.data.polygons:
        digest.update(struct.pack('<II', len(face.vertices), face.material_index))
        digest.update(struct.pack('<' + 'I' * len(face.vertices), *face.vertices))
    if obj.data.shape_keys:
        for key in obj.data.shape_keys.key_blocks:
            digest.update(key.name.encode('utf-8') + b'\0')
            digest.update(key.relative_key.name.encode('utf-8') + b'\0')
            for point in key.data:
                xyz(point.co)
            digest.update(struct.pack('<f?', key.value, key.mute))
    for row in obj.matrix_world:
        digest.update(struct.pack('<4f', *row))
    return digest.hexdigest()


def _vertices(source, face_ids):
    return sorted({int(v) for fi in face_ids for v in source.data.polygons[fi].vertices})


def _shape_movement(source, ids, token):
    keys = source.data.shape_keys
    if keys is None:
        raise RuntimeError('Structural reference has no stored shape keys')
    matches = [key for key in keys.key_blocks if token == key.name]
    if len(matches) != 1:
        raise RuntimeError('Expected one observed source shape key containing ' + token)
    key = matches[0]
    length = max((key.data[i].co - key.relative_key.data[i].co).length for i in ids)
    return {'key': key.name, 'maximum_relative_delta_m': float(length)}


def _edge_report(faces, labels=None):
    uses = collections.defaultdict(list)
    degenerate = 0
    for fi, face in enumerate(faces):
        ids = [labels[v] if labels is not None else v for v in face]
        if len(set(ids)) < 3:
            degenerate += 1
        for a, b in zip(ids, ids[1:] + ids[:1]):
            uses[tuple(sorted((a, b)))].append((a, b))
    return {'boundary_edges': sum(len(v) == 1 for v in uses.values()),
            'nonmanifold_edges': sum(len(v) > 2 for v in uses.values()),
            'same_direction_pairs': sum(len(v) == 2 and v[0] == v[1] for v in uses.values()),
            'degenerate_index_faces': degenerate}


def _compatible_labels(source, ids):
    keys = source.data.shape_keys.key_blocks
    basis = keys[0]
    mapping = {}
    labels = {}
    for i in ids:
        values = list(source.data.vertices[i].co)
        for key in keys:
            values.extend(key.data[i].co - basis.data[i].co)
        signature = struct.pack('<' + 'f' * len(values), *values)
        labels[i] = mapping.setdefault(signature, len(mapping))
    return labels


def extract():
    import bpy
    root = _private_root(bpy)
    component_file = root / 'deformation-compatible-welded-components.json'
    report_file = root / 'structural-extraction.json'
    if report_file.exists() or bpy.data.collections.get(STAGING):
        raise RuntimeError('Structural extraction already exists; no automatic replacement')
    document = json.loads(component_file.read_text(encoding='utf-8'))
    source_scene = bpy.data.scenes.get(SOURCE_SCENE)
    target_scene = bpy.data.scenes.get(TARGET_SCENE)
    if source_scene is None or target_scene is None or source_scene == target_scene:
        raise RuntimeError('Both distinct private source and assembly scenes must already exist')
    source = source_scene.objects.get('Face')
    if source is None or source.type != 'MESH':
        raise RuntimeError('Private reference scene must contain the observed Face mesh')
    if len(source.data.vertices) != 4709 or len(source.data.polygons) != 8280:
        raise RuntimeError('Observed private source Face topology changed')
    mouth, eyes = _observed_groups(document, len(source.data.polygons))
    if not source.data.shape_keys or not source.data.shape_keys.use_relative:
        raise RuntimeError('Expected relative source shape keys')
    before = _hash_source(source)
    source_objects = tuple(sorted(o.name for o in source_scene.objects))
    active_scene = bpy.context.window.scene if bpy.context.window else None
    roles = []
    teeth = [row for row in mouth if row['faces'] == 384]
    def center(row):
        ids = _vertices(source, row['face_ids'])
        points = [source.matrix_world @ source.data.vertices[i].co for i in ids]
        return [sum(p[j] for p in points) / len(points) for j in range(3)]
    teeth.sort(key=lambda row: center(row)[2])
    if center(teeth[1])[2] <= center(teeth[0])[2]:
        raise RuntimeError('Upper/lower teeth cannot be resolved by observed mean Z')
    for role, row in zip(('lower_teeth', 'upper_teeth'), teeth):
        response = _shape_movement(source, _vertices(source, row['face_ids']), 'Fcl_HA_Hide')
        if response['maximum_relative_delta_m'] <= 0:
            raise RuntimeError('Teeth candidate lacks observed Fcl_HA_Hide deformation')
        roles.append((role, row, response))
    lining = next(row for row in mouth if row['faces'] == 480)
    response = _shape_movement(source, _vertices(source, lining['face_ids']), 'Fcl_MTH_SkinFung')
    if response['maximum_relative_delta_m'] <= 0:
        raise RuntimeError('Oral-lining candidate lacks observed shape response')
    roles.append(('oral_lining_candidate', lining, response))
    roles.append(('tongue_candidate', next(row for row in mouth if row['faces'] == 448), {}))
    signs = []
    for row in eyes:
        x = center(row)[0]
        if x == 0:
            raise RuntimeError('Inner-lid source side is ambiguous')
        signs.append(1 if x > 0 else -1)
        roles.append(('inner_lid_source_positive_x' if x > 0 else 'inner_lid_source_negative_x', row,
                      {'classification': 'Deforming EyeWhite sheet; NOT a stationary complete eyeball'}))
    if sorted(signs) != [-1, 1]:
        raise RuntimeError('Inner-lid source sheets do not occupy opposite source X sides')
    staging = bpy.data.collections.new(STAGING)
    target_scene.collection.children.link(staging)
    staging['internal_only'] = True
    staging['acceptance'] = 'OPEN_SOURCE_PARTS_NOT_ACCEPTED'
    created = []
    report = {'internal_only': True, 'status': 'OPEN_PARTS_REQUIRE_CLOSURE_JOIN_AND_AUDIT',
              'exports_created': 0, 'source_images_or_materials_copied': 0,
              'source_file_sha256': hashlib.sha256(component_file.read_bytes()).hexdigest(),
              'source_object': source.name, 'source_scene': SOURCE_SCENE,
              'target_scene': TARGET_SCENE, 'parts': []}
    try:
        for role, row, response in roles:
            face_ids = sorted(row['face_ids'])
            ids = _vertices(source, face_ids)
            index = {old: new for new, old in enumerate(ids)}
            faces = [[index[int(v)] for v in source.data.polygons[fi].vertices] for fi in face_ids]
            name = 'INTERNAL_ONLY__' + role
            mesh = bpy.data.meshes.new(name)
            mesh.from_pydata([tuple(source.data.vertices[i].co) for i in ids], [], faces)
            mesh.update()
            obj = bpy.data.objects.new(name, mesh)
            created.append(obj)
            staging.objects.link(obj)
            obj.matrix_world = source.matrix_world.copy()
            obj['internal_only'] = True
            obj['acceptance'] = 'OPEN_NOT_ACCEPTED'
            obj['source_scene'] = SOURCE_SCENE
            obj['source_object'] = source.name
            obj['source_mesh'] = source.data.name
            obj['structural_role'] = role
            obj['not_a_complete_eyeball'] = role.startswith('inner_lid')
            obj['source_rig_not_copied_or_bound'] = True
            attr = mesh.attributes.new('internal_source_vertex_id', 'INT', 'POINT')
            for dest, original in zip(attr.data, ids):
                dest.value = original
            attr = mesh.attributes.new('internal_source_face_id', 'INT', 'FACE')
            for dest, original in zip(attr.data, face_ids):
                dest.value = original
            material = bpy.data.materials.new(name + '__OWN_UNTEXTURED')
            material.diffuse_color = ((0.8, 0.72, 0.62, 1) if 'teeth' in role else (0.25, 0.035, 0.045, 1))
            material.use_nodes = True
            for node in material.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    node.inputs['Base Color'].default_value = material.diffuse_color
                    node.inputs['Roughness'].default_value = 0.8
            material['internal_only'] = True
            material['source_texture_copied'] = False
            mesh.materials.append(material)
            for dest, original in zip(mesh.polygons, face_ids):
                dest.use_smooth = source.data.polygons[original].use_smooth
            key_map = {}
            for original in source.data.shape_keys.key_blocks:
                key = obj.shape_key_add(name=original.name, from_mix=False)
                for dest, vi in zip(key.data, ids):
                    dest.co = original.data[vi].co
                key.interpolation = original.interpolation
                key.slider_min = original.slider_min
                key.slider_max = original.slider_max
                key.value = 0.0
                key.mute = original.mute
                key.vertex_group = original.vertex_group
                key_map[original.name] = key
            for original in source.data.shape_keys.key_blocks:
                key_map[original.name].relative_key = key_map[original.relative_key.name]
            for group in source.vertex_groups:
                target_group = obj.vertex_groups.new(name=group.name)
                target_group.lock_weight = group.lock_weight
                for dest, vi in enumerate(ids):
                    for membership in source.data.vertices[vi].groups:
                        if membership.group == group.index:
                            target_group.add([dest], membership.weight, 'REPLACE')
            labels = _compatible_labels(source, ids)
            source_faces = [list(source.data.polygons[fi].vertices) for fi in face_ids]
            topology = _edge_report(source_faces, labels)
            if topology['boundary_edges'] != row['boundary_edges']:
                raise RuntimeError('Deformation-compatible boundary count differs from observed source for ' + role)
            coordinate_error = max((mesh.vertices[j].co - source.data.vertices[i].co).length for j, i in enumerate(ids))
            shape_error = max((key_map[key.name].data[j].co - key.data[i].co).length
                              for key in source.data.shape_keys.key_blocks for j, i in enumerate(ids))
            if coordinate_error != 0 or shape_error != 0:
                raise RuntimeError('Extraction changed source coordinates or stored shape ancestry')
            if len(mesh.uv_layers) or any(node.type == 'TEX_IMAGE' and node.image
                                         for mat in mesh.materials if mat.node_tree
                                         for node in mat.node_tree.nodes):
                raise RuntimeError('Unexpected source texture dependency')
            report['parts'].append({'object': obj.name, 'role': role, 'vertices': len(ids), 'faces': len(faces),
                                    'source_vertex_ids': ids, 'source_face_ids': face_ids,
                                    'source_shape_names': list(key_map), 'shape_count': len(key_map),
                                    'maximum_source_coordinate_error': coordinate_error,
                                    'maximum_source_shape_error': shape_error,
                                    'raw_topology': _edge_report(faces), 'deformation_compatible_topology': topology,
                                    'source_mean_world_xyz': center(row), 'classification_evidence': response,
                                    'status': 'OPEN_NOT_ACCEPTED', 'source_textures_copied': False})
        after = _hash_source(source)
        if before != after or source_objects != tuple(sorted(o.name for o in source_scene.objects)):
            raise RuntimeError('Original reference scene/source changed during extraction')
        if active_scene is not None and bpy.context.window.scene != active_scene:
            raise RuntimeError('Active operator scene unexpectedly changed')
        report['source_before_sha256'] = before
        report['source_after_sha256'] = after
        report['active_scene_preserved'] = True
        report_file.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    except Exception:
        # Remove only newly created staging objects. Never remove source objects.
        for obj in created:
            mesh = obj.data
            own_materials = list(mesh.materials)
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
            for material in own_materials:
                if material.users == 0:
                    bpy.data.materials.remove(material)
        bpy.data.collections.remove(staging)
        raise
    compact = {'status': report['status'], 'parts': [{'role': r['role'], 'vertices': r['vertices'],
               'faces': r['faces'], 'boundary_edges': r['deformation_compatible_topology']['boundary_edges'],
               'shape_count': r['shape_count']} for r in report['parts']],
               'source_unchanged': before == after, 'active_scene_preserved': True,
               'source_images_copied': 0, 'exports_created': 0,
               'report_private_filename': report_file.name}
    print(json.dumps(compact))
    return compact


if __name__ == '__main__':
    extract()

