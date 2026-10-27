# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import full_look_review
import native_stage_export
from native_stage_export import enum_option_supported


class NativeExportCompatibilityTests(unittest.TestCase):
    def test_dynamic_enum_defers_validation_to_operator(self):
        self.assertTrue(enum_option_supported(SimpleNamespace(enum_items=[]),'GLB'))

    def test_static_enum_mismatch_stays_rejected(self):
        prop=SimpleNamespace(enum_items=[SimpleNamespace(identifier='GLB')])
        self.assertFalse(enum_option_supported(prop,'INVALID'))
        self.assertTrue(enum_option_supported(prop,'GLB'))

    def test_actual_export_call_requests_packed_image_embedding(self):
        # Stop at the operator boundary: no Blender import/execution, asset
        # export, or mock claim of image-byte fidelity. The native run supplies
        # that evidence; this test guards its exact compatibility options.
        class ReachedExporter(Exception):pass
        calls=[]
        class Exporter:
            def get_rna_type(self):
                names=['filepath','export_format','use_selection','use_active_scene','export_skins','export_morph','export_morph_normal','export_normals','export_animations','export_apply','export_image_format','export_keep_originals','export_all_vertex_colors','export_extras']
                return SimpleNamespace(properties=[SimpleNamespace(identifier=name,type='ENUM' if name in ('export_format','export_image_format') else 'OTHER',enum_items=[]) for name in names])
            def __call__(self,**options):calls.append(options);raise ReachedExporter()
        fake_bpy=SimpleNamespace(context=SimpleNamespace(window=None,view_layer=SimpleNamespace(objects=SimpleNamespace(active=None),update=lambda:None)),ops=SimpleNamespace(export_scene=SimpleNamespace(gltf=Exporter())))
        key='export-compatibility-test';session={'request':{'mode':'native_stage_build','native_build_provenance':{'input_artifact_id':'runtime-input','repository_commit':'runtime-revision','construction_report_path':'runtime-report'}},'scene':SimpleNamespace(objects=[]),'source_object':object()}
        with tempfile.TemporaryDirectory() as output,patch.dict(full_look_review.SESSIONS,{key:session}),patch.dict(sys.modules,{'bpy':fake_bpy}),patch.object(full_look_review,'_set_state'),patch.object(native_stage_export,'_preserve_hierarchy',return_value=[]),patch.object(native_stage_export,'_assemble_rigid_head',return_value={}):
            with self.assertRaises(ReachedExporter):native_stage_export.export_native_session(key,output)
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0]['export_format'],'GLB')
        self.assertEqual(calls[0]['export_image_format'],'AUTO')
        self.assertIs(calls[0]['export_keep_originals'],False)


if __name__=='__main__':unittest.main()
