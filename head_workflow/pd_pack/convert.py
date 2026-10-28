# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert private VRM/embedded GLB geometry to a PD format_version=1 pack.

No textures/materials, identity sliders, dynamics or VRM exporter are generated.
One descriptor per active mesh-node primitive avoids assuming shared accessors.
"""
import json
from pathlib import Path
import re
import numpy as np
from .gltf import GLB


def local_matrix(node):
    if 'matrix' in node:
        if any(k in node for k in ('translation', 'rotation', 'scale')):
            raise ValueError('node has both matrix and TRS')
        matrix = np.asarray(node['matrix'], dtype=float).reshape(4, 4).T
    else:
        q = np.asarray(node.get('rotation', [0, 0, 0, 1]), dtype=float)
        if q.shape != (4,) or abs(np.linalg.norm(q) - 1) > 1e-4:
            raise ValueError('invalid node quaternion')
        x, y, z, w = q
        r = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                      [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                      [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
        matrix = np.eye(4)
        matrix[:3, :3] = r @ np.diag(node.get('scale', [1, 1, 1]))
        matrix[:3, 3] = node.get('translation', [0, 0, 0])
    if not np.isfinite(matrix).all() or not np.allclose(matrix[3], [0, 0, 0, 1]):
        raise ValueError('invalid affine node matrix')
    return matrix


def graph(g):
    nodes = g.get('nodes', [])
    if not nodes:
        raise ValueError('nodes required')
    parents = [-1] * len(nodes)
    for i, n in enumerate(nodes):
        for c in n.get('children', []):
            if not isinstance(c, int) or not 0 <= c < len(nodes) or parents[c] != -1:
                raise ValueError('invalid or multiply-parented node')
            parents[c] = i
    order, visiting, done = [], set(), set()
    def visit(i):
        if i in visiting:
            raise ValueError('node cycle')
        if i in done:
            return
        visiting.add(i)
        if parents[i] >= 0:
            visit(parents[i])
        visiting.remove(i); done.add(i); order.append(i)
    for i in range(len(nodes)):
        visit(i)
    index = {n: i for i, n in enumerate(order)}
    local = np.array([local_matrix(nodes[n]) for n in order])
    parent_indices = [index[parents[n]] if parents[n] >= 0 else -1 for n in order]
    world = np.empty_like(local)
    for i, p in enumerate(parent_indices):
        world[i] = local[i] if p < 0 else world[p] @ local[i]
    roots = g['scenes'][g.get('scene', 0)]['nodes'] if g.get('scenes') else [i for i, p in enumerate(parents) if p < 0]
    active = set()
    def descend(i):
        if i in active:
            return
        active.add(i)
        for c in nodes[i].get('children', []):
            descend(c)
    for r in roots:
        descend(r)
    names, used = [], set()
    for n in order:
        name = nodes[n].get('name') or f'node_{n}'
        if name in used:
            name += f'__node_{n}'
        used.add(name); names.append(name)
    return order, index, parent_indices, names, local, world, active


def convert(source, output, *, runtime_source=None, driver_source=None):
    output = Path(output)
    if output.exists():
        raise FileExistsError('output pack must be a fresh directory')
    reader = GLB(Path(source).read_bytes()); g = reader.g
    if any('EXT_meshopt_compression' in v.get('extensions', {}) for v in g.get('bufferViews', [])):
        raise ValueError('compressed buffer views require an external decoder')
    order, index, parents, names, local, world, active = graph(g)
    arrays, documents, descriptors, params, raw_ids = {}, {}, [], {}, {}
    losses = {'materials/textures/images omitted', 'normal/tangent streams recomputed by Blender',
              'animations, spring bones, constraints, look-at and first-person behavior not executed',
              'no source-authoring identity sliders or correctives can be recovered', 'no VRM exporter generated'}

    def arr(name, value):
        path = 'data/' + name + '.npy'
        arrays[path] = np.asarray(value)
        return {'file': path}

    for ni in sorted(active):
        node = g['nodes'][ni]
        if 'mesh' not in node:
            continue
        mesh = g['meshes'][node['mesh']]
        counts = {len(p.get('targets', [])) for p in mesh['primitives']}
        if len(counts) != 1:
            raise ValueError('morph count must agree across a mesh node primitives')
        count = counts.pop()
        defaults = node.get('weights', mesh.get('weights', [0.] * count))
        if len(defaults) != count or not np.isfinite(defaults).all():
            raise ValueError('invalid default morph weights')
        labels = mesh.get('extras', {}).get('targetNames', [])
        for k in range(count):
            pid = f'morph_n{ni}_{k:03d}'; raw_ids[ni, k] = pid
            params[pid] = {'id': pid, 'label': labels[k] if k < len(labels) else pid,
                           'group': 'Morph Targets', 'kind': 'linear', 'default': float(defaults[k]),
                           'min': min(-1., float(defaults[k])), 'max': max(1., float(defaults[k])), 'step': .01}
        for pi, primitive in enumerate(mesh['primitives']):
            if primitive.get('mode', 4) != 4 or primitive.get('extensions', {}).get('KHR_draco_mesh_compression'):
                raise ValueError('only uncompressed triangle primitives supported')
            attributes = primitive['attributes']
            if any(k.startswith(('JOINTS_', 'WEIGHTS_')) and k not in ('JOINTS_0', 'WEIGHTS_0') for k in attributes):
                raise ValueError('more than four influences cannot be preserved by this PD viewport')
            p = reader.accessor(attributes['POSITION'])
            if p.shape[1] != 3 or g['accessors'][attributes['POSITION']]['componentType'] != 5126:
                raise ValueError('float VEC3 positions required')
            ix = reader.accessor(primitive['indices']).ravel() if 'indices' in primitive else np.arange(len(p))
            if ix.dtype.kind not in 'ui' or len(ix) % 3 or np.any(ix >= len(p)):
                raise ValueError('invalid triangle indices')
            selected, remap = np.unique(ix, return_inverse=True)
            name = f'node_{ni:04d}_primitive_{pi:03d}'
            d = {'name': name, 'target_mesh': name, 'source_node': ni, 'source_mesh': node['mesh'],
                 'source_primitive': pi, 'node_index': index[ni],
                 'source_vertex_indices': arr(name+'_source_indices', selected),
                 'vertices': arr(name+'_vertices', p[selected]),
                 'faces': arr(name+'_faces', remap.reshape(-1, 3).astype(np.int32))}
            if 'TEXCOORD_0' in attributes:
                uv = reader.accessor(attributes['TEXCOORD_0'])
                if uv.shape != (len(p), 2):
                    raise ValueError('invalid UV stream')
                d['uv'] = arr(name+'_uv', uv[selected])
            if count:
                basis = []
                for target in primitive['targets']:
                    delta = reader.accessor(target['POSITION']) if 'POSITION' in target else np.zeros_like(p)
                    if delta.shape != p.shape:
                        raise ValueError('morph/position stream mismatch')
                    basis.append(delta[selected])
                d['morphs'] = arr(name+'_morphs', np.array(basis, dtype=np.float32))
                d['morph_params'] = [raw_ids[ni, k] for k in range(count)]
                documents['bs/linear/'+name+'.bs.json'] = {'id': name+'_morphs', 'type': 'linear',
                    'target_mesh': name, 'data': d['morphs'], 'params': d['morph_params']}
            if 'skin' in node:
                skin = g['skins'][node['skin']]
                palette = skin['joints']
                ji = reader.accessor(attributes['JOINTS_0'])
                weights = reader.accessor(attributes['WEIGHTS_0']).astype(float)
                if ji.shape != (len(p), 4) or ji.dtype.kind not in 'ui' or np.any(ji >= len(palette)) or weights.shape != ji.shape or np.any(weights < 0):
                    raise ValueError('invalid four-influence skin data')
                totals = weights.sum(axis=1)
                if np.any(abs(totals - 1) > 1e-4):
                    raise ValueError('skin weights must sum to one; no silent repair')
                weights /= totals[:, None]
                ibm = reader.accessor(skin['inverseBindMatrices']).reshape(-1, 4, 4).transpose(0, 2, 1) if 'inverseBindMatrices' in skin else np.tile(np.eye(4), (len(palette), 1, 1))
                if ibm.shape != (len(palette), 4, 4) or not np.allclose(ibm[:,3,:], [0,0,0,1]):
                    raise ValueError('inverse bind matrix count mismatch')
                d.update(bones=arr(name+'_bones', [index[n] for n in palette]),
                         indices=arr(name+'_indices', ji[selected].astype(np.int32)),
                         weights=arr(name+'_weights', weights[selected].astype(np.float32)),
                         bindposes=arr(name+'_bindposes', ibm.astype(np.float64)))
            descriptors.append(d)
            documents['meshes/'+name+'.mesh.json'] = d
    if not descriptors:
        raise ValueError('no active triangle meshes')
    expressions, humanoid = {}, {}
    vrm1 = g.get('extensions', {}).get('VRMC_vrm')
    vrm0 = g.get('extensions', {}).get('VRM')
    entries = []
    if vrm1:
        for group in ('preset', 'custom'):
            for name, exp in vrm1.get('expressions', {}).get(group, {}).items():
                entries.append((group, name, exp, exp.get('morphTargetBinds', [])))
        humanoid = {role: names[index[entry['node']]] for role, entry in vrm1.get('humanoid', {}).get('humanBones', {}).items()}
    elif vrm0:
        aliases = {'a': 'aa', 'i': 'ih', 'u': 'ou', 'e': 'ee', 'o': 'oh', 'blink_l': 'blinkLeft', 'blink_r': 'blinkRight'}
        for exp in vrm0.get('blendShapeMaster', {}).get('blendShapeGroups', []):
            preset = exp.get('presetName', 'unknown'); group = 'custom' if preset == 'unknown' else 'preset'
            name = exp.get('name', 'custom') if group == 'custom' else aliases.get(preset, preset)
            binds = [dict(node=ni, index=b['index'], weight=b['weight']/100.) for b in exp.get('binds', [])
                     for ni in active if g['nodes'][ni].get('mesh') == b['mesh']]
            entries.append((group, name, exp, binds))
        humanoid = {h['bone']: names[index[h['node']]] for h in vrm0.get('humanoid', {}).get('humanBones', [])}
    for group, name, exp, binds in entries:
        if exp.get('materialColorBinds') or exp.get('textureTransformBinds') or exp.get('materialValues'):
            raise ValueError('material-changing expression cannot be represented by this geometry-only converter')
        pid = 'vrm_' + ('' if group == 'preset' else 'custom_') + re.sub(r'[^a-zA-Z0-9_]', '_', name)
        if pid in expressions:
            raise ValueError('expression identifier collision')
        mapped = []
        for b in binds:
            key = (b['node'], b['index']); weight = float(b['weight'])
            if key not in raw_ids or not np.isfinite(weight) or not 0 <= weight <= 1:
                raise ValueError('expression bind references missing node/morph or invalid weight')
            mapped.append({'param': raw_ids[key], 'weight': weight, 'source_node': key[0], 'target_index': key[1]})
        entry = {'name': name, 'preset': name if group == 'preset' else None,
                 'isBinary': bool(exp.get('isBinary', False)), 'binds': mapped}
        for override in ('overrideBlink', 'overrideMouth', 'overrideLookAt'):
            mode = exp.get(override, 'none')
            if mode not in ('none', 'blend', 'block'):
                raise ValueError('invalid expression override')
            entry[override] = mode
        expressions[pid] = entry
        params[pid] = {'id': pid, 'label': name, 'group': 'VRM Expressions', 'kind': 'semantic',
                       'min': 0., 'max': 1., 'default': 0., 'step': .01}
    documents['manifest.json'] = {'format_version': '1', 'id': 'converted_vrm_'+reader.sha256[:12],
        'name': 'Converted private VRM geometry/morph pack', 'version': '1.0.0', 'dependencies': ['numpy'],
        'source_sha256': reader.sha256, 'limitations': sorted(losses), 'source_arrays_are_private': True}
    documents['params.json'] = list(params.values())
    documents['lbs/skeleton.json'] = {'joints': [{'id': name, 'parent': max(0, p), 'source_node': order[i]}
        for i, (name, p) in enumerate(zip(names, parents))], 'parent_indices': parents,
        'local_matrices': arr('node_local_matrices', local), 'positions': arr('joint_positions', world[:, :3, 3])}
    documents['export_map.json'] = {'expressions': expressions, 'humanoid_bones': humanoid,
        'note': 'Semantic mapping metadata only. PD export/__init__.py is an empty interface stub; it cannot emit VRM.'}
    output.mkdir(parents=True)
    for path, value in documents.items():
        dest = output/path; dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf8')
    for path, value in arrays.items():
        dest = output/path; dest.parent.mkdir(parents=True, exist_ok=True); np.save(dest, value, allow_pickle=False)
    (output/'py').mkdir()
    for name, text in [('runtime', runtime_source), ('driver', driver_source)]:
        (output/'py'/f'{name}.py').write_text(text if text is not None else Path(__file__).with_name(name+'.py').read_text(), encoding='utf8')
    (output/'py/__init__.py').write_text('', encoding='utf8')
    (output/'.gitignore').write_text('*\n', encoding='utf8')
    return {'source_sha256': reader.sha256, 'descriptors': len(descriptors), 'skeleton_nodes': len(names),
            'raw_morph_controls': len(raw_ids), 'expression_controls': len(expressions),
            'humanoid_roles': len(humanoid), 'limitations': sorted(losses)}
