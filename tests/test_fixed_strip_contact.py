# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest
import numpy as np
from lab_recipes.fixed_strip_contact import audit_fixed_core_strip_contact


class FixedStripContactTests(unittest.TestCase):
    def fixture(self):
        p=np.zeros((2,9,3))
        p[:,0]=[-1,1,0];p[:,1]=[0,1,0];p[:,4]=[0,0,0]
        p[:,5]=[0,2,0];p[:,7]=[0,.5,0];p[:,8]=[0,.5,.25]
        # Adjacent core faces may move while the contacted edge stays fixed.
        p[1,0,2]=.5
        data={'lid_poses':p,'lid_faces':np.array([[4,1,0],[1,5,0],[4,7,8],[7,1,8]]),
              'lid_face_domains':np.array([0,0,1,1]),
              'lid_construction_to_final_vertex_ids':np.arange(6),
              'lid_skin_boundary_edges':np.array([[4,8],[8,1]])}
        config={'construction':{'lengthSegments':2,'crossSectionSamples':4},
                'controls':{'blink':{'samples':[0,1]}}}
        return data,config

    def test_complete_fixed_subdivision_contact_without_topological_weld(self):
        data,config=self.fixture();r=audit_fixed_core_strip_contact(data,config)
        self.assertTrue(r['pass']);self.assertFalse(r['watertight_claim'])
        self.assertEqual(r['meshes']['lid']['core_strip_shared_topological_edges'],0)

    def test_small_detachment_is_not_hidden_by_endpoint_names(self):
        data,config=self.fixture();data['lid_poses'][:,7,0]=np.float32(.0001)
        self.assertFalse(audit_fixed_core_strip_contact(data,config)['pass'])

    def test_neutral_contact_does_not_certify_moving_strip(self):
        data,config=self.fixture();data['lid_poses'][1,7,2]=.125
        self.assertFalse(audit_fixed_core_strip_contact(data,config)['pass'])

    def test_reverse_coverage_rejects_a_half_edge_gap(self):
        data,config=self.fixture();data['lid_faces']=data['lid_faces'][:3]
        data['lid_face_domains']=np.array([0,0,1])
        data['lid_skin_boundary_edges']=np.array([[4,8],[8,7]])
        self.assertFalse(audit_fixed_core_strip_contact(data,config)['pass'])

    def test_empty_geometry_cannot_pass(self):
        _,config=self.fixture()
        with self.assertRaises(ValueError):audit_fixed_core_strip_contact({},config)


if __name__=='__main__':unittest.main()
