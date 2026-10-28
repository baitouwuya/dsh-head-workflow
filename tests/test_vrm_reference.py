# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic GLB fixtures only; the operator's VRM is never a test asset."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
import numpy as np
from head_workflow.reference.vrm import GLB,VRMReference
from head_workflow.reference.fit import validate,fit_lid_profile,evaluate_lid
from head_workflow.reference.quality import closure_metrics

ROOT=Path(__file__).resolve().parents[1]


def pack_glb(g,buffer):
    g=copy.deepcopy(g)
    g['buffers']=[{'byteLength':len(buffer)}]
    raw=json.dumps(g).encode()
    raw+=b' '*((-len(raw))%4)
    buf=buffer+b'\0'*((-len(buffer))%4)
    chunks=struct.pack('<II',len(raw),0x4e4f534a)+raw+struct.pack('<II',len(buf),0x004e4942)+buf
    return struct.pack('<III',0x46546c67,2,len(chunks)+12)+chunks


def synthetic_vrm():
    arrays=[np.array([[0,1,0],[1,1,0],[0,2,0]],dtype='<f4'),
            np.array([[0,.1,.2],[0,.2,.3],[0,.3,.4]],dtype='<f4'),
            np.array([[0,0,.1],[0,0,.1],[0,0,.1]],dtype='<f4'),
            np.array([0,1,2],dtype='<u2')]
    buf=b'';views=[];accessors=[]
    for a in arrays:
        buf+=b'\0'*((-len(buf))%4)
        views.append({'buffer':0,'byteOffset':len(buf),'byteLength':a.nbytes})
        accessors.append({'bufferView':len(views)-1,'componentType':5126 if a.dtype.kind=='f' else 5123,
                          'type':'VEC3' if a.ndim==2 else 'SCALAR','count':len(a)})
        buf+=a.tobytes()
    exp={'isBinary':False,'morphTargetBinds':[{'node':0,'index':0,'weight':.5},{'node':0,'index':1,'weight':.25}]}
    g={'asset':{'version':'2.0'},'accessors':accessors,'bufferViews':views,
       'nodes':[{'mesh':0}], 'materials':[{'name':'FaceEyeline'}],
       'meshes':[{'extras':{'targetNames':['CloseA','CloseB']},'primitives':[
           {'attributes':{'POSITION':0},'indices':3,'material':0,'targets':[{'POSITION':1},{'POSITION':2}]}]}],
       'extensions':{'VRMC_vrm':{'expressions':{'preset':{'blink':exp}}}}}
    return g,buf,arrays


class GLBReaderTests(unittest.TestCase):
    def test_dense_and_strided_accessors(self):
        g,buf,a=synthetic_vrm()
        reader=GLB(pack_glb(g,buf))
        np.testing.assert_array_equal(reader.accessor(0),a[0])
        interleaved=np.column_stack([a[0],np.zeros(3)]).astype('<f4')
        g['bufferViews']=[{'buffer':0,'byteLength':interleaved.nbytes,'byteStride':16}]
        g['accessors']=[{'bufferView':0,'type':'VEC3','componentType':5126,'count':3}]
        np.testing.assert_array_equal(GLB(pack_glb(g,interleaved.tobytes())).accessor(0),a[0])

    def test_sparse_zero_base_and_invalid_indices(self):
        indices=bytes([1,2,0,0]);values=np.array([[1,2,3],[4,5,6]],dtype='<f4').tobytes()
        g={'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':2},{'buffer':0,'byteOffset':4,'byteLength':24}],
           'accessors':[{'count':3,'type':'VEC3','componentType':5126,'sparse':{'count':2,
              'indices':{'bufferView':0,'componentType':5121},'values':{'bufferView':1}}}]}
        np.testing.assert_array_equal(GLB(pack_glb(g,indices+values)).accessor(0),[[0,0,0],[1,2,3],[4,5,6]])
        for bad in (bytes([1,1,0,0]),bytes([1,3,0,0]),bytes([2,1,0,0])):
            with self.assertRaises(ValueError):GLB(pack_glb(g,bad+values)).accessor(0)

    def test_corrupt_headers_bounds_and_nonfinite_fail(self):
        g,buf,a=synthetic_vrm();raw=pack_glb(g,buf)
        for bad in (raw[:-1],b'bad',b'bad!'+raw[4:]):
            with self.assertRaises(ValueError):GLB(bad)
        broken=copy.deepcopy(g);broken['bufferViews'][0]['byteLength']=1
        with self.assertRaises(ValueError):GLB(pack_glb(broken,buf)).accessor(0)
        broken=copy.deepcopy(g);broken['bufferViews'][0]['byteStride']=8
        with self.assertRaises(ValueError):GLB(pack_glb(broken,buf)).accessor(0)
        invalid=np.array([float('nan')],dtype='<f4').tobytes()+buf[4:]
        with self.assertRaises(ValueError):GLB(pack_glb(g,invalid)).accessor(0)
        with self.assertRaises(ValueError):GLB(raw).accessor(-1)


