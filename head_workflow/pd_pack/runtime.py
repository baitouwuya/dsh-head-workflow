# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable NumPy evaluator copied into each private generated PD pack.

Coordinates and rest matrices stay in glTF space until the final +Y-up to
Blender +Z-up conversion. This module does not export any file or VRM.
"""
import json
from pathlib import Path
import numpy as np

AXIS = np.array([[1., 0., 0.], [0., 0., -1.], [0., 1., 0.]])
PROCEDURAL = {
    'overrideBlink': {'blink', 'blinkLeft', 'blinkRight'},
    'overrideMouth': {'aa', 'ih', 'ou', 'ee', 'oh'},
    'overrideLookAt': {'lookUp', 'lookDown', 'lookLeft', 'lookRight'},
}


def expression_values(expressions, params):
    values = {}
    for pid, exp in expressions.items():
        v = float(params.get(pid, 0.))
        if not np.isfinite(v):
            raise ValueError('nonfinite expression value')
        v = float(np.clip(v, 0., 1.))
        values[pid] = float(v > .5) if exp.get('isBinary') else v
    result = dict(values)
    for override, names in PROCEDURAL.items():
        attenuation = 0.
        for pid, exp in expressions.items():
            if exp.get('preset') in names:
                continue  # A procedural expression cannot override its own group.
            v = values[pid]
            mode = exp.get(override, 'none')
            if v > 0 and mode == 'block':
                attenuation = 1.
            elif mode == 'blend':
                attenuation += v
        factor = max(0., 1. - attenuation)
        for pid, exp in expressions.items():
            if exp.get('preset') in names:
                result[pid] = (0. if factor < 1. else values[pid]) if exp.get('isBinary') else values[pid] * factor
    return result


def rotation_vector(vector):
    angle = np.linalg.norm(vector)
    if angle < 1e-12:
        return np.eye(3)
    x, y, z = vector / angle
    skew = np.array([[0., -z, y], [z, 0., -x], [-y, x, 0.]])
    return np.eye(3) + np.sin(angle) * skew + (1 - np.cos(angle)) * (skew @ skew)


class Runtime:
    def __init__(self, directory):
        self.root = Path(directory).resolve()
        self.skeleton = self.read('lbs/skeleton.json')
        self.parents = self.skeleton['parent_indices']
        self.names = [j['id'] for j in self.skeleton['joints']]
        self.local = self.array(self.skeleton['local_matrices']).astype(float)
        self.params = {p['id']: p for p in self.read('params.json')}
        self.mapping = self.read('export_map.json')
        self.expressions = self.mapping['expressions']
        self.meshes = []
        for path in sorted((self.root / 'meshes').glob('*.mesh.json')):
            d = json.loads(path.read_text(encoding='utf8'))
            item = {'desc': d}
            for key in ('vertices', 'faces', 'uv', 'bones', 'indices', 'weights', 'bindposes', 'morphs'):
                if key in d:
                    item[key] = self.array(d[key])
            self.meshes.append(item)

    def read(self, path):
        return json.loads((self.root / path).read_text(encoding='utf8'))

    def array(self, ref):
        path = (self.root / (ref['file'] if isinstance(ref, dict) else ref)).resolve()
        if self.root not in path.parents:
            raise ValueError('array outside pack')
        return np.load(path, allow_pickle=False)

    def evaluate(self, params=None, pose=None):
        params, pose = dict(params or {}), dict(pose or {})
        unknown = set(params) - set(self.params)
        if unknown:
            raise ValueError(f'unknown controls: {sorted(unknown)}')
        values = {k: float(params.get(k, p.get('default', 0.))) for k, p in self.params.items()}
        if not np.isfinite(list(values.values())).all():
            raise ValueError('nonfinite control')
        for k, value in values.items():
            if k not in self.expressions and not self.params[k]['min'] <= value <= self.params[k]['max']:
                raise ValueError(f'control outside range: {k}')
        expr = expression_values(self.expressions, values)
        for pid, weight in expr.items():
            for bind in self.expressions[pid]['binds']:
                values[bind['param']] += weight * bind['weight']
        rotations = np.asarray(pose.get('rotations', np.zeros((len(self.parents), 3))), dtype=float)
        translation = np.asarray(pose.get('translation', np.zeros(3)), dtype=float)
        if rotations.shape != (len(self.parents), 3) or translation.shape != (3,) or not np.isfinite(rotations).all() or not np.isfinite(translation).all():
            raise ValueError('invalid pose arrays')
        world = np.empty_like(self.local)
        for i, parent in enumerate(self.parents):
            r = np.eye(4); r[:3, :3] = rotation_vector(rotations[i])
            local = self.local[i] @ r
            world[i] = local if parent < 0 else world[parent] @ local
        world[:, :3, 3] += translation
        output = []
        for item in self.meshes:
            d = item['desc']
            p = np.asarray(item['vertices'], dtype=float).copy()
            if 'morphs' in item:
                w = np.array([values[k] for k in d['morph_params']])
                p += np.einsum('k,kvc->vc', w, item['morphs'])
            hom = np.column_stack([p, np.ones(len(p))])
            if 'weights' in item:
                palette = world[item['bones']] @ item['bindposes']
                skinned = np.zeros((len(p), 4))
                for k in range(item['weights'].shape[1]):
                    skinned += item['weights'][:, k, None] * np.einsum('vij,vj->vi', palette[item['indices'][:, k]], hom)
                p = skinned[:, :3]
            else:
                p = (hom @ world[d['node_index']].T)[:, :3]
            output.append((d['name'], (p @ AXIS.T).astype(np.float32), item['faces'], item.get('uv')))
        return {'meshes': output, 'joints': world[:, :3, 3] @ AXIS.T,
                'extra': {'world': world, 'joints': self.names, 'parents': self.parents}}
