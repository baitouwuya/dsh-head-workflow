# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import sys,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import full_look_review


class RestNormalRegressionTests(unittest.TestCase):
    def test_frame_update_never_writes_posed_normals_to_basis(self):
        calls=[];updates=[]
        fake_bpy=types.SimpleNamespace(context=types.SimpleNamespace(view_layer=types.SimpleNamespace(update=lambda:updates.append(True))))
        fake_verifier=types.SimpleNamespace(apply_control_values=lambda objects,mapping,values:calls.append((objects,mapping,values)))
        # No source mesh/normal arrays are exposed. A per-frame normal rewrite
        # would fail here, reproducing the known Basis compensation regression.
        objects=object();mapping={'control':[{'value':1,'name':'actual-knot'}]}
        session={'request':{'repo_root':'.'},'scene':types.SimpleNamespace(objects=objects),'mapping':mapping,'rest_normals_initialized':True}
        with patch.dict(sys.modules,{'bpy':fake_bpy,'native_render_verification':fake_verifier}):
            full_look_review._set_state(session,{'control':.5})
        self.assertEqual(calls,[(objects,mapping,{'control':.5})]);self.assertEqual(len(updates),1)


if __name__=='__main__':unittest.main()
