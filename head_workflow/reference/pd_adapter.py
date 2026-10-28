# SPDX-License-Identifier: GPL-3.0-or-later
"""Read private PD packs in memory. Does not create Blender objects or materials."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
from .geometry import (boundary_loops, split_lids, frame_for, normalize,
                       sample_path, encode_curve, statistics,
                       anchor_frames, encode_piecewise)

BLINK_WEIGHTS = (0., .25, .5, .75, 1.)


class PDReference:
    def __init__(self, addon_dir, pack_dir):
        addon_dir, self.pack_dir = Path(addon_dir).resolve(), Path(pack_dir).resolve()
        addon_hash = hashlib.sha256()
        for source in sorted(addon_dir.rglob('*.py')):
            addon_hash.update(source.relative_to(addon_dir).as_posix().encode())
            addon_hash.update(source.read_bytes())
        self.addon_sha256 = addon_hash.hexdigest()
        if not (self.pack_dir / 'manifest.json').exists():
            candidates = list(self.pack_dir.glob('*/manifest.json'))
            if len(candidates) != 1:
                raise ValueError('expected one pack manifest')
            self.pack_dir = candidates[0].parent
        name = 'parametric_deformation'
        if name in sys.modules:
            if Path(sys.modules[name].__file__).resolve() != addon_dir / '__init__.py':
                raise ValueError('a different Parametric Deformation version is already imported')
        else:
            spec = importlib.util.spec_from_file_location(name, addon_dir / '__init__.py',
                                                        submodule_search_locations=[str(addon_dir)])
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        from parametric_deformation.core.config import load_pack
        self.pack = load_pack(str(self.pack_dir))
        spec = importlib.util.spec_from_file_location('_head_reference_pd_driver', self.pack_dir / 'py/driver.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.adapter = module.VRoidAdapter()
        self.adapter.load(self.pack, str(self.pack_dir))
        names = json.loads((self.pack_dir / 'data/expression_names.json').read_text())
        matches = [i for i, n in enumerate(names) if n.endswith('.Eye.Joy')]
        if len(matches) != 1:
            raise ValueError('expected one bilateral Eye.Joy closure expression')
        self.blink_id = f'expr_{matches[0]:03d}'
        self.blink_label = names[matches[0]]
        self.desc = next(d for d in self.pack.mesh_descriptors if d['name'] == 'face')
        self.fingerprint = hashlib.sha256()
        # Bind the evidence to private geometry/deformation inputs, without publishing them.
        files = [self.pack_dir / 'manifest.json', self.pack_dir / 'params.json',
                 self.pack_dir / 'meshes/face.mesh.json', self.pack_dir / 'py/driver.py']
        files += sorted((self.pack_dir / 'data').glob('*'))
        files += sorted((self.pack_dir / 'lbs').glob('*'))
        for f in files:
            if f.is_file():
                self.fingerprint.update(f.relative_to(self.pack_dir).as_posix().encode())
                self.fingerprint.update(f.read_bytes())

    def evaluate(self, params, blink):
        if any(k.startswith('expr_') for k in params):
            raise ValueError('identity parameters cannot include expressions')
        allowed = {p['id']: p for p in self.pack.params}
        for key, value in params.items():
            if key not in allowed or not np.isfinite(value) or not allowed[key]['min'] <= value <= allowed[key]['max']:
                raise ValueError(f'invalid PD parameter: {key}')
        result = self.adapter.evaluate({**params, self.blink_id: blink}, {})
        mesh = next(m for m in result.meshes if m[0] == 'face')
        return np.asarray(mesh[1], dtype=float), np.asarray(mesh[2], dtype=int)

    def extract(self, params=None):
        params = dict(params or {})
        neutral, faces = self.evaluate(params, 0.)
        evaluated = [neutral] + [self.evaluate(params, w)[0] for w in BLINK_WEIGHTS[1:]]

        def region(suffix):
            slots = [s for s in self.desc['slots'] if suffix in s['material']]
            if len(slots) != 1:
                raise ValueError(f'ambiguous region {suffix}')
            s = slots[0]
            return faces[s['tri_start']:s['tri_start'] + s['tri_count']]

        skin_faces, white_faces, lash_faces = region('Face_00_SKIN'), region('EyeWhite'), region(getattr(self, 'lash_region', 'FaceEyelash'))
        skin_loops = boundary_loops(skin_faces)
        white_loops = boundary_loops(white_faces)
        lash_loops = boundary_loops(lash_faces)
        eyes = {}
        for label, side in [('positive_x', 1), ('negative_x', -1)]:
            whites = [c for c in white_loops if np.all(side * neutral[c, 0] > 0)]
            lashes = [c for c in lash_loops if np.all(side * neutral[c, 0] > 0)]
            if len(whites) != 1 or len(lashes) != 1:
                raise ValueError('ambiguous eye or lash boundary')
            white, lash = whites[0], lashes[0]
            loop = min(skin_loops, key=lambda c: np.linalg.norm(neutral[c].mean(0) - neutral[white].mean(0)))
            # Verify matching geometric boundary rather than relying on vertex IDs.
            match = np.linalg.norm(neutral[loop, None, :] - neutral[white][None, :, :], axis=2).min(1)
            if match.max() > 1e-5:
                raise ValueError('skin/sclera aperture boundaries do not coincide')
            upper, lower = split_lids(neutral, loop, side)
            lash_upper, lash_lower = split_lids(neutral, lash, side)
            frame = frame_for(neutral, upper)
            margins, lash_samples = [], []
            for vertices in evaluated:
                row = {}
                for key, path in [('upper', upper), ('lower', lower)]:
                    pts = sample_path(normalize(vertices[path], frame), normalize(neutral[path], frame))
                    row[key] = encode_curve(pts)
                # Pair the two sheet boundaries by neutral arclength. Unlike
                # lateral slicing this remains continuous at folded sheet tips.
                lash_a, lash_b = [sample_path(normalize(vertices[path], frame),
                                              normalize(neutral[path], frame))
                                  for path in (lash_upper, lash_lower)]
                center = (lash_a + lash_b) / 2
                width_stats = statistics(np.linalg.norm(lash_a - lash_b, axis=1))
                center_curve = encode_piecewise(center)
                # The same inner-to-outer arclength parameter anchors the band
                # throughout the blink. No nearest-point switching between poses.
                anchor_u = np.linspace(0, 1, len(center))
                origins, axes = anchor_frames(row['upper'], anchor_u)
                local = np.einsum('nij,nj->ni', axes, center - origins)
                lash_samples.append({'centreline': center_curve, 'anchor_offsets': encode_piecewise(local),
                                     'sheet_width': width_stats})
                margins.append(row)
            # The pack has an open skin sheet: no paired back surface to measure gauge.
            rim_set = set(map(int, loop))
            adjacent = {(int(a), int(b)) for tri in skin_faces for a in tri for b in tri
                        if int(a) in rim_set and int(b) not in rim_set}
            collar_steps = [np.linalg.norm(neutral[a] - neutral[b])/frame[2] for a, b in adjacent]
            recess = [(normalize(neutral[[b]], frame)[0, 2] - normalize(neutral[[a]], frame)[0, 2]) for a, b in adjacent]
            eyes[label] = {
                'aperture': margins[0], 'lid_margin': margins,
                'lash_band': {'samples': lash_samples,
                              'anchor_u': np.round(anchor_u, 7).tolist(),
                              'frame_rule': 'upper-margin tangent; projected +depth normal; binormal = normal cross tangent'},
                'socket_depth': {'method': 'adjacent skin minus aperture depth, signed collar recess proxy',
                                 'statistics': statistics(recess), 'anatomical_socket_depth': None},
                'lid_thickness': {'method': 'open skin sheet; no paired inner surface',
                                  'physical_thickness': None,
                                  'collar_edge_length_proxy': statistics(collar_steps)},
            }
        return {'schema_version': 1, 'units': 'neutral canthus distance = 1',
                'axes': ['inner_to_outer', 'orthogonal_up', 'outward_depth'],
                'normalization': 'neutral canthus midpoint; frame held fixed across blink; eye sides canonicalized',
                'blink_weights': list(BLINK_WEIGHTS),
                'provenance': self.provenance(params), 'eyes': eyes}

    def provenance(self, params):
        return {'pack': self.pack.manifest['id'], 'pack_version': self.pack.manifest['version'],
                               'private_input_sha256': self.fingerprint.hexdigest(),
                               'addon_code_sha256': self.addon_sha256,
                               'expression': self.blink_label,
                               'expression_note': 'Eye.Joy is the available closure surrogate, not a separately captured physiological blink',
                               'identity_parameters': params,
                               'evaluation': 'Parametric Deformation VRoidAdapter.evaluate'}
