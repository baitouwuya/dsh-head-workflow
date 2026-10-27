# SPDX-License-Identifier: GPL-3.0-or-later
"""Renderer contract tests only: no Blender import or execution on the test host."""
import builtins
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock


def load_renderer_without_native_imports():
    real_import=builtins.__import__
    def guarded(name,*args,**kwargs):
        if name in ('bpy','mathutils') or name.startswith(('bpy.','mathutils.')):
            raise AssertionError('Native Blender imports are forbidden in these tests')
        return real_import(name,*args,**kwargs)
    path=Path(__file__).resolve().parents[1]/'tools/native_render_verification.py'
    with mock.patch('builtins.__import__',side_effect=guarded):
        spec=importlib.util.spec_from_file_location('native_render_contract',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


renderer=load_renderer_without_native_imports()


def mesh(name,values):
    keys=[SimpleNamespace(name=key,value=value) for key,value in values.items()]
    return SimpleNamespace(name=name,type='MESH',data=SimpleNamespace(shape_keys=SimpleNamespace(key_blocks=keys)))


def values(obj):
    return {key.name:key.value for key in obj.data.shape_keys.key_blocks}


class NativeRenderControlTests(unittest.TestCase):
    def setUp(self):
        self.mapping={'left':[{'value':.25,'name':'close-left-quarter'},{'value':1,'name':'close-left-full'}],
                      'right':[{'value':1,'name':'close-right-full'}]}
        self.obj=mesh('head',{'Basis':0.,'close-left-quarter':.8,'close-left-full':.2,
                              'close-right-full':.9,'jaw-existing':.35,'expression-existing':.7})

    def test_import_is_pure_without_loading_blender(self):
        module=load_renderer_without_native_imports()
        self.assertIsNone(module.bpy);self.assertIsNone(module.Matrix);self.assertIsNone(module.Vector)

    def test_only_configured_blink_values_change(self):
        result=renderer.apply_control_values([self.obj],self.mapping,{'left':.625})
        actual=values(self.obj)
        self.assertEqual(actual['close-left-quarter'],.5);self.assertEqual(actual['close-left-full'],.5)
        self.assertEqual(actual['close-right-full'],0.)
        self.assertEqual(actual['jaw-existing'],.35);self.assertEqual(actual['expression-existing'],.7)
        self.assertEqual(actual['Basis'],0.)
        self.assertFalse(result['unrelated_morph_values_changed'])

    def test_neutral_reset_preserves_unrelated_values(self):
        renderer.apply_control_values([self.obj],self.mapping,{'left':1,'right':1})
        renderer.apply_control_values([self.obj],self.mapping,{})
        actual=values(self.obj)
        self.assertTrue(all(actual[name]==0 for name in ['close-left-quarter','close-left-full','close-right-full']))
        self.assertEqual(actual['jaw-existing'],.35);self.assertEqual(actual['expression-existing'],.7)

    def test_every_raw_invalid_knot_is_rejected_before_filtering_or_mesh_lookup(self):
        for bad in (-1,0,float('nan'),float('inf'),-float('inf'),1.1,'0.25',True,None):
            with self.subTest(raw=bad):
                mapping={'left':[{'value':bad,'name':'invalid'},{'value':1,'name':'valid'}]}
                with self.assertRaises(ValueError):renderer.apply_control_values([],mapping,{})

    def test_duplicate_weights_or_morph_names_rejected(self):
        cases=[{'left':[{'value':1,'name':'a'},{'value':1,'name':'b'}]},
               {'left':[{'value':.25,'name':'a'},{'value':1,'name':'a'}]},
               {'left':[{'value':1,'name':'shared'}],'right':[{'value':1,'name':'shared'}]}]
        for mapping in cases:
            with self.subTest(mapping=mapping),self.assertRaises(ValueError):renderer.validate_controller(mapping)

    def test_missing_end_empty_name_and_malformed_knots_rejected(self):
        cases=[{'left':[]},{'left':[{'value':.5,'name':'a'}]},
               {'left':[{'value':1,'name':''}]},{'left':[{'value':1,'name':'   '}]},
               {'left':[{'value':1,'name':None}]},{'left':[{'value':1}]},
               {'left':['not-a-knot']},{'left':'not-a-list'},[]]
        for mapping in cases:
            with self.subTest(mapping=mapping),self.assertRaises(ValueError):renderer.validate_controller(mapping)

    def test_valid_unsorted_knots_normalized_only_after_validation(self):
        mapping={'left':[{'value':1,'name':'full'},{'value':.25,'name':'quarter'}]};before=copy.deepcopy(mapping)
        self.assertEqual(renderer.validate_controller(mapping)['left'],((.25,'quarter'),(1.,'full')))
        self.assertEqual(mapping,before)

    def test_bad_values_and_unknown_controls_fail_without_mutation(self):
        before=values(self.obj)
        for requested in ({'left':True},{'left':'1'},{'left':float('nan')},{'left':-1},{'left':1.1},{'unknown':1},None):
            with self.subTest(requested=requested),self.assertRaises(ValueError):
                renderer.apply_control_values([self.obj],self.mapping,requested)
            self.assertEqual(values(self.obj),before)

    def test_partial_active_mapping_on_one_mesh_is_not_hidden_by_another(self):
        partial=mesh('partial',{'Basis':0.,'close-left-full':.3,'jaw-existing':.2})
        before=values(self.obj);partial_before=values(partial)
        with self.assertRaisesRegex(ValueError,'incomplete'):
            renderer.apply_control_values([self.obj,partial],self.mapping,{'left':.5})
        self.assertEqual(values(self.obj),before);self.assertEqual(values(partial),partial_before)

    def test_source_without_candidate_knots_can_render_neutral_unchanged(self):
        source=mesh('source',{'Reference':0.,'jaw-existing':.45})
        renderer.apply_control_values([source],self.mapping,{})
        self.assertEqual(values(source),{'Reference':0.,'jaw-existing':.45})

    def test_missing_active_control_and_reference_basis_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'absent'):
            renderer.apply_control_values([],self.mapping,{'left':1})
        source=mesh('source',{'Reference':0.,'jaw-existing':.45})
        with self.assertRaisesRegex(ValueError,'reference basis'):
            renderer.apply_control_values([source],{'left':[{'value':1,'name':'Reference'}]}, {})

    def test_wrapper_uses_same_contract_with_fake_scene_only(self):
        update=mock.Mock();fake=SimpleNamespace(context=SimpleNamespace(scene=SimpleNamespace(objects=[self.obj]),view_layer=SimpleNamespace(update=update)))
        with mock.patch.object(renderer,'bpy',fake):renderer.set_controls(self.mapping,{'right':1})
        self.assertEqual(values(self.obj)['jaw-existing'],.35);self.assertEqual(values(self.obj)['close-right-full'],1)
        update.assert_called_once_with()

    def test_invalid_request_fails_before_native_runtime_initialization(self):
        request={'controller':{'left':[{'value':-1,'name':'bad'},{'value':1,'name':'full'}]},'states':[]}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'request.json';path.write_text(json.dumps(request))
            with mock.patch.object(renderer,'load_native_runtime',side_effect=AssertionError('No native runtime allowed')):
                with self.assertRaises(ValueError):renderer.main(path)


if __name__=='__main__':unittest.main()
