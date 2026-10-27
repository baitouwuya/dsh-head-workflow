# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Failure/pass-contract regressions found in the independent appearance review."""
import unittest
import numpy as np
from lab_recipes.lid_normals import (area_weighted_normals,build_normal_targets,
    audit_normal_interpolation,orient_closed_generated_mesh,
    split_generated_shading_domains,audit_face_normal_jumps)
from lab_recipes.skin_appearance import (transfer_skin_colors,transfer_lid_anchor_colors,
    audit_source_uv_charts,audit_uv_chart_excursions,interpolate_skin_color_strip,
    blend_skin_boundary_colors)

class AppearanceContractGuards(unittest.TestCase):
    def setUp(self):
        self.p=np.array([[0.,0,0],[1,0,0],[1,1,0],[0,1,0]])
        self.f=np.array([[0,1,2],[0,2,3]])
        self.uv=self.p[:,:2]*.5
        self.image=np.full((4,4,3),200,dtype=np.uint8)
        self.poses=np.array([self.p,self.p+[0,0,.1]])
        self.normals=build_normal_targets(self.poses,self.f)['sample_normals']
    def test_fractional_geometry_indices_are_not_truncated(self):
        bad=self.f+.1
        for operation in [lambda:area_weighted_normals(self.p,bad),
                          lambda:build_normal_targets(self.poses,bad),
                          lambda:split_generated_shading_domains(self.poses,bad,[0,1]),
                          lambda:audit_face_normal_jumps(self.p,bad),
                          lambda:audit_normal_interpolation(self.poses,bad,self.normals)]:
            with self.assertRaises(ValueError):operation()
        tetra=np.array([[0.,0,0],[1,0,0],[0,1,0],[0,0,1]])
        faces=np.array([[0,1,2],[0,3,1],[0,2,3],[1,3,2]])+.1
        with self.assertRaises(ValueError):orient_closed_generated_mesh(tetra,faces)
    def test_empty_required_normal_geometry_is_rejected(self):
        p=np.empty((0,3));f=np.empty((0,3),dtype=int)
        with self.assertRaises(ValueError):area_weighted_normals(p,f)
        with self.assertRaises(ValueError):build_normal_targets(np.array([p,p]),f)
        with self.assertRaises(ValueError):split_generated_shading_domains(np.empty((0,4,3)),self.f,[0,1])
    def test_interpolation_rejects_vacuous_or_nonfinite_inputs(self):
        for poses,normals,samples in [(self.poses[:1],self.normals[:1],[.5]),
                                     (self.poses,self.normals,[]),
                                     (self.poses,np.full_like(self.normals,np.nan),[.5]),
                                     (self.poses,np.full_like(self.normals,np.inf),[.5]),
                                     (self.poses,np.zeros_like(self.normals),[.5])]:
            with self.assertRaises(ValueError):audit_normal_interpolation(poses,self.f,normals,samples)
    def test_true_interval_normal_cancellation_cannot_hide_between_subsamples(self):
        normals=self.normals.copy();normals[1]*=-1
        report=audit_normal_interpolation(self.poses,self.f,normals,subsamples=(.25,))
        self.assertEqual(report['cancelled_interpolated_normals'],0)
        self.assertEqual(report['interval_cancelled_vertex_normals'],4)
        self.assertEqual(report['minimum_interpolated_normal_length'],0)
    def test_normal_jump_audit_includes_all_pairs_at_three_face_contact(self):
        a=np.radians(80);p=np.array([[0.,0,0],[1,0,0],[0,1,0],[0,np.cos(a),np.sin(a)],[0,np.cos(a),-np.sin(a)]])
        r=audit_face_normal_jumps(p,[[0,1,2],[0,1,3],[0,1,4]])
        self.assertEqual(r['nonmanifold_edges'],1)
        self.assertEqual(r['adjacent_face_pairs'],3)
        self.assertEqual(r['above_90_degrees'],1)
        self.assertAlmostEqual(r['face_angle_degrees_quantiles'][-1],160)
    def test_single_face_jump_audit_reports_no_adjacency(self):
        r=audit_face_normal_jumps(self.p[:3],[[0,1,2]])
        self.assertEqual(r['triangle_count'],1)
        self.assertEqual(r['adjacent_face_pairs'],0)
        self.assertEqual(r['face_angle_degrees_quantiles'],[])
    def test_fractional_skin_binding_and_anchor_indices_are_rejected(self):
        for faces,triangle,allowed in [(self.f+.1,[0],[0]),(self.f,[.5],[0]),(self.f,[0],[.5])]:
            with self.assertRaises(ValueError):transfer_skin_colors(faces,self.uv,self.image,triangle,[[1,0,0]],allowed)
        with self.assertRaises(ValueError):transfer_lid_anchor_colors(self.f,self.uv,self.image,[0],[[1,0,0]],[.5],[0])
        with self.assertRaises(ValueError):audit_source_uv_charts(self.p,self.f+.1,self.uv,1e-7)
    def test_empty_color_transfer_and_uv_audit_are_rejected(self):
        with self.assertRaises(ValueError):transfer_skin_colors(self.f,self.uv,self.image,[],np.empty((0,3)),[0])
        with self.assertRaises(ValueError):audit_source_uv_charts(self.p,np.empty((0,3),int),self.uv,1e-7)
        with self.assertRaises(ValueError):audit_uv_chart_excursions(self.image,self.uv,np.empty((0,3),int))
    def test_nan_excursion_threshold_cannot_return_zero_failures(self):
        for tolerance in [np.nan,np.inf,-1]:
            with self.assertRaises(ValueError):audit_uv_chart_excursions(self.image,self.uv,self.f,tolerance)
    def test_quantization_overflow_is_rejected(self):
        with np.errstate(over='ignore',invalid='ignore'):
            with self.assertRaises(ValueError):audit_source_uv_charts(self.p,self.f,self.uv,1e-300)
    def test_color_output_must_be_normalized_and_nonempty(self):
        with self.assertRaises(ValueError):interpolate_skin_color_strip([0,1],[[2,0,0,1],[1,1,1,1]],[.5])
        with self.assertRaises(ValueError):interpolate_skin_color_strip([0,1],[[0,0,0,1],[1,1,1,1]],[])
        with self.assertRaises(ValueError):blend_skin_boundary_colors(self.p,self.f,[0.5],[2],np.ones((4,4)),np.ones((4,4)))
    def test_decoded_array_preservation_does_not_claim_encoded_image_audit(self):
        before=self.image.copy();result=transfer_skin_colors(self.f,self.uv,self.image,[0],[[1,0,0]],[0])
        self.assertTrue(np.array_equal(self.image,before))
        self.assertTrue(result['source_image_unchanged'])
        self.assertFalse(result['source_encoded_image_bytes_audited'])

if __name__=='__main__':unittest.main()
