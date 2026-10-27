# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest
import numpy as np
from lab_recipes.lash_contacts import classify_lash_contacts

class LashContactTests(unittest.TestCase):
    def setUp(self):
        ys=np.array([-1.,-.5,.5,1]);skin=np.array([[0,y,z] for z in [0,.1] for y in ys]);band=np.array([[.001,y,z] for z in [0,.02] for y in ys]);accessory=np.array([[.003,-.5,0],[.003,-.498,.002],[.003,-.502,.002]])
        self.v=np.vstack([skin,band,accessory]);base=np.array([(i,i+1,4+i) for i in range(3)]+[(i+1,5+i,4+i) for i in range(3)]);self.f=np.vstack([base,base+8,[[16,17,18]]]);self.rail=np.repeat(band[:4][None],2,axis=0);self.rail[1,1:3,2]-=.1
    def run_classification(self,**changes):
        arguments=dict(vertices=self.v,triangles=self.f,canonical_ids=np.arange(len(self.v)),band_indices=np.arange(8,16),skin_triangle_indices=np.arange(6),accessory_groups=[np.arange(16,19)],rail_poses=self.rail,aperture_lateral_bounds=[-1,1],contact_tolerance=.01,corner_fraction=.1,minimum_front_normal_x=0,minimum_dynamic_motion=.05,minimum_moving_roots=2,minimum_moving_span=.5,query_nearest_triangles=lambda points,vertices,faces:{'triangle_indices':np.zeros(len(points),dtype=int)})
        arguments.update(changes);return classify_lash_contacts(**arguments)
    def test_neutral_overlap_is_not_automatically_static(self):
        result=self.run_classification()
        self.assertEqual(result['static_vertices'].tolist(),[8,11])
        self.assertEqual(result['moving_vertices'].tolist(),[9,10])
        self.assertEqual(result['incidental_or_moving_skin_contacts'].tolist(),[9,10])
        self.assertEqual(len(result['accessories'][0]['source_vertices']),3)
    def test_zero_motion_cannot_satisfy_moving_contact_gate(self):
        with self.assertRaisesRegex(ValueError,'moving-margin'):
            self.run_classification(rail_poses=np.repeat(self.rail[:1],2,axis=0))
    def test_backfacing_contact_is_not_corner_support(self):
        f=self.f.copy();f[:6]=f[:6,::-1]
        with self.assertRaisesRegex(ValueError,'front-skin'):
            self.run_classification(triangles=f)
    def test_unbound_accessory_is_reported(self):
        v=self.v.copy();v[16:]+=10
        with self.assertRaisesRegex(ValueError,'Accessory'):
            self.run_classification(vertices=v)
    def test_nonfinite_threshold_and_unknown_ids_rejected(self):
        with self.assertRaises(ValueError):self.run_classification(contact_tolerance=float('nan'))
        with self.assertRaises(ValueError):self.run_classification(canonical_ids=np.full(len(self.v),-1))
    def test_requires_nonvacuous_support_span(self):
        with self.assertRaisesRegex(ValueError,'moving-margin'):
            self.run_classification(minimum_moving_span=1.1)
if __name__=='__main__':unittest.main()
