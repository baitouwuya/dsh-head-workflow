# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest
import numpy as np
from lab_recipes.frontmost_skin import frontmost_skin_bindings,FrontmostSkinIndex,frontmost_skin_triangle_ids

class FrontmostSkinTests(unittest.TestCase):
    def test_nearest_hidden_parallel_sheet_is_replaced(self):
        v=np.array([[x,y,z] for x in [0.,1.] for y,z in [(-1,-1),(1,-1),(0,1)] ]);f=np.array([[0,1,2],[3,4,5]])
        r=frontmost_skin_bindings([[0,0,0]],v,f,[0,1]);self.assertEqual(r['source_triangle_ids'].tolist(),[1]);np.testing.assert_allclose(r['positions'],[[1,0,0]])
        self.assertFalse(FrontmostSkinIndex(v,f,[0,1]).segment_frontmost([0,-.2,0],[0,.2,0])['frontmost'])
    def test_narrow_occluder_between_endpoint_samples_is_found(self):
        v=np.array([[0,-1,-1],[0,1,-1],[0,0,1],[.1,.11,-.01],[.1,.13,-.01],[.1,.12,.01]]);f=np.array([[0,1,2],[3,4,5]])
        r=FrontmostSkinIndex(v,f,[0,1]).segment_frontmost([0,-.4,0],[0,.4,0]);self.assertFalse(r['frontmost']);self.assertAlmostEqual(r['maximum_occluding_depth'],.1);self.assertGreater(r['witness_parameter'],.6);self.assertLess(r['witness_parameter'],.7)
        self.assertEqual(frontmost_skin_triangle_ids(v,f,[0,1],[0])['triangle_ids'].tolist(),[])
    def test_projected_hole_cannot_pass_as_nonempty_support(self):
        v=np.array([[0,-2,-1],[0,-.1,-1],[0,-1,1],[0,.1,-1],[0,2,-1],[0,1,1]]);f=np.array([[0,1,2],[3,4,5]])
        r=FrontmostSkinIndex(v,f,[0,1]).segment_frontmost([0,-1,0],[0,1,0]);self.assertTrue(r['nonempty_projected_support']);self.assertFalse(r['complete_projected_support']);self.assertFalse(r['frontmost'])
    def test_far_nearly_edge_on_triangle_cannot_occlude_local_segment(self):
        v=np.array([[0,-1,-1],[0,1,-1],[0,0,1],[2,3,3],[3,3.003,3.009],[4,3.002,3.0060000000000002]])
        r=FrontmostSkinIndex(v,np.array([[0,1,2],[3,4,5]]),[0,1]).segment_frontmost([0,-.2,0],[0,.2,0])
        self.assertTrue(r['frontmost']);self.assertLessEqual(r['maximum_occluding_depth'],1e-6)
    def test_invalid_geometry_and_endpoints_rejected(self):
        v=np.array([[0,-1,-1],[0,1,-1],[0,0,1]]);f=np.array([[0,1,2]])
        with self.assertRaises(ValueError):FrontmostSkinIndex(v,f.astype(float),[0])
        with self.assertRaises(ValueError):FrontmostSkinIndex(v,f,[])
        with self.assertRaises(ValueError):FrontmostSkinIndex(v,f,[0]).segment_frontmost([np.nan,0,0],[0,0,0])
if __name__=='__main__':unittest.main()
