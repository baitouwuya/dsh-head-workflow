# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic fixtures only. Host checks separately exercise the real PD loader/UI."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
from head_workflow.pd_pack.convert import convert, graph
from head_workflow.pd_pack.runtime import Runtime, expression_values
from test_vrm_reference import synthetic_vrm, pack_glb


class PackTests(unittest.TestCase):
    def make(self, root, mutate=None):
        g, buffer, arrays = synthetic_vrm()
        if mutate:
            mutate(g)
        source = Path(root)/'input.vrm'; source.write_bytes(pack_glb(g, buffer))
        out = Path(root)/'pack'
        summary = convert(source, out)
        return Runtime(out), summary, out, arrays

    def test_weighted_expression_and_axis_conversion(self):
        with tempfile.TemporaryDirectory() as root:
            rt, summary, out, arrays = self.make(root)
            self.assertEqual(summary['descriptors'], 1)
            for w in (0., .25, .5, .75, 1.):
                got = rt.evaluate({'vrm_blink': w})['meshes'][0][1]
                want = (arrays[0]+w*(.5*arrays[1]+.25*arrays[2])) @ np.array([[1,0,0],[0,0,-1],[0,1,0]]).T
                np.testing.assert_allclose(got, want, atol=2e-7)
            self.assertTrue((out/'py/driver.py').exists())
            self.assertEqual((out/'.gitignore').read_text(), '*\n')
            self.assertFalse((out/'materials.json').exists())

    def test_nonidentity_mesh_node_and_default_morph(self):
        with tempfile.TemporaryDirectory() as root:
            def change(g):
                g['nodes'][0].update(translation=[2,3,4], scale=[2,1,.5], weights=[.2,0])
            rt, _, _, arrays = self.make(root, change)
            expected=(arrays[0]+arrays[1]*.2)*[2,1,.5]+[2,3,4]
            np.testing.assert_allclose(rt.evaluate()['meshes'][0][1], expected[:,[0,2,1]]*[1,-1,1], atol=3e-7)

    def test_multiple_primitives_and_mesh_instances(self):
        with tempfile.TemporaryDirectory() as root:
            def change(g):
                other=copy.deepcopy(g['meshes'][0]['primitives'][0])
                other['attributes']['POSITION']=1  # deliberately distinct stream
                g['meshes'][0]['primitives'].append(other)
                g['nodes'].append({'mesh':0,'translation':[3,0,0]})
            rt, summary, _, _ = self.make(root, change)
            self.assertEqual(summary['descriptors'],4)
            a=rt.evaluate()['meshes'];b=rt.evaluate({'vrm_blink':1})['meshes']
            self.assertGreater(np.linalg.norm(b[0][1]-a[0][1]),0)
            np.testing.assert_array_equal(b[2][1],a[2][1])  # bind is to node 0, not every mesh instance

    def test_vrm0_mesh_binding_and_percent_weights(self):
        with tempfile.TemporaryDirectory() as root:
            def change(g):
                g['extensions']={'VRM':{'blendShapeMaster':{'blendShapeGroups':[{'presetName':'blink','binds':[{'mesh':0,'index':0,'weight':50}]}]}}}
            rt,_,_,arrays=self.make(root,change)
            np.testing.assert_allclose(rt.evaluate({'vrm_blink':1})['meshes'][0][1],(arrays[0]+.5*arrays[1])[:,[0,2,1]]*[1,-1,1],atol=2e-7)

    def test_existing_directory_and_unsupported_data_fail(self):
        with tempfile.TemporaryDirectory() as root:
            rt,_,out,_=self.make(root)
            with self.assertRaises(FileExistsError):convert(Path(root)/'input.vrm',out)
        changes=[lambda g:g['meshes'][0]['primitives'][0]['attributes'].update(JOINTS_1=0),
                 lambda g:g['meshes'][0]['primitives'][0].update(mode=1),
                 lambda g:g['extensions']['VRMC_vrm']['expressions']['preset']['blink'].update(materialColorBinds=[{'material':0}])]
        for change in changes:
            with tempfile.TemporaryDirectory() as root:
                with self.assertRaises(ValueError):self.make(root,change)
                self.assertFalse((Path(root)/'pack').exists())

    def test_parent_sorting_and_cycle_rejection(self):
        g={'nodes':[{'translation':[0,2,0]},{'children':[0],'translation':[1,0,0]}]}
        order,index,parents,names,local,world,active=graph(g)
        self.assertEqual(order,[1,0]);self.assertEqual(parents,[-1,0])
        np.testing.assert_allclose(world[1,:3,3],[1,2,0])
        with self.assertRaises(ValueError):graph({'nodes':[{'children':[1]},{'children':[0]}]})

    def test_skin_inverse_bind_and_pose(self):
        # Build a generated pack's skin payload from synthetic data, independently
        # of the converter's unskinned fixture, to exercise LBS plus parent FK.
        with tempfile.TemporaryDirectory() as root:
            rt,_,out,arrays=self.make(root)
            dpath=next((out/'meshes').glob('*.json'));d=json.loads(dpath.read_text())
            local=np.eye(4)[None];local[0,:3,3]=[1,0,0]
            np.save(out/'data/node_local_matrices.npy',local)
            payload={'bones':np.array([0]),'indices':np.zeros((3,4),dtype=int),
                     'weights':np.tile([1.,0,0,0],(3,1)), 'bindposes':np.linalg.inv(local)}
            for key,value in payload.items():
                np.save(out/f'data/{key}.npy',value);d[key]={'file':f'data/{key}.npy'}
            dpath.write_text(json.dumps(d))
            rt=Runtime(out)
            np.testing.assert_allclose(rt.evaluate()['meshes'][0][1],arrays[0][:,[0,2,1]]*[1,-1,1])
            moved=rt.evaluate(pose={'rotations':[[0,0,np.pi/2]]})['meshes'][0][1]
            expected=np.column_stack([1-arrays[0][:,1],np.zeros(3),arrays[0][:,0]-1])
            np.testing.assert_allclose(moved,expected,atol=1e-6)

    def test_invalid_runtime_controls_and_pose(self):
        with tempfile.TemporaryDirectory() as root:
            rt,_,_,_=self.make(root)
            for params,pose in [({'unknown':1},{}),({'vrm_blink':float('nan')},{}),({}, {'rotations':[[1,2]]}),({'morph_n0_000':2},{})]:
                with self.assertRaises(ValueError):rt.evaluate(params,pose)


class ExpressionTests(unittest.TestCase):
    def test_binary_threshold_and_overrides(self):
        e={'blink':{'preset':'blink'},'happy':{'preset':'happy','isBinary':True,'overrideBlink':'block'}}
        self.assertEqual(expression_values(e,{'blink':1,'happy':.5})['blink'],1)
        self.assertEqual(expression_values(e,{'blink':1,'happy':.51})['blink'],0)
        e['happy'].update(isBinary=False,overrideBlink='blend')
        self.assertAlmostEqual(expression_values(e,{'blink':.8,'happy':.25})['blink'],.6)
        e['blink']['isBinary']=True
        self.assertEqual(expression_values(e,{'blink':1,'happy':.01})['blink'],0)

    def test_procedural_cannot_override_itself_and_values_clamp(self):
        e={'blink':{'preset':'blink','overrideBlink':'block'}}
        self.assertEqual(expression_values(e,{'blink':2})['blink'],1)
        self.assertEqual(expression_values(e,{'blink':-1})['blink'],0)


if __name__=='__main__':unittest.main()
