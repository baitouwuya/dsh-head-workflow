# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native_stage_export import plan_head_assembly


class NativeHeadAssemblyTests(unittest.TestCase):
    def test_unrigged_source_and_all_generated_parts_share_rigid_root(self):
        hierarchy=[{'source_object':'input-parent','export_object':'copied-parent','type':'EMPTY','parent_source':None},
                   {'source_object':'input-mesh','export_object':'copied-mesh','type':'MESH','parent_source':'input-parent'}]
        plan=plan_head_assembly(hierarchy,['upper','lower','cover'])
        self.assertEqual(plan['source_dependency_roots'],['copied-parent'])
        self.assertEqual(plan['generated_objects'],['upper','lower','cover'])
        self.assertEqual(plan['generated_attachment']['kind'],'rigid_assembly')
        self.assertFalse(plan['source_rigged'])

    def test_all_independent_dependency_roots_are_included(self):
        hierarchy=[{'source_object':name,'export_object':name,'type':'MESH','parent_source':None} for name in ('mesh','dependency')]
        self.assertEqual(plan_head_assembly(hierarchy,['lid'])['source_dependency_roots'],['mesh','dependency'])

    def test_rigged_source_requires_measured_bone_binding(self):
        hierarchy=[{'source_object':'measured-rig','export_object':'copied-rig','type':'ARMATURE','parent_source':None,'bones':['measured-head']}]
        with self.assertRaisesRegex(ValueError,'measured native_generated_binding'):plan_head_assembly(hierarchy,['lid'])
        binding={'kind':'bone','source_armature':'measured-rig','bone':'measured-head','evidence_path':'runtime-measurement.json'}
        plan=plan_head_assembly(hierarchy,['lid','cover'],binding)
        self.assertEqual(plan['generated_attachment']['parent_object'],'copied-rig')
        self.assertEqual(plan['generated_attachment']['bone'],'measured-head')
        binding['bone']='invented-head'
        with self.assertRaisesRegex(ValueError,'existing source armature bone'):plan_head_assembly(hierarchy,['lid'],binding)

    def test_incomplete_source_hierarchy_is_not_silently_flattened(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):
            plan_head_assembly([{'source_object':'mesh','export_object':'mesh','parent_source':'missing'}],['lid'])


if __name__=='__main__':unittest.main()