class VRMAdapterTests(unittest.TestCase):
    def reference(self,change=None):
        g,buf,arrays=synthetic_vrm()
        if change:change(g)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'synthetic.vrm';path.write_bytes(pack_glb(g,buf))
            return VRMReference(path)

    def test_native_binding_weights_and_axis_conversion(self):
        ref=self.reference();_,_,a=synthetic_vrm()
        for w in (0,.25,.5,.75,1):
            got,faces=ref.evaluate({},w)
            expected=(a[0]+w*(.5*a[1]+.25*a[2]))@ref.axis.T
            np.testing.assert_allclose(got,expected,atol=2e-7)
            np.testing.assert_array_equal(faces,[[0,1,2]])
        self.assertEqual(ref.provenance({})['morph_targets'],['CloseA','CloseB'])
        self.assertEqual(ref.lash_region,'FaceEyeline')

    def test_no_silent_pd_controls_or_bad_weights(self):
        ref=self.reference()
        with self.assertRaises(ValueError):ref.evaluate({'Eye Size Y':.5},0)
        for w in (-1,1.1,float('nan')):
            with self.assertRaises(ValueError):ref.evaluate({},w)

    def test_binary_transformed_or_default_morphed_models_rejected(self):
        changes=[lambda g:g['extensions']['VRMC_vrm']['expressions']['preset']['blink'].update(isBinary=True),
                 lambda g:g['nodes'][0].update(translation=[1,0,0]),
                 lambda g:g['meshes'][0].update(weights=[1,0]),
                 lambda g:g['meshes'][0]['primitives'][0].update(mode=5)]
        for change in changes:
            with self.assertRaises(ValueError):self.reference(change)

    def test_multiple_expression_nodes_and_split_streams_rejected(self):
        def nodes(g):g['extensions']['VRMC_vrm']['expressions']['preset']['blink']['morphTargetBinds'][1]['node']=1
        def streams(g):
            p=copy.deepcopy(g['meshes'][0]['primitives'][0]);p['attributes']['POSITION']=1
            g['meshes'][0]['primitives'].append(p)
        for change in (nodes,streams):
            with self.assertRaises(ValueError):self.reference(change)
        with self.assertRaises(ValueError):self.reference(lambda g:g['extensions']['VRMC_vrm']['expressions']['preset']['blink']['morphTargetBinds'][0].update(index=-1))


class NativeProfileTests(unittest.TestCase):
    def load(self,name):
        return json.loads((ROOT/'profiles/reference'/name).read_text(encoding='utf-8-sig'))

    def test_native_profile_and_fit(self):
        profile=validate(self.load('base-vrm.json'))
        self.assertEqual(profile['provenance']['expression'],'blink')
        self.assertEqual(profile['provenance']['morph_targets'],['Fcl_EYE_Close'])
        self.assertEqual(profile['provenance']['band_source'],'FaceEyeline')
        fitted=fit_lid_profile(profile)
        for side,eye in fitted['eyes'].items():
            self.assertLess(eye['fit_rms'],.0013)
            self.assertLess(eye['fit_max'],.006)
            self.assertIsNone(eye['lid_thickness']['physical_thickness'])
            pose=evaluate_lid(fitted,side,.625,np.linspace(0,1,65))
            np.testing.assert_allclose(pose['lash'],pose['anchor_origin']+np.einsum('nji,nj->ni',pose['anchor_axes'],pose['anchor_offsets']),atol=1e-12)

    def test_closure_measured_before_reduction_improves_surrogate(self):
        r=self.load('base-vrm-verification.json')
        for side in ('positive_x','negative_x'):
            native=r['native_blink']['eyes'][side][-1]
            joy=r['pd_eye_joy']['eyes'][side][-1]
            self.assertLess(native['rms_height_gap'],joy['rms_height_gap']*.2)
            self.assertLess(native['max_positive_gap'],.003)
            self.assertLess(native['max_overlap'],.025)
        self.assertGreater(r['bilateral_minus_left_plus_right_max_error_eye_widths'],.1)

    def test_live_report_distinguishes_supported_blink_from_pd_shaping(self):
        r=self.load('base-vrm-verification.json')['live_experiment']
        self.assertTrue(r['test_passed'])
        self.assertTrue(r['native_blink_import_parity']['passed'])
        self.assertFalse(r['direct_pd_driving_supported'])
        self.assertFalse(r['topology']['index_transfer_compatible'])
        for trial in r['pd_shaping_trials']:
            self.assertGreater(trial['template_max_motion_in_reference_eye_widths'],.01)
            self.assertEqual(trial['imported_vrm_max_motion_eye_widths'],0.)
            self.assertEqual(trial['imported_vrm_evaluated_max_motion_eye_widths'],0.)
        self.assertTrue(all(r['datablock_sets_restored'].values()))
        self.assertTrue(r['scene_selection_restored'])
        self.assertTrue(r['pd_properties_restored'])

    def test_quality_reports_gap_overlap_and_depth_separately(self):
        up=np.array([[-.5,.1,.03],[.5,.1,.03]])
        lo=np.array([[-.5,0.,0.],[.5,0.,0.]])
        report=closure_metrics(up,lo)
        self.assertAlmostEqual(report['max_positive_gap'],.1)
        self.assertAlmostEqual(report['max_absolute_depth_difference'],.03)
        self.assertEqual(report['max_overlap'],0.)
        self.assertAlmostEqual(closure_metrics(lo,up)['max_overlap'],.1)


if __name__=='__main__':unittest.main()
