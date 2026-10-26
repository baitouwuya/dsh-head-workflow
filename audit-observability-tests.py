# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Independent missing-evidence regression fixtures; no Blender or host build.

These fixtures distinguish a fully observed zero from missing observations. They
exercise aggregation only and never change acceptance rules or numerical limits.
"""
import copy
import ast
import collections
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from head_repair.audit import aggregate_geometry, aggregate_semantic


PROFILE = {
    'character': {'eyes': [{'label': 'left'}, {'label': 'right'}]},
    'sampling': {
        'jaw_degrees': [0, 15], 'blink_weights': [0, 1],
        'mouth_views': [0, 45], 'eye_grid': [5, 5], 'mouth_grid': [5, 5],
    },
}
GEOMETRY_METRICS = (
    'projected_flips', 'quad_normal_max_degrees',
    'adjacent_triangle_max_degrees',
)
SEMANTIC_METRICS = (
    'eye_exposed_or_empty', 'mouth_empty_or_posterior',
    'mouth_unwanted_occluders',
)


def geometry_rows():
    return [
        {'pose': pose, 'projected_flips': 0,
         'quad_normal_max_degrees': 0.0,
         'adjacent_triangle_max_degrees': 0.0,
         'quad_normal_observations': 4,
         'projected_triangle_observations': 8,
         'adjacent_triangle_observations': 6}
        for pose in ('jaw_0', 'jaw_15', 'blink_0', 'blink_1')
    ]


def semantic_report():
    return {
        'eyes': [
            {'side': side, 'rays': 9, 'exposed_or_empty': 0}
            for side in ('left', 'right')
        ],
        'mouth': [
            {'degrees': degrees, 'view_degrees': view, 'rays': 9,
             'empty_or_posterior_hits': 0, 'unwanted_corridor_occluders': 0}
            for degrees in (0, 15) for view in (0, 45)
        ],
    }


def raw_geometry(vertices, faces, triangles):
    """Run the unmodified real function with only Blender access stubbed.

    This checks NumPy geometry behavior, not Blender evaluation or export. No
    replacement measurement algorithm or numerical tolerance lives in this test.
    """
    ns = SimpleNamespace
    data = ns(vertices=[ns(co=tuple(v)) for v in vertices],
              polygons=[ns(index=i, vertices=tuple(f), material_index=0)
                        for i, f in enumerate(faces)],
              materials=[ns(name='SEM_new_lip')],
              loop_triangles=[ns(vertices=tuple(v), polygon_index=i)
                              for i, v in triangles],
              attributes={}, calc_loop_triangles=lambda: None)
    body = ns(type='MESH', name='BodyFace', data=data, to_mesh=lambda: data,
              to_mesh_clear=lambda: None)
    body.evaluated_get = lambda _: body
    fake_bpy = ns(context=ns(scene=ns(objects=[body]),
                            evaluated_depsgraph_get=lambda: None))
    source = Path(__file__).resolve().parent / 'head_repair' / 'measure.py'
    parsed = ast.parse(source.read_text())
    function = next(n for n in parsed.body
                    if isinstance(n, ast.FunctionDef) and n.name == 'geometry')
    code = compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec')
    namespace = {'bpy': fake_bpy, 'np': np, 'math': math,
                 'collections': collections, 'apply': lambda *_: None}
    exec(code, namespace)
    profile = {'sampling': {'jaw_degrees': [0], 'blink_weights': []}}
    return namespace['geometry'](profile, {})[0]


class ObservabilityTests(unittest.TestCase):
    def assert_metrics(self, result, expected):
        self.assertIsInstance(result['coverage'], dict)
        self.assertTrue(result['coverage'], 'Coverage counts must be reported')
        for key, value in expected.items():
            self.assertIn(key, result['metrics'])
            self.assertEqual(result['metrics'][key], value, key)

    def test_raw_triangle_only_mesh_has_no_quad_measurement(self):
        row = raw_geometry([(0, 0, 0), (0, 1, 0), (0, 0, 1)],
                           [(0, 1, 2)], [(0, (0, 1, 2))])
        self.assertIsNone(row['quad_normal_max_degrees'])
        self.assertEqual(row['quad_normal_observations'], 0)
        self.assertEqual(row['projected_triangle_observations'], 1)
        self.assertIsNone(row['adjacent_triangle_max_degrees'])
        self.assertEqual(row['adjacent_triangle_observations'], 0)

    def test_raw_degenerate_quad_has_no_valid_normal_measurement(self):
        row = raw_geometry([(0, 0, 0), (0, 1, 0), (0, 2, 0), (0, 3, 0)],
                           [(0, 1, 2, 3)], [(0, (0, 1, 2)), (0, (0, 2, 3))])
        for key in GEOMETRY_METRICS:
            self.assertIsNone(row[key], key)
        for key in ('quad_normal_observations', 'projected_triangle_observations',
                    'adjacent_triangle_observations'):
            self.assertEqual(row[key], 0, key)

    def test_raw_valid_flat_quad_has_measured_zero_and_positive_counts(self):
        row = raw_geometry([(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)],
                           [(0, 1, 2, 3)], [(0, (0, 1, 2)), (0, (0, 2, 3))])
        for key in GEOMETRY_METRICS:
            self.assertEqual(row[key], 0, key)
        self.assertEqual(row['quad_normal_observations'], 1)
        self.assertEqual(row['projected_triangle_observations'], 2)
        self.assertEqual(row['adjacent_triangle_observations'], 1)

    def test_empty_geometry_is_missing(self):
        self.assert_metrics(aggregate_geometry(PROFILE, []),
                            dict.fromkeys(GEOMETRY_METRICS))

    def test_no_quads_is_missing_even_with_legacy_zero(self):
        rows = geometry_rows()
        for row in rows:
            row['quad_normal_observations'] = 0
        self.assert_metrics(aggregate_geometry(PROFILE, rows), {
            'quad_normal_max_degrees': None, 'projected_flips': 0,
            'adjacent_triangle_max_degrees': 0.0})

    def test_degenerate_quad_without_valid_normals_is_missing(self):
        rows = geometry_rows()
        rows[1].update(quad_normal_observations=0,
                       quad_normal_max_degrees=None)
        self.assert_metrics(aggregate_geometry(PROFILE, rows),
                            {'quad_normal_max_degrees': None})

    def test_valid_flat_quads_are_measured_zero(self):
        self.assert_metrics(aggregate_geometry(PROFILE, geometry_rows()),
                            dict.fromkeys(GEOMETRY_METRICS, 0))

    def test_valid_nonzero_geometry_remains_observed(self):
        rows = geometry_rows()
        rows[0].update(projected_flips=2, quad_normal_max_degrees=42.0,
                       adjacent_triangle_max_degrees=35.0)
        rows[1].update(projected_flips=3, quad_normal_max_degrees=30.0,
                       adjacent_triangle_max_degrees=45.0)
        self.assert_metrics(aggregate_geometry(PROFILE, rows), {
            'projected_flips': 5, 'quad_normal_max_degrees': 42.0,
            'adjacent_triangle_max_degrees': 45.0})

    def test_geometry_coverage_reports_counts_not_only_pass_flags(self):
        coverage = aggregate_geometry(PROFILE, geometry_rows())['coverage']
        expected = ['jaw_0', 'jaw_15', 'blink_0', 'blink_1']
        self.assertEqual(coverage['expected_poses'], expected)
        self.assertEqual(coverage['observed_poses'], expected)
        self.assertEqual(coverage['missing_poses'], [])
        self.assertEqual(coverage['duplicate_poses'], [])
        self.assertEqual(coverage['observations']['projected_flips'],
                         dict.fromkeys(expected, 8))
        self.assertEqual(coverage['observations']['quad_normal_max_degrees'],
                         dict.fromkeys(expected, 4))
        self.assertEqual(coverage['observations']['adjacent_triangle_max_degrees'],
                         dict.fromkeys(expected, 6))

    def test_geometry_missing_count_stays_explicit(self):
        rows = geometry_rows()
        del rows[0]['quad_normal_observations']
        result = aggregate_geometry(PROFILE, rows)
        self.assertIsNone(result['metrics']['quad_normal_max_degrees'])
        self.assertIsNone(result['coverage']['observations']
                          ['quad_normal_max_degrees']['jaw_0'])

    def test_missing_pose_invalidates_geometry_coverage(self):
        self.assert_metrics(aggregate_geometry(PROFILE, geometry_rows()[:-1]),
                            dict.fromkeys(GEOMETRY_METRICS))

    def test_duplicate_pose_does_not_replace_missing_pose(self):
        rows = geometry_rows()
        rows[-1] = copy.deepcopy(rows[0])
        self.assert_metrics(aggregate_geometry(PROFILE, rows),
                            dict.fromkeys(GEOMETRY_METRICS))

    def test_each_zero_observation_count_invalidates_its_probe(self):
        pairs = [('projected_triangle_observations', 'projected_flips'),
                 ('adjacent_triangle_observations', 'adjacent_triangle_max_degrees')]
        for count, metric in pairs:
            with self.subTest(metric=metric):
                rows = geometry_rows()
                rows[0][count] = 0
                self.assert_metrics(aggregate_geometry(PROFILE, rows), {metric: None})

    def test_missing_report_is_not_zero(self):
        for report in (None, {}):
            with self.subTest(report=report):
                self.assert_metrics(aggregate_semantic(PROFILE, report),
                                    dict.fromkeys(SEMANTIC_METRICS))

    def test_missing_eyes_does_not_invalidate_observed_mouth(self):
        report = semantic_report()
        report['eyes'] = []
        self.assert_metrics(aggregate_semantic(PROFILE, report), {
            'eye_exposed_or_empty': None, 'mouth_empty_or_posterior': 0,
            'mouth_unwanted_occluders': 0})

    def test_missing_one_eye_is_missing(self):
        report = semantic_report()
        report['eyes'].pop()
        self.assert_metrics(aggregate_semantic(PROFILE, report),
                            {'eye_exposed_or_empty': None})

    def test_zero_eye_rays_is_missing(self):
        report = semantic_report()
        report['eyes'][0]['rays'] = 0
        self.assert_metrics(aggregate_semantic(PROFILE, report),
                            {'eye_exposed_or_empty': None})

    def test_missing_mouth_row_is_missing(self):
        report = semantic_report()
        report['mouth'].pop()
        self.assert_metrics(aggregate_semantic(PROFILE, report), {
            'eye_exposed_or_empty': 0, 'mouth_empty_or_posterior': None,
            'mouth_unwanted_occluders': None})

    def test_zero_mouth_rays_is_missing(self):
        report = semantic_report()
        report['mouth'][0]['rays'] = 0
        self.assert_metrics(aggregate_semantic(PROFILE, report), {
            'mouth_empty_or_posterior': None, 'mouth_unwanted_occluders': None})

    def test_duplicate_mouth_row_does_not_replace_missing_view(self):
        report = semantic_report()
        report['mouth'][-1] = copy.deepcopy(report['mouth'][0])
        self.assert_metrics(aggregate_semantic(PROFILE, report), {
            'mouth_empty_or_posterior': None, 'mouth_unwanted_occluders': None})

    def test_fully_covered_zero_failures_is_zero(self):
        self.assert_metrics(aggregate_semantic(PROFILE, semantic_report()),
                            dict.fromkeys(SEMANTIC_METRICS, 0))

    def test_fully_covered_nonzero_failures_are_retained(self):
        report = semantic_report()
        report['eyes'][0]['exposed_or_empty'] = 2
        report['eyes'][1]['exposed_or_empty'] = 1
        report['mouth'][0]['empty_or_posterior_hits'] = 4
        report['mouth'][1]['unwanted_corridor_occluders'] = 3
        self.assert_metrics(aggregate_semantic(PROFILE, report), {
            'eye_exposed_or_empty': 3, 'mouth_empty_or_posterior': 4,
            'mouth_unwanted_occluders': 3})

    def test_semantic_coverage_reports_expected_probes_and_actual_rays(self):
        coverage = aggregate_semantic(PROFILE, semantic_report())['coverage']
        self.assertEqual(coverage['eyes']['expected'], ['left', 'right'])
        self.assertEqual(coverage['eyes']['rays'], {'left': 9, 'right': 9})
        self.assertEqual(coverage['eyes']['missing'], [])
        self.assertEqual(coverage['mouth']['expected'],
                         [[0.0, 0.0], [0.0, 45.0], [15.0, 0.0], [15.0, 45.0]])
        self.assertEqual(coverage['mouth']['rays'], {
            '(0.0, 0.0)': 9, '(0.0, 45.0)': 9,
            '(15.0, 0.0)': 9, '(15.0, 45.0)': 9})
        self.assertEqual(coverage['mouth']['missing'], [])

    def test_missing_report_preserves_expected_counts_with_unknown_observed_rays(self):
        coverage = aggregate_semantic(PROFILE, None)['coverage']
        self.assertEqual(coverage['eyes']['missing'], ['left', 'right'])
        self.assertEqual(coverage['eyes']['rays'], {'left': None, 'right': None})
        self.assertEqual(len(coverage['mouth']['expected']), 4)
        self.assertEqual(len(coverage['mouth']['missing']), 4)
        self.assertTrue(all(value is None for value in coverage['mouth']['rays'].values()))

    def test_missing_failure_field_invalidates_only_relevant_probe(self):
        report = semantic_report()
        del report['mouth'][0]['empty_or_posterior_hits']
        self.assert_metrics(aggregate_semantic(PROFILE, report), {
            'mouth_empty_or_posterior': None, 'mouth_unwanted_occluders': 0})
        report = semantic_report()
        del report['eyes'][0]['exposed_or_empty']
        self.assert_metrics(aggregate_semantic(PROFILE, report),
                            {'eye_exposed_or_empty': None})


if __name__ == '__main__':
    unittest.main(verbosity=2)
