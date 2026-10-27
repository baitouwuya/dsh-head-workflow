# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import copy,struct,unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native_glb_clips import pack_glb,unpack_glb,append_blink_cycles,read_weight_clip,sample_weight_track
from native_stage_export import _require_native


class NativeClipTests(unittest.TestCase):
    def setUp(self):
        self.mapping={'right':[{'value':.5,'name':'rhalf'},{'value':1.,'name':'rfull'}],'left':[{'value':.5,'name':'lhalf'},{'value':1.,'name':'lfull'}]}
        self.names=['smile','lfull','rhalf','lhalf','rfull']
        self.doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':4}],'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':3}],
                  'images':[{'bufferView':0,'mimeType':'image/jpeg'}],
                  'meshes':[{'primitives':[{'attributes':{},'targets':[{} for _ in self.names]}],'extras':{'targetNames':self.names},'weights':[.3,0,0,0,0]}],
                  'nodes':[{'mesh':0},{'mesh':0,'weights':[.8,0,0,0,0]}],
                  'animations':[{'name':'existing','samplers':[],'channels':[]}]}
        self.raw=pack_glb(self.doc,b'abc\0')
        self.scenarios=[{'id':'right-cycle','controls':['right']},{'id':'left-cycle','controls':['left']},{'id':'both-cycle','controls':['right','left']}]

    def output(self):
        return append_blink_cycles(self.raw,self.mapping,self.scenarios,[0,.25,.5,1,0],[0,.1,.2,.3,.4])

    def samples(self,doc,binary,animation,node):
        a=next(a for a in doc['animations'] if a['name']==animation);ch=next(c for c in a['channels'] if c['target']['node']==node);access=doc['accessors'][a['samplers'][ch['sampler']]['output']];view=doc['bufferViews'][access['bufferView']]
        values=struct.unpack_from('<'+'f'*access['count'],binary,view['byteOffset']);return [values[i:i+5] for i in range(0,len(values),5)]

    def test_target_name_mapping_and_rest_values(self):
        data,report=self.output();doc,b,_=unpack_glb(data)
        a=self.samples(doc,b,'right-cycle',0)
        self.assertAlmostEqual(a[0][0],.3);self.assertEqual(a[1][2],.5);self.assertEqual(a[2][2],1);self.assertEqual(a[3][4],1)
        self.assertTrue(all(row[1]==row[3]==0 for row in a))
        inst=self.samples(doc,b,'right-cycle',1);self.assertTrue(all(abs(row[0]-.8)<1e-6 for row in inst))
        self.assertEqual(list(a[-1][1:]),[0,0,0,0]);self.assertTrue(report['unrelated_rest_weights_preserved'])

    def test_independent_and_bilateral_cycles(self):
        data,_=self.output();doc,b,_=unpack_glb(data)
        left=self.samples(doc,b,'left-cycle',0);both=self.samples(doc,b,'both-cycle',0)
        self.assertEqual(left[3][1],1);self.assertEqual(left[3][4],0)
        self.assertEqual(both[3][1],1);self.assertEqual(both[3][4],1)

    def test_original_binary_images_and_animations_remain(self):
        data,report=self.output();doc,b,_=unpack_glb(data)
        self.assertEqual(b[:4],b'abc\0');self.assertEqual(doc['animations'][0],self.doc['animations'][0]);self.assertEqual(doc['images'],self.doc['images']);self.assertEqual(report['embedded_images'][0]['bytes'],3)

    def test_verifier_decodes_actual_serialized_values_between_keys(self):
        data,_=self.output();tracks=read_weight_clip(data,'right-cycle');sample=sample_weight_track(tracks[0],.15)
        self.assertAlmostEqual(sample[2],.75,places=6);self.assertAlmostEqual(sample[0],.3,places=6)
        self.assertEqual(tracks[0]['target_names'],self.names)
        with self.assertRaises(ValueError):read_weight_clip(data,'missing')

    def test_incomplete_controller_rejected(self):
        bad=copy.deepcopy(self.doc);bad['meshes'][0]['extras']['targetNames'][2]='unexpected'
        with self.assertRaisesRegex(ValueError,'Incomplete'):append_blink_cycles(pack_glb(bad,b'abc\0'),self.mapping,self.scenarios,[0,1,0],[0,.1,.2])

    def test_invalid_raw_knots_times_and_clip_names_rejected(self):
        for value in (-.5,0,float('nan'),True):
            mapping=copy.deepcopy(self.mapping);mapping['right'][0]['value']=value
            with self.assertRaises(ValueError):append_blink_cycles(self.raw,mapping,self.scenarios,[0,1,0],[0,.1,.2])
        with self.assertRaises(ValueError):append_blink_cycles(self.raw,self.mapping,self.scenarios,[0,1,0],[0,.1,.1])
        with self.assertRaises(ValueError):append_blink_cycles(self.raw,self.mapping,[{'id':'existing','controls':['right']}],[0,1,0],[0,.1,.2])

    def test_host_mode_rejected_without_blender_import(self):
        with self.assertRaisesRegex(ValueError,'Host precheck'):_require_native({'request':{'mode':'host_precheck'}})
        with self.assertRaisesRegex(ValueError,'provenance'):_require_native({'request':{'mode':'native_stage_build'}})
        p={'input_artifact_id':'runtime-input','repository_commit':'runtime-commit','construction_report_path':'runtime-report'}
        self.assertEqual(_require_native({'request':{'mode':'native_stage_build','native_build_provenance':p}}),p)


if __name__=='__main__':unittest.main()
