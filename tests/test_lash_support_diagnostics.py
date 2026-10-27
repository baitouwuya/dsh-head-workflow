# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest
import numpy as np
from lab_recipes.lash_contacts import classify_lash_contacts

class LashSupportDiagnosticTests(unittest.TestCase):
    def args(self):
        ys=np.array([-1.,-.5,.5,1]);skin=np.array([[0,y,z] for z in [0,.1] for y in ys]);band=np.array([[.001,y,z] for z in [0,.02] for y in ys]);v=np.vstack([skin,band]);base=np.array([(i,i+1,4+i) for i in range(3)]+[(i+1,5+i,4+i) for i in range(3)]);rail=np.repeat(band[:4][None],2,axis=0);rail[1,1:3,2]-=.1
        return dict(vertices=v,triangles=np.vstack([base,base+8]),canonical_ids=np.arange(len(v)),band_indices=np.arange(8,16),skin_triangle_indices=np.arange(6),accessory_groups=[],rail_poses=rail,aperture_lateral_bounds=[-1,1],contact_tolerance=.01,corner_fraction=.1,minimum_front_normal_x=0.,minimum_dynamic_motion=.05,minimum_moving_roots=3,minimum_moving_span=1.1,query_nearest_triangles=lambda p,v,f:{'triangle_indices':np.zeros(len(p),int)})
    def test_diagnostics_keep_actual_two_roots_and_original_limits(self):
        kw=self.args()
        with self.assertRaisesRegex(ValueError,'moving-margin'):classify_lash_contacts(**kw)
        r=classify_lash_contacts(**kw,support_diagnostics_only=True);self.assertFalse(r['support_satisfied']);self.assertEqual(r['moving_vertices'].tolist(),[9,10]);self.assertEqual(r['support_diagnostics'],{'observed_roots':2,'required_roots':3,'observed_span':1.,'required_span':1.1,'contact_tolerance':.01})
    def test_zero_motion_is_reported_as_zero_support_not_an_empty_array_crash(self):
        kw=self.args();kw['rail_poses'][1]=kw['rail_poses'][0];r=classify_lash_contacts(**kw,support_diagnostics_only=True);self.assertEqual(len(r['moving_vertices']),0);self.assertEqual(r['moving_span'],0);self.assertFalse(r['support_satisfied'])
    def test_diagnostics_mode_is_explicit_boolean(self):
        with self.assertRaises(ValueError):classify_lash_contacts(**self.args(),support_diagnostics_only='false')
if __name__=='__main__':unittest.main()
