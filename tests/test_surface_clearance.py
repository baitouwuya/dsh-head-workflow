# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest,numpy as np
from lab_recipes.surface_routes import SkinTriangleGraph
from lab_recipes.skin_attachment import nearest_triangle_bindings
from lab_recipes.eye_clearance import enforce_eye_clearance
class SourceRouteTests(unittest.TestCase):
    def test_each_hinge_route_segment_lies_on_actual_skin(self):
        v=np.array([[0.,0,0],[0,1,0],[0,0,1],[1,1,0]]);f=np.array([[0,1,2],[1,3,2]]);graph=SkinTriangleGraph(v,f,np.arange(4));r=graph.route(np.array([0,.2,.2]),np.array([.2,.6,.4]),0,1,padding=2)
        q=np.concatenate([r['positions'][:-1]*(1-t)+r['positions'][1:]*t for t in [.25,.5,.75]])
        self.assertLess(nearest_triangle_bindings(q,v,f)['distance'].max(),1e-12)
    def test_disconnected_surface_fails(self):
        v=np.array([[0.,0,0],[0,1,0],[0,0,1],[2,0,0],[2,1,0],[2,0,1]]);f=np.array([[0,1,2],[3,4,5]]);graph=SkinTriangleGraph(v,f,np.arange(6))
        with self.assertRaises(ValueError):graph.route(np.array([0,.2,.2]),np.array([2,.2,.2]),0,1,padding=3)
class ClearanceTests(unittest.TestCase):
    def fixture(self):
        p=np.array([[[0.,0,0],[0,1,0],[0,0,1]]]*2);f=np.array([[0,1,2]]);eye=p[0].copy();eye[:,0]=.1;return p,f,eye
    def test_exact_overlap_plane_clears_without_yz_or_source_mutation(self):
        p,f,e=self.fixture();old=p.copy();r=enforce_eye_clearance(p,f,e,f,[],.01,.2)
        self.assertTrue((r['poses'][:,:,0]>=.11-1e-12).all());np.testing.assert_array_equal(r['poses'][:,:,1:],p[:,:,1:]);np.testing.assert_array_equal(p,old);self.assertFalse(r['unresolved_fixed_constraints'])
    def test_fixed_conflict_is_reported_not_silently_moved(self):
        p,f,e=self.fixture();r=enforce_eye_clearance(p,f,e,f,[0,1,2],.01,.2)
        self.assertTrue(r['unresolved_fixed_constraints']);np.testing.assert_array_equal(r['poses'],p)
    def test_offset_limit_and_nonfinite_are_rejected(self):
        p,f,e=self.fixture()
        with self.assertRaises(ValueError):enforce_eye_clearance(p,f,e,f,[],.01,.001)
        with self.assertRaises(ValueError):enforce_eye_clearance(p,f,e,f,[],float('nan'),.2)
if __name__=='__main__':unittest.main()

