# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import copy
import json
import tempfile
import unittest
from pathlib import Path
from head_workflow.config import load, validate_input

PROFILE = Path(__file__).resolve().parents[1] / 'profiles' / 'original-character.json'


class ConfigurationTests(unittest.TestCase):
    def modified_profile(self, change):
        config = json.loads(PROFILE.read_text())
        change(config)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'profile.json'
            path.write_text(json.dumps(config))
            return load(path)

    def test_supported_profile(self):
        config = load(PROFILE)
        self.assertEqual(len(config['eyes']), 2)
        self.assertEqual(len(config['original_controls']), 7)
        self.assertEqual(len(config['stitches']), 2)

    def test_rejects_duplicate_eye_side(self):
        with self.assertRaises(ValueError):
            self.modified_profile(lambda c: c['eyes'][1].update(label=c['eyes'][0]['label']))

    def test_rejects_unsupported_jaw(self):
        with self.assertRaises(ValueError):
            self.modified_profile(lambda c: c.update(jaw_max_degrees=40))

    def test_rejects_nonfinite_geometry(self):
        with self.assertRaises(ValueError):
            self.modified_profile(lambda c: c['eyes'][0].update(sphere_radius=float('nan')))

    def test_rejects_excessive_resolution(self):
        with self.assertRaises(ValueError):
            self.modified_profile(lambda c: c.update(eye_texture_size=32768))

    def test_profile_cannot_silently_target_different_model(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'wrong.glb'
            path.write_bytes(b'not the fitted model')
            with self.assertRaises(ValueError):
                validate_input(path, load(PROFILE))


if __name__ == '__main__':
    unittest.main()
