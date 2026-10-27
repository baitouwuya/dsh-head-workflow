# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest
import numpy as np
from lab_recipes.lid_normals import area_weighted_normals,build_normal_targets,audit_normal_interpolation,orient_closed_generated_mesh,split_generated_shading_domains

class LidNormalTests(unittest.TestCase):
    def setUp(self):
        self.p=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0.]],float)
        self.f=np.array([[0,1,2],[0,2,3]])
    def test_translation_preserves_normal_and_zero_delta(self):
        out=build_normal_targets(np.array([self.p,self.p+[1,2,3]]),self.f)
        self.assertTrue(np.allclose(out['base_normals'],[0,0,1]))
        self.assertTrue(np.array_equal(out['target_normal_deltas'],np.zeros_like(out['target_normal_deltas'])))
    def test_sample_targets_recover_recomputed_normals(self):
        pose=self.p.copy();pose[2,2]=.5
        out=build_normal_targets(np.array([self.p,pose]),self.f)
        rebuilt=out['base_normals']+out['target_normal_deltas'][0]
        self.assertTrue(np.allclose(rebuilt,area_weighted_normals(pose,self.f),atol=1e-7))
        self.assertTrue(np.allclose(np.linalg.norm(rebuilt,axis=1),1,atol=1e-7))
    def test_source_arrays_unchanged(self):
        original=self.p.copy();build_normal_targets(np.array([self.p,self.p+[0,0,.1]]),self.f)
        self.assertTrue(np.array_equal(self.p,original))
    def test_unstable_or_invalid_normals_rejected(self):
        with self.assertRaises(ValueError):area_weighted_normals(self.p,[[0,0,0]])
    def test_interpolation_error_is_measured(self):
        pose=self.p.copy();pose[2,2]=1
        ps=np.array([self.p,pose]);out=build_normal_targets(ps,self.f);report=audit_normal_interpolation(ps,self.f,out['sample_normals'])
        self.assertEqual(report['cancelled_interpolated_normals'],0)
        self.assertGreater(report['angular_error_degrees_quantiles'][-1],0)

    def test_inward_closed_component_is_reoriented_without_position_change(self):
        p=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1.]]);f=np.array([[0,1,2],[0,3,1],[0,2,3],[1,3,2]])
        old=p.copy();out=orient_closed_generated_mesh(p,f)
        self.assertEqual(out['flipped_triangles'],4)
        self.assertGreater(out['components'][0]['signed_volume_after'],0)
        self.assertTrue(np.array_equal(p,old))
        again=orient_closed_generated_mesh(p,out['faces']);self.assertEqual(again['flipped_triangles'],0)

    def test_orientation_rejects_open_or_inconsistent_winding(self):
        with self.assertRaisesRegex(ValueError,'closed'):
            orient_closed_generated_mesh(self.p,self.f)
        p=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1.]])
        with self.assertRaisesRegex(ValueError,'inconsistent'):
            orient_closed_generated_mesh(p,[[0,2,1],[0,3,1],[0,2,3],[1,3,2]])

    def test_shading_domain_split_preserves_triangle_trajectories(self):
        poses=np.array([self.p,self.p+[0,0,.2]])
        out=split_generated_shading_domains(poses,self.f,[0,1])
        self.assertEqual(len(out['domains']),2)
        for domain in out['domains']:
            self.assertTrue(np.array_equal(domain['poses'][:,domain['faces']],poses[:,self.f[domain['source_face_indices']]]))
            self.assertTrue(np.array_equal(domain['poses'],poses[:,domain['source_vertex_indices']]))

    def test_invalid_shading_domain_length_rejected(self):
        with self.assertRaises(ValueError):
            split_generated_shading_domains(np.array([self.p,self.p]),self.f,[0])

if __name__=='__main__':unittest.main()
