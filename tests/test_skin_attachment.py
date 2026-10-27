# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest,numpy as np
from lab_recipes.skin_attachment import nearest_triangle_bindings,evaluate_bindings,transition_outer_boundary,weld_identical_generated_trajectories,SkinSurfaceIndex
class BindingTests(unittest.TestCase):
    def test_plane_edge_vertex_nearest_and_reconstruction(self):
        v=np.array([[0.,0,0],[0,1,0],[0,0,1]]);f=np.array([[0,1,2]]);q=np.array([[2,.2,.3],[1,-.3,.4],[0,2,0]])
        b=nearest_triangle_bindings(q,v,f);np.testing.assert_allclose(b['positions'],[[0,.2,.3],[0,0,.4],[0,1,0]],atol=1e-14)
        np.testing.assert_allclose(evaluate_bindings(v,f,b['triangle_indices'],b['barycentric']),b['positions']);self.assertTrue((b['barycentric']>=0).all())
    def test_choose_actual_nearest_triangle(self):
        v=np.array([[0.,0,0],[0,1,0],[0,0,1],[2,0,0],[2,1,0],[2,0,1]]);f=np.array([[0,1,2],[3,4,5]])
        self.assertEqual(nearest_triangle_bindings([[1.8,.2,.2]],v,f)['triangle_indices'][0],1)
    def test_bad_input_fails(self):
        with self.assertRaises(ValueError):nearest_triangle_bindings([[np.nan,0,0]],[[0,0,0]],[[0,0,0]])
        with self.assertRaises(ValueError):nearest_triangle_bindings([[0,0,0]],[[0,0,0]],[[0,1,0]])
class TransitionTests(unittest.TestCase):
    def fixture(self):
        p=np.zeros((3,10,3));p[:,np.arange(8),1]=np.repeat([0,1],4);p[1,[3,7],2]=.2;p[2,[3,7],2]=.4
        return p,np.array([1,5,8,9]),np.array([[-1,0,0],[-1,1,0],[-1,0,0],[-1,1,0]])
    def test_attached_outer_fixed_inner_unchanged_and_no_mutation(self):
        p,i,a=self.fixture();old=p.copy();q=transition_outer_boundary(p,i,a,4)
        np.testing.assert_array_equal(q[:,i],np.broadcast_to(a,q[:,i].shape));np.testing.assert_array_equal(q[:,[3,7]],p[:,[3,7]]);np.testing.assert_array_equal(p,old)
    def test_moving_outer_or_bad_topology_refused(self):
        p,i,a=self.fixture();p[1,1,0]=.1
        with self.assertRaises(ValueError):transition_outer_boundary(p,i,a,4)
        p,i,a=self.fixture()
        with self.assertRaises(ValueError):transition_outer_boundary(p,i,a,6)
        with self.assertRaises(ValueError):transition_outer_boundary(p,i[::-1],a,4)
    def test_weld_requires_identical_complete_trajectory(self):
        p=np.array([[[0.,0,0],[0,0,0],[0,0,0],[1,0,0]],[[0,0,0],[0,.2,0],[0,0,0],[1,0,0]]]);f=np.array([[0,2,3],[0,1,3]])
        w=weld_identical_generated_trajectories(p,f)
        self.assertEqual(w['merged_vertices'],1);self.assertEqual(w['removed_zero_edge_faces'],1)
        self.assertNotEqual(w['old_to_new'][0],w['old_to_new'][1])
class SegmentCoverageTests(unittest.TestCase):
    def test_complete_two_triangle_surface_and_tolerance(self):
        v=np.array([[0.,0,0],[0,1,0],[0,1,1],[0,0,1]]);index=SkinSurfaceIndex(v,[[0,1,2],[0,2,3]])
        self.assertTrue(index.segment_coverage([0,.1,.2],[0,.9,.8],1e-6)['covered'])
        self.assertTrue(index.segment_coverage([5e-7,.1,.2],[5e-7,.9,.8],1e-6)['covered'])
        self.assertFalse(index.segment_coverage([2e-6,.1,.2],[2e-6,.9,.8],1e-6)['covered'])
    def test_gap_between_disconnected_triangles_is_not_sampled_away(self):
        v=np.array([[0.,0,0],[0,1,0],[0,0,1],[0,2,0],[0,3,0],[0,3,1]]);index=SkinSurfaceIndex(v,[[0,1,2],[3,4,5]])
        result=index.segment_coverage([0,.1,.1],[0,2.9,.1],1e-6)
        self.assertFalse(result['covered']);self.assertTrue(result['uncovered_parameter_intervals'])
if __name__=='__main__':unittest.main()

