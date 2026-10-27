# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest
import numpy as np
from lab_recipes.construction_diagnostics import generated_geometry_diagnostics

class ConstructionDiagnosticTests(unittest.TestCase):
    def fixture(self):return np.array([[[0,0,0],[1,0,0],[0,1,0]],[[0,0,0],[1,0,0],[2,0,0]]],float),np.array([[0,1,2]])
    def test_strict_default_rejects_actual_collapse(self):
        p,f=self.fixture()
        with self.assertRaises(ValueError):generated_geometry_diagnostics(p,f,1e-12,{'newly_collapsed_face_count':1})
    def test_diagnostic_mode_reports_failure_without_changing_geometry(self):
        p,f=self.fixture();old=p.copy();r=generated_geometry_diagnostics(p,f,1e-12,{'newly_collapsed_face_count':1},diagnostics_only=True)
        self.assertFalse(r['numeric_diagnostics_pass']);self.assertEqual(r['generated_degenerate_observations'],1);self.assertEqual(r['newly_collapsed_face_count'],1);np.testing.assert_array_equal(p,old)
    def test_between_knot_collapse_is_not_hidden_by_valid_samples(self):
        p,f=self.fixture();p[1]=p[0];r=generated_geometry_diagnostics(p,f,1e-12,{'newly_collapsed_face_count':2},diagnostics_only=True)
        self.assertEqual(r['generated_degenerate_observations'],0);self.assertFalse(r['numeric_diagnostics_pass'])
    def test_nonfinite_geometry_remains_concrete_error(self):
        p,f=self.fixture();p[1,0,0]=np.nan
        with self.assertRaises(ValueError):generated_geometry_diagnostics(p,f,1e-12,{'newly_collapsed_face_count':1},diagnostics_only=True)
