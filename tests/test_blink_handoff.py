# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest
import numpy as np
from lab_recipes.blink_handoff import audit_neutral_and_near_neutral,audit_component_binding,linear_triangle_area_minimum,audit_linear_morph_segments

class BlinkHandoffChecks(unittest.TestCase):
    def setUp(self):self.p=np.array([[0.,0,0],[1,0,0],[0,1,0]])
    def test_neutral_identity_catches_unweighted_clearance(self):
        result=audit_neutral_and_near_neutral(lambda v:self.p+[.01,0,v],self.p,[1e-6,.01],1e-9)
        self.assertFalse(result['neutral_identity_pass'])
    def test_continuous_interpolation_reports_near_zero_response(self):
        result=audit_neutral_and_near_neutral(lambda v:self.p+[0,0,v],self.p,[1e-6,.01,.25],1e-9)
        self.assertTrue(result['neutral_identity_pass'])
        self.assertAlmostEqual(result['samples'][1]['maximum_displacement'],1e-6)
    def test_static_moving_lash_mask_edge_is_reported(self):
        target=self.p.copy();target[1,0]=10
        r=audit_component_binding(self.p,target,[[0,1,2]],[False,True,False],movement_tolerance=1e-9,minimum_edge_length=1e-9,stretch_limit=3)
        self.assertEqual(r['partially_masked_components'],1)
        self.assertEqual(r['mask_cut_edges'],2)
        self.assertEqual(r['moving_static_edges'],2)
        self.assertEqual(r['stretch_limit_exceedances'],2)
        self.assertEqual(r['maximum_edge_stretch_ratio'],10)
    def test_rigid_rotation_is_not_torn_or_collapsed(self):
        a=np.radians(120);rotation=np.array([[1,0,0],[0,np.cos(a),-np.sin(a)],[0,np.sin(a),np.cos(a)]])
        target=self.p@rotation.T
        r=audit_component_binding(self.p,target,[[0,1,2]],[True]*3,movement_tolerance=1e-9,minimum_edge_length=1e-9,stretch_limit=1.01)
        self.assertEqual(r['mask_cut_edges'],0)
        self.assertEqual(r['stretch_limit_exceedances'],0)
        area=linear_triangle_area_minimum(self.p,target)
        self.assertTrue(area['reference_normal_reversal'])
        self.assertAlmostEqual(area['minimum_area_ratio'],.5)
    def test_valid_endpoints_can_hide_interior_collapse(self):
        target=self.p.copy();target[2,1]=-1
        r=linear_triangle_area_minimum(self.p,target)
        self.assertEqual(r['initial_double_area'],1)
        self.assertEqual(r['final_double_area'],1)
        self.assertAlmostEqual(r['minimum_double_area'],0)
        self.assertAlmostEqual(r['at'],.5)
    def test_threshold_is_explicit_not_hidden(self):
        r=audit_component_binding(self.p,self.p*10,[[0,1,2]],[True]*3,movement_tolerance=1e-9,minimum_edge_length=1e-9)
        self.assertIsNone(r['stretch_limit'])
        self.assertIsNone(r['stretch_limit_exceedances'])
    def test_invalid_geometry_rejected(self):
        with self.assertRaises(ValueError):linear_triangle_area_minimum(np.full((3,3),np.nan),self.p)
    def test_seam_canonical_ids_join_components(self):
        p=np.vstack([self.p,self.p])
        r=audit_component_binding(p,p,[[0,1,2],[3,4,5]],[True]*3+[False]*3,movement_tolerance=1e-9,minimum_edge_length=1e-9,canonical_ids=[0,1,2,0,4,5],canonical_tolerance=1e-9)
        self.assertEqual(r['component_count'],1)
        self.assertEqual(r['partially_masked_components'],1)
        self.assertFalse(r['canonical_consistency_pass'])
        self.assertEqual(r['canonical_mask_conflict_count'],1)

    def test_nonfinite_runtime_thresholds_rejected(self):
        for bad in [float('nan'),float('inf'),-float('inf')]:
            with self.assertRaises(ValueError):audit_neutral_and_near_neutral(lambda v:self.p,self.p,[.01],bad)
            for key in ['movement_tolerance','minimum_edge_length','stretch_limit']:
                args=dict(movement_tolerance=1e-9,minimum_edge_length=1e-9,stretch_limit=3);args[key]=bad
                with self.assertRaises(ValueError):audit_component_binding(self.p,self.p,[[0,1,2]],[True]*3,**args)

    def test_fractional_triangle_indices_are_not_truncated(self):
        with self.assertRaises(ValueError):audit_component_binding(self.p,self.p,[[0,1.5,2]],[True]*3,movement_tolerance=0,minimum_edge_length=0)

    def test_area_extrema_translation_and_scale_invariant(self):
        target=self.p.copy();target[2]=[0,-.5,.5]
        reference=linear_triangle_area_minimum(self.p,target)
        for scale in [1e-6,1.,1e6]:
            offset=np.array([1.2,-3.4,5.6])*scale
            actual=linear_triangle_area_minimum(self.p*scale+offset,target*scale+offset)
            self.assertAlmostEqual(actual['at'],reference['at'],places=10)
            self.assertAlmostEqual(actual['minimum_area_ratio'],reference['minimum_area_ratio'],places=10)
            self.assertAlmostEqual(actual['minimum_double_area']/(scale*scale),reference['minimum_double_area'],places=10)

    def test_segment_audit_maps_control_value_and_excludes_inherited(self):
        basis=np.vstack([self.p,[[2,0,0],[2,0,0],[2,0,0]]]);target=basis.copy();target[2,1]=-1
        r=audit_linear_morph_segments(basis,[[0,1,2],[3,4,5]],[0,.25],[basis,target],source_double_area_floor=1e-12,collapse_area_ratio=1e-6)
        self.assertEqual(r['newly_collapsed_face_count'],1)
        self.assertEqual(r['inherited_source_degenerate_faces'],1)
        self.assertEqual(r['collapse_events'][0]['triangle_index'],0)
        self.assertAlmostEqual(r['collapse_events'][0]['control_value'],.125)

    def test_segment_audit_accepts_rotation_without_collapse(self):
        a=np.radians(120);rotation=np.array([[1,0,0],[0,np.cos(a),-np.sin(a)],[0,np.sin(a),np.cos(a)]])
        r=audit_linear_morph_segments(self.p,[[0,1,2]],[0,1],[self.p,self.p@rotation.T],source_double_area_floor=1e-12,collapse_area_ratio=1e-6)
        self.assertEqual(r['newly_collapsed_face_count'],0)
        self.assertEqual(r['segments'][0]['reference_normal_reversals_diagnostic_only'],1)

    def test_empty_required_geometry_rejected(self):
        empty=np.empty((0,3));triangles=np.empty((0,3),dtype=int)
        with self.assertRaises(ValueError):audit_neutral_and_near_neutral(lambda v:empty,empty,[.01],1e-9)
        with self.assertRaises(ValueError):audit_component_binding(self.p,self.p,triangles,[True]*3,movement_tolerance=0,minimum_edge_length=0)
        with self.assertRaises(ValueError):audit_linear_morph_segments(empty,triangles,[0,1],[empty,empty],source_double_area_floor=0,collapse_area_ratio=1e-6)

    def test_no_source_valid_faces_rejected(self):
        degenerate=np.zeros((3,3))
        with self.assertRaisesRegex(ValueError,'No source-valid'):
            audit_linear_morph_segments(degenerate,[[0,1,2]],[0,1],[degenerate,degenerate],source_double_area_floor=0,collapse_area_ratio=1e-6)

    def test_canonical_sentinel_and_missing_tolerance_rejected(self):
        for ids,tolerance in [([-1,-1,-1],1e-9),([0,1,2],None)]:
            with self.assertRaises(ValueError):audit_component_binding(self.p,self.p,[[0,1,2]],[True]*3,movement_tolerance=0,minimum_edge_length=0,canonical_ids=ids,canonical_tolerance=tolerance)
        for bad in [float('nan'),float('inf'),-1]:
            with self.assertRaises(ValueError):audit_component_binding(self.p,self.p,[[0,1,2]],[True]*3,movement_tolerance=0,minimum_edge_length=0,canonical_ids=[0,1,2],canonical_tolerance=bad)

    def test_translated_duplicate_island_reports_seam_tear(self):
        basis=np.vstack([self.p,self.p]);posed=basis.copy();posed[3:]+=[0,0,10]
        r=audit_component_binding(basis,posed,[[0,1,2],[3,4,5]],[True]*6,movement_tolerance=1e-9,minimum_edge_length=1e-9,stretch_limit=1.01,canonical_ids=[0,1,2,0,4,5],canonical_tolerance=1e-8)
        self.assertEqual(r['component_count'],1)
        self.assertEqual(r['partially_masked_components'],0)
        self.assertEqual(r['maximum_edge_stretch_ratio'],1)
        self.assertFalse(r['canonical_consistency_pass'])
        self.assertEqual(r['canonical_conflict_counts'],{'rest_gap':0,'posed_gap':1,'displacement_gap':1})
        self.assertEqual(r['canonical_worst_groups'][0]['posed_gap'],10)

    def test_rest_id_conflict_is_reported(self):
        basis=np.vstack([self.p,self.p+[0,0,10]])
        r=audit_component_binding(basis,basis,[[0,1,2],[3,4,5]],[True]*6,movement_tolerance=0,minimum_edge_length=0,canonical_ids=[0,1,2,0,4,5],canonical_tolerance=1e-8)
        self.assertFalse(r['canonical_consistency_pass'])
        self.assertEqual(r['canonical_conflict_counts']['rest_gap'],1)
        self.assertEqual(r['canonical_conflict_counts']['displacement_gap'],0)

    def test_duplicate_vertices_moving_together_are_consistent(self):
        basis=np.vstack([self.p,self.p]);posed=basis+[0,0,10]
        r=audit_component_binding(basis,posed,[[0,1,2],[3,4,5]],[True]*6,movement_tolerance=0,minimum_edge_length=0,canonical_ids=[0,1,2,0,4,5],canonical_tolerance=1e-8)
        self.assertTrue(r['canonical_consistency_pass'])
        self.assertEqual(r['referenced_vertex_count'],6)
        self.assertEqual(r['triangle_count'],2)

    def test_segment_audit_exposes_source_counts(self):
        basis=np.vstack([self.p,np.zeros((3,3))])
        r=audit_linear_morph_segments(basis,[[0,1,2],[3,4,5]],[0,1],[basis,basis],source_double_area_floor=1e-12,collapse_area_ratio=1e-6)
        self.assertEqual(r['source_face_count'],2)
        self.assertEqual(r['source_valid_face_count'],1)

if __name__=='__main__':unittest.main()
