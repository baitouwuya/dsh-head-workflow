# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest,sys
from pathlib import Path
import numpy as np
from lab_recipes.skin_route_preflight import measure_skin_route_requirements

class RoutePreflightTests(unittest.TestCase):
    def setUp(self):
        self.v=np.array([[x,y,z] for x,y in [(0,0),(.1,1),(.2,.8),(.3,2)] for z in [-.5,.5]])
        self.f=np.array([[2*i,2*i+2,2*i+3] for i in range(3)]+[[2*i,2*i+3,2*i+1] for i in range(3)])
        self.p=np.array([self.v[self.f[0]].mean(0),self.v[self.f[2]].mean(0)])
        self.kw={'attachment_tolerance':1e-6,'route_padding':.1,'maximum_route_padding':1.,'route_depth_margin':.5}
    def test_fold_filter_disconnects_but_source_component_route_is_certified(self):
        n=np.cross(self.v[self.f[:,1]]-self.v[self.f[:,0]],self.v[self.f[:,2]]-self.v[self.f[:,0]])
        with self.assertRaisesRegex(ValueError,'No certified'):
            measure_skin_route_requirements(self.p,self.v,self.f,np.arange(8),np.flatnonzero(n[:,0]>0),**self.kw)
        r=measure_skin_route_requirements(self.p,self.v,self.f,np.arange(8),np.arange(6),**self.kw)
        self.assertGreater(r['required_maximum_route_length'],np.linalg.norm(self.p[1]-self.p[0]));self.assertFalse(r['source_geometry_changed'])
        self.assertLessEqual(r['routes'][0]['maximum_chord_distance'],1.)
    def test_exterior_rejection_cannot_be_overridden_by_connected_path(self):
        with self.assertRaisesRegex(ValueError,'No certified'):
            measure_skin_route_requirements(self.p,self.v,self.f,np.arange(8),np.arange(6),segment_exterior_check=lambda a,b:False,**self.kw)
    def test_direct_edge_also_requires_exterior_coverage(self):
        same=self.v[self.f[0]][:2]
        with self.assertRaisesRegex(ValueError,'No certified'):
            measure_skin_route_requirements(same,self.v,self.f,np.arange(8),np.arange(6),segment_exterior_check=lambda a,b:False,**self.kw)
    def test_detached_anchor_is_not_accepted_by_route_length_fit(self):
        p=self.p.copy();p[0,0]+=10
        with self.assertRaisesRegex(ValueError,'not attached'):
            measure_skin_route_requirements(p,self.v,self.f,np.arange(8),np.arange(6),**self.kw)
if __name__=='__main__':unittest.main()
