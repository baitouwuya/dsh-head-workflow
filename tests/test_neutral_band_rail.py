# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest
import numpy as np
from lab_recipes.neutral_band_rail import project_rail_to_band_sections,fit_tapered_neutral_band_rail,apply_neutral_rail_fit

class NeutralBandRailTests(unittest.TestCase):
    def fixture(self):
        v=np.array([[.3,-1,-.2],[.3,1,-.2],[.3,1,.2],[.3,-1,.2]]);f=np.array([[0,1,2],[0,2,3]]);rail=np.c_[np.full(5,.4),np.linspace(-1,1,5),np.zeros(5)];return rail,v,f
    def test_sections_use_source_barycentrics_and_preserve_lateral_coordinates(self):
        rail,v,f=self.fixture();before=v.copy();r=project_rail_to_band_sections(rail,v,f);np.testing.assert_allclose(r['positions'][:,0],.3);np.testing.assert_allclose(r['positions'][:,1],rail[:,1]);np.testing.assert_allclose(r['positions'],np.einsum('ni,nij->nj',r['barycentric'],v[f[r['triangle_indices']]]));np.testing.assert_array_equal(v,before)
    def test_taper_preserves_canthi_and_fits_center_without_contact_limit_change(self):
        rail,v,f=self.fixture();r=fit_tapered_neutral_band_rail(rail,v,f,[-1,1],taper_outer_fraction=.1,taper_inner_fraction=.25);np.testing.assert_array_equal(r['positions'][[0,-1]],rail[[0,-1]]);self.assertAlmostEqual(r['positions'][2,0],.3)
    def test_local_neutral_fit_preserves_outer_boundary_and_closed_pose(self):
        m=8;count=3;phi=np.arange(m)*2*np.pi/m;base=np.array([[.3+.01*np.cos(a),y,.02*np.sin(a)] for y in [-.5,0,.5] for a in phi]+[[.3,-1,0],[.3,1,0]]);poses=np.repeat(base[None],3,axis=0);poses[1,:,2]-=.01;poses[2,:,2]-=.02;inner=np.arange(count)*m+6;target=base[inner].copy();target[:,0]-=.005;out=apply_neutral_rail_fit(poses,np.arange(len(base)),m,target,inner,[0,.5,1]);np.testing.assert_array_equal(out[-1],poses[-1]);np.testing.assert_array_equal(out[:,np.r_[np.arange(count)*m+2,len(base)-2,len(base)-1]],poses[:,np.r_[np.arange(count)*m+2,len(base)-2,len(base)-1]]);np.testing.assert_allclose(out[0,inner],target)
    def test_missing_surface_support_and_wrong_mapping_are_explicit(self):
        rail,v,f=self.fixture();rail[-1,1]=2
        with self.assertRaisesRegex(ValueError,'no surface support'):project_rail_to_band_sections(rail,v,f)
        with self.assertRaises(ValueError):apply_neutral_rail_fit(np.zeros((2,10,3)),np.arange(10,dtype=float),8,np.zeros((1,3)),[6],[0,1])
if __name__=='__main__':unittest.main()
