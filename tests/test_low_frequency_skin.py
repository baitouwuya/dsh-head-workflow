# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest
import numpy as np
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from full_look_arrays import low_frequency_skin_field


class SkinFieldTests(unittest.TestCase):
    def setUp(self):
        y,z=np.meshgrid(np.linspace(-1,1,11),np.linspace(-1,1,9))
        self.yz=np.c_[y.ravel(),z.ravel()]
        self.rgb=np.c_[.72+.02*y.ravel(),.66+.01*z.ravel(),.62+.01*y.ravel()]
        self.rgba=np.c_[self.rgb,np.ones(len(self.rgb))]

    def test_recovers_low_frequency_gradient_and_rejects_ink(self):
        rgba=self.rgba.copy();rgba[::7,:3]=.025
        q=np.array([[0,0],[.2,.3],[-.3,-.2]])
        r=low_frequency_skin_field(self.yz,rgba,q)
        expected=np.c_[.72+.02*q[:,0],.66+.01*q[:,1],.62+.01*q[:,0]]
        np.testing.assert_allclose(r['colors_linear_rgba'][:,:3],expected,atol=1e-6)
        self.assertEqual(r['report']['dark_reference_outlier_count'],len(rgba[::7]))
        self.assertFalse(r['report']['boundary_pigment_constraint'])

    def test_shared_coordinates_have_identical_colors_independent_of_query_mesh(self):
        first=np.array([[0,0],[.3,.2]])
        second=np.array([[.3,.2],[-.4,.2],[0,0]])
        a=low_frequency_skin_field(self.yz,self.rgba,first)['colors_linear_rgba']
        b=low_frequency_skin_field(self.yz,self.rgba,second)['colors_linear_rgba']
        np.testing.assert_array_equal(a[0],b[2]);np.testing.assert_array_equal(a[1],b[0])

    def test_field_has_no_high_frequency_stripes(self):
        q=np.c_[np.linspace(-.5,.5,101),np.zeros(101)]
        result=low_frequency_skin_field(self.yz,self.rgba,q)['colors_linear_rgba']
        self.assertLess(float(abs(np.diff(result,n=2,axis=0)).max()),2e-7)

    def test_rank_deficiency_uses_reported_median(self):
        result=low_frequency_skin_field(np.zeros((4,2)),np.tile([.7,.6,.5,1],(4,1)),np.array([[0,0],[9,9]]))
        self.assertEqual(result['report']['fit_rank'],1)
        np.testing.assert_array_equal(result['colors_linear_rgba'][0],result['colors_linear_rgba'][1])

    def test_nonfinite_or_invalid_colors_rejected(self):
        for bad in (float('nan'),-1,2):
            rgba=self.rgba.copy();rgba[0,0]=bad
            with self.assertRaises(ValueError):low_frequency_skin_field(self.yz,rgba,np.array([[0,0]]))


if __name__=='__main__':unittest.main()
