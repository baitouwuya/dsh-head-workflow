# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest
import numpy as np
from lab_recipes.triangle_depth_bound import TriangleDepthBound

class TriangleBoundsTests(unittest.TestCase):
    def setUp(self):
        self.bound=TriangleDepthBound([[[.2,0,0],[.4,1,0],[.3,0,1]],[[.8,2,2],[.9,3,2],[.85,2,3]]])
    def test_local_bounds_not_global_residual(self):
        np.testing.assert_array_equal(self.bound([[.1,.1],[2.1,2.1]],[[.2,.2],[2.2,2.2]]),[.4,.9])
    def test_empty_is_explicit(self):
        self.assertEqual(self.bound([[4,4]],[[5,5]])[0],-np.inf)
        self.assertEqual(self.bound.last_empty_footprints,1)
    def test_swept_footprint_is_conservative(self):
        self.assertEqual(self.bound([[.1,.1]],[[2.2,2.2]])[0],.9)
    def test_invalid_geometry_and_bounds_are_rejected(self):
        for bad in [[],np.zeros((2,3)),np.full((1,3,3),np.nan)]:
            with self.assertRaises(ValueError):TriangleDepthBound(bad)
        with self.assertRaises(ValueError):self.bound([[2,0]],[[1,1]])
        with self.assertRaises(ValueError):self.bound([[0,0]],[[np.nan,1]])
if __name__=='__main__':unittest.main()
