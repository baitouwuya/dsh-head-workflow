# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest,numpy as np
from lab_recipes.skin_transition import append_skin_transition_strips
from lab_recipes.skin_attachment import nearest_triangle_bindings,SkinSurfaceIndex

class ContinuousTransitionTests(unittest.TestCase):
    def fixture(self):
        skin=np.array([[0.,0,0],[0,1,0],[0,0,1],[1,1,0]]);sf=np.array([[0,1,2],[1,3,2]])
        p=np.array([[0.,.2,.2],[.2,.6,.4],[.8,.2,.3],[.5,.8,.7]]);f=np.array([[0,1,2],[0,3,1],[0,2,3],[1,3,2]]);binding=nearest_triangle_bindings(p,skin,sf)
        return skin,sf,np.repeat(p[None],2,axis=0),f,binding
    def call(self,skin,sf,p,f,binding,maximum_route_length=4):
        return append_skin_transition_strips(p,f,[0,1],skin,sf,np.arange(len(skin)),[0,1],binding['triangle_indices'],binding['barycentric'],attachment_tolerance=1e-6,source_double_area_floor=1e-14,route_padding=1,maximum_route_padding=2,route_depth_margin=2,maximum_route_length=maximum_route_length)
    def test_routed_strip_fully_attaches_and_preserves_source(self):
        skin,sf,p,f,b=self.fixture();old=skin.copy();r=self.call(skin,sf,p,f,b);self.assertTrue(r['complete_edge_certificate_pass']);self.assertTrue(r['routes']);self.assertGreater(len(r['faces']),len(f));np.testing.assert_array_equal(skin,old)
        index=SkinSurfaceIndex(skin,sf)
        for a,c in r['skin_boundary_edges']:self.assertTrue(index.segment_coverage(r['poses'][0,a],r['poses'][0,c],1e-6)['covered'])
        np.testing.assert_array_equal(r['poses'][0,r['skin_boundary_vertices']],r['poses'][1,r['skin_boundary_vertices']])
    def test_fixed_but_detached_input_is_rejected(self):
        skin,sf,p,f,b=self.fixture();p[:,0,0]=.05
        with self.assertRaisesRegex(ValueError,'not actually attached'):self.call(skin,sf,p,f,b)
    def test_declared_route_limit_prevents_unbounded_repair(self):
        skin,sf,p,f,b=self.fixture()
        with self.assertRaisesRegex(ValueError,'No bounded'):self.call(skin,sf,p,f,b,maximum_route_length=.01)
if __name__=='__main__':unittest.main()
