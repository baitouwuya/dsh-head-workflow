# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest
import numpy as np
from lab_recipes.lash_transfer import RigidLashCurveBinding,audit_paired_attachment,audit_lash_edge_strain

class LashTransferTests(unittest.TestCase):
    def setUp(self):
        self.curve=np.array([[0.,-1,0],[0,0,1],[0,1,0]])
        self.points=np.array([[.1,-.7,.4],[.1,-.6,.5],[.15,.5,.5],[.2,.7,.4]])
    def test_exact_neutral_identity(self):
        b=RigidLashCurveBinding(self.points,self.curve,influence_radius=.2)
        self.assertTrue(np.array_equal(b.evaluate(self.curve),self.points))
    def test_rigid_translation_preserves_shape_and_follows_rail(self):
        b=RigidLashCurveBinding(self.points,self.curve,influence_radius=.2);delta=np.array([.4,.3,-.2])
        np.testing.assert_allclose(b.evaluate(self.curve+delta),self.points+delta,atol=1e-14)
    def test_material_plane_rotation_preserves_offsets(self):
        angle=.8;R=np.array([[1,0,0],[0,np.cos(angle),-np.sin(angle)],[0,np.sin(angle),np.cos(angle)]])
        b=RigidLashCurveBinding(self.points,self.curve,influence_radius=.2)
        np.testing.assert_allclose(b.evaluate(self.curve@R.T),self.points@R.T,atol=1e-14)
        normals=np.tile([0.,0,1],(len(self.points),1))
        np.testing.assert_allclose(b.evaluate_normals(normals,self.curve@R.T),normals@R.T,atol=1e-14)
        self.assertTrue(np.array_equal(b.evaluate_normals(normals,self.curve),normals))
    def test_scale_and_translation_covariance(self):
        target=self.curve.copy();target[:,2]*=.25
        expected=RigidLashCurveBinding(self.points,self.curve,influence_radius=.2).evaluate(target)
        for scale in [1e-4,1e4]:
            offset=np.array([2,-3,4])*scale
            result=RigidLashCurveBinding(self.points*scale+offset,self.curve*scale+offset,influence_radius=.2*scale).evaluate(target*scale+offset)
            np.testing.assert_allclose((result-offset)/scale,expected,atol=1e-12)
    def test_duplicate_seam_points_receive_identical_motion(self):
        points=np.vstack([self.points,self.points[0]])
        target=self.curve.copy();target[:,2]*=.25
        result=RigidLashCurveBinding(points,self.curve,influence_radius=.2).evaluate(target)
        self.assertTrue(np.array_equal(result[0],result[-1]))
    def test_nonvacuous_curve_response(self):
        target=self.curve.copy();target[:,2]-=.2
        result=RigidLashCurveBinding(self.points,self.curve,influence_radius=.2).evaluate(target)
        self.assertGreater(np.linalg.norm(result-self.points,axis=1).min(),.19)
    def test_invalid_input_is_rejected(self):
        for radius in [0,-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):RigidLashCurveBinding(self.points,self.curve,influence_radius=radius)
        b=RigidLashCurveBinding(self.points,self.curve,influence_radius=.2)
        with self.assertRaises(ValueError):b.evaluate(self.curve[:-1])
        with self.assertRaises(ValueError):b.evaluate(np.full_like(self.curve,np.nan))
    def test_attachment_checks_actual_carrier_motion(self):
        root=self.points;carrier=root-[.001,0,0]
        good=audit_paired_attachment(root,root+[0,0,1],carrier,carrier+[0,0,1],maximum_gap=.002)
        self.assertTrue(good['attachment_pass'])
        bad=audit_paired_attachment(root,root+[0,0,1],carrier,carrier,maximum_gap=.002)
        self.assertFalse(bad['attachment_pass'])
    def test_inherited_detachment_cannot_pass_by_preserving_offset(self):
        result=audit_paired_attachment(self.points,self.points,self.points-[.1,0,0],self.points-[.1,0,0],maximum_gap=.002)
        self.assertEqual(result['maximum_gap_growth'],0)
        self.assertFalse(result['attachment_pass'])
    def test_strain_catches_compression_and_extension(self):
        p=np.array([[0.,0,0],[1,0,0],[0,1,0]])
        for factor in [.1,3]:
            r=audit_lash_edge_strain(p,p*factor,[[0,1,2]],minimum_edge_length=1e-8,minimum_ratio=.8,maximum_ratio=1.2)
            self.assertFalse(r['strain_pass'])
        r=audit_lash_edge_strain(p,p+[1,2,3],[[0,1,2]],minimum_edge_length=1e-8,minimum_ratio=.8,maximum_ratio=1.2)
        self.assertTrue(r['strain_pass'])
if __name__=='__main__':unittest.main()
