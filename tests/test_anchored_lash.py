# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest
import numpy as np
from lab_recipes.anchored_lash import AnchoredLashBinding,rigid_contact_transfer
class AnchoredLashTests(unittest.TestCase):
    def setUp(self):
        self.p=np.array([[0.,0,0],[1,0,0],[0,1,0],[1,1,0]])
        self.f=np.array([[0,1,2],[1,3,2]])
    def binding(self):return AnchoredLashBinding(self.p,self.f,[0,1],target_strength=.01,max_iterations=60,convergence_tolerance=1e-10,maximum_vertices=20)
    def test_exact_neutral(self):
        p,r=self.binding().evaluate(self.p);self.assertTrue(np.array_equal(p,self.p));np.testing.assert_equal(r,np.repeat(np.eye(3)[None],4,axis=0))
    def test_measured_roots_are_exact_not_soft(self):
        target=self.p.copy();target[2:,2]=.2;b=self.binding();p,_=b.evaluate(target)
        self.assertTrue(np.array_equal(p[:2],self.p[:2]));self.assertGreater(p[2:,2].max(),.1)
        self.assertEqual(b.last_report['fixed_root_maximum_error'],0)
    def test_rigid_carrier_translation(self):
        b=self.binding();d=np.array([1.,2,3]);p,_=b.evaluate(self.p+d,carrier_points=self.p[:2]+d);np.testing.assert_allclose(p,self.p+d,atol=1e-12)
    def test_invalid_runtime_limit_and_indices(self):
        with self.assertRaises(ValueError):AnchoredLashBinding(self.p,self.f,[0.5],target_strength=.01,max_iterations=2,convergence_tolerance=0,maximum_vertices=20)
        with self.assertRaises(ValueError):AnchoredLashBinding(self.p,self.f,[0],target_strength=.01,max_iterations=2,convergence_tolerance=0,maximum_vertices=3)
    def test_accessory_transfer_preserves_shape_and_contact(self):
        d=np.array([1.,2,3]);p,r=rigid_contact_transfer(self.p,self.p[:2],self.p[:2]+d,self.p,self.p+d);np.testing.assert_allclose(p,self.p+d,atol=1e-12);np.testing.assert_allclose(r,np.eye(3),atol=1e-12)
    def test_relative_edge_weights_protect_a_short_source_edge(self):
        p=np.array([[0.,0,0],[.001,0,0],[1,0,0],[1,1,0],[0,1,0]]);f=np.array([[0,1,4],[1,2,3],[1,3,4]]);target=p.copy();target[1,2]=.1;target[3:,2]=.1;ratios=[]
        for power in [0,2]:
            b=AnchoredLashBinding(p,f,[0,2],target_strength=.001,max_iterations=400,convergence_tolerance=0,maximum_vertices=20,edge_weight_power=power);posed,_=b.evaluate(target);ratios.append(np.linalg.norm(posed[1]-posed[0])/.001)
        self.assertLess(ratios[1],ratios[0]);self.assertLess(ratios[1],1.05)
    def test_scale_and_translation_covariance(self):
        target=self.p.copy();target[2:,2]=.2
        def solve(p,t):
            return AnchoredLashBinding(p,self.f,[0,1],target_strength=.01,max_iterations=80,convergence_tolerance=0,maximum_vertices=20).evaluate(t)[0]
        reference=solve(self.p,target)
        for scale in [1e-3,1e3]:
            offset=np.array([2,-3,4])*scale
            np.testing.assert_allclose((solve(self.p*scale+offset,target*scale+offset)-offset)/scale,reference,atol=1e-10)
if __name__=='__main__':unittest.main()
