# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Configuration checks independent of Blender."""
import hashlib
import json
import math
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    if config.get('schema_version') != 1:
        raise ValueError('Unsupported profile schema')
    for name in ('body_prefix', 'hair_prefix', 'head_bone'):
        if not isinstance(config.get(name), str) or not config[name]:
            raise ValueError('Missing selector: ' + name)
    if {e['label'] for e in config['eyes']} != {'left', 'right'} or len(config['eyes']) != 2:
        raise ValueError('Exactly one left and one right eye are required')
    for eye in config['eyes']:
        if eye['sphere_radius'] <= 0 or len(eye['rim_xyz']) < 3:
            raise ValueError('Invalid eye fit')
    if not 0 < config['jaw_max_degrees'] <= 8:
        raise ValueError('Supported jaw range is greater than 0 and at most 8 degrees')
    if not 0 < config['lid_close_fraction'] < 1:
        raise ValueError('lid_close_fraction must be between 0 and 1')
    for field, low, high in [('eye_texture_size', 16, 1024), ('eye_latitudes', 4, 128),
                             ('eye_longitudes', 8, 256), ('oral_rim_samples', 8, 512), ('oral_rings', 3, 64)]:
        if not isinstance(config[field], int) or not low <= config[field] <= high:
            raise ValueError('Out of range: ' + field)
    def finite(value):
        if isinstance(value, dict):
            return all(finite(x) for x in value.values())
        if isinstance(value, list):
            return all(finite(x) for x in value)
        return not isinstance(value, (int, float)) or math.isfinite(value)
    if not finite(config):
        raise ValueError('Profile contains non-finite numbers')
    return config


def validate_input(path, config):
    actual = sha256(path)
    expected = config.get('source_sha256')
    if expected and actual != expected:
        raise ValueError('Input does not match this fitted profile; supply a profile fitted to this input')
    return actual
