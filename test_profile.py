# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import copy,json,tempfile,unittest
from pathlib import Path
from head_repair.config import load
from head_repair.audit import evaluate

class ProfileContract(unittest.TestCase):
    def setUp(self):self.path=Path(__file__).parent/'profiles/original-head.json';self.p,_=load(self.path)
    def passing(self):return {n:r['value'] for n,r in self.p['audit']['rules'].items()}
    def test_prior_fold_is_rejected_even_with_closure_pass(self):
        m=self.passing();m['quad_normal_max_degrees']=171.4766
        self.assertFalse(evaluate(self.p,m,{n:True for n in self.p['audit']['visual_required']})['accepted'])
    def test_missing_evidence_and_visual_review_do_not_pass(self):
        self.assertFalse(evaluate(self.p,{})['numeric_pass'])
        self.assertFalse(evaluate(self.p,self.passing())['accepted'])
    def test_threshold_travels_with_profile(self):
        m=self.passing();m['quad_normal_max_degrees']=70
        self.assertTrue(evaluate(self.p,m)['numeric_pass'])
        p=copy.deepcopy(self.p);p['audit']['rules']['quad_normal_max_degrees']['value']=60
        self.assertFalse(evaluate(p,m)['numeric_pass'])
    def test_retry_changes_parameter_without_mutating_base(self):
        raw=self.path.read_bytes();p,diff=load(self.path,['geometry.eyes.rows=16'])
        self.assertEqual(p['geometry']['eyes']['rows'],16);self.assertEqual(len(diff),1);self.assertEqual(self.path.read_bytes(),raw)
        with self.assertRaises(ValueError):load(self.path,['geometry.eyes.typo=16'])
    def test_invalid_geometry_setting_is_rejected(self):
        for value in ['geometry.eyes.z_step=0','geometry.eyes.depth_mode="typo"','geometry.eyes.row_sampling="typo"']:
            with self.assertRaises(ValueError):load(self.path,[value])

if __name__=='__main__':unittest.main()
