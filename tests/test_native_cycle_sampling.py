# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import sys,struct,unittest,types
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native_cycle_verification import cycle_sample_schedule
from native_stage_export import cycle_verification_request
import full_look_review


class NativeCycleSamplingTests(unittest.TestCase):
    def tracks(self,rate=24,count=13):
        # Actual GLB float32 timing, including its representational noise.
        times=list(struct.unpack('<'+'f'*count,struct.pack('<'+'f'*count,*[i/rate for i in range(count)])))
        return [{'times':times}]

    def test_same_requested_rate_is_raised_and_midpoints_are_rendered(self):
        s=cycle_sample_schedule(self.tracks(),requested_fps=24,clip_fps=24)
        self.assertEqual(s['fps'],48);self.assertEqual(s['frames'],26)
        self.assertIn(1/48,s['sample_times_seconds']);self.assertEqual(s['samples_between_serialized_keys'],12)
        self.assertEqual(s['sample_times_seconds'][-1],.5)
        self.assertEqual(s['sample_times_seconds'][-2],.5)
        self.assertAlmostEqual(s['video_duration_seconds'],13/24)
        self.assertAlmostEqual(s['video_duration_seconds'],s['source_sequence_duration_seconds'])
        self.assertTrue(all(abs((b-a)-1/48)<1e-12 for a,b in zip(s['frame_clock_seconds'],s['frame_clock_seconds'][1:])))

    def test_rate_inferred_from_float32_key_data_without_version_constant(self):
        s=cycle_sample_schedule(self.tracks(rate=30,count=31))
        self.assertEqual(s['fps'],60);self.assertEqual(s['frames'],62)
        self.assertEqual(s['samples_between_serialized_keys'],30)
        self.assertAlmostEqual(s['video_duration_seconds'],31/30)

    def test_nonmonotonic_times_and_invalid_rates_fail(self):
        with self.assertRaises(ValueError):cycle_sample_schedule([{'times':[0,.1,.1]}])
        for invalid in (0,True,24.5):
            with self.assertRaises(ValueError):cycle_sample_schedule(self.tracks(),requested_fps=invalid)

    def test_request_default_doubles_runtime_clip_fps(self):
        key='sampling-unit-test';r={'mode':'native_stage_build','native_build_provenance':{'input_artifact_id':'runtime','repository_commit':'runtime','construction_report_path':'runtime'},'native_source_render_spec':{'path':'runtime','world_to_review':[]},'repo_root':'.','scenarios':[],'views':[],'lights':[],'fps':24}
        full_look_review.SESSIONS[key]={'request':r,'scene':types.SimpleNamespace(render=types.SimpleNamespace(engine='runtime'))}
        try:
            request=cycle_verification_request(key,'sealed.glb','review')
            self.assertEqual(request['clip_fps'],24);self.assertEqual(request['fps'],48)
            r['verification_fps']=24
            self.assertEqual(cycle_verification_request(key,'sealed.glb','review')['fps'],48)
        finally:del full_look_review.SESSIONS[key]


if __name__=='__main__':unittest.main()
