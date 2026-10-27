# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from blender_runtime_compat import resolve_render_engine,set_render_engine

class RenderEngineTests(unittest.TestCase):
    def test_42_and_52_alias_both_directions(self):
        self.assertEqual(resolve_render_engine('BLENDER_EEVEE',['BLENDER_EEVEE_NEXT','CYCLES']),'BLENDER_EEVEE_NEXT')
        self.assertEqual(resolve_render_engine('BLENDER_EEVEE_NEXT',['BLENDER_EEVEE','CYCLES']),'BLENDER_EEVEE')
        self.assertEqual(resolve_render_engine(None,['BLENDER_EEVEE']),'BLENDER_EEVEE')
    def test_explicit_other_engine_is_not_replaced(self):
        self.assertEqual(resolve_render_engine('CYCLES',['CYCLES','BLENDER_EEVEE']),'CYCLES')
        with self.assertRaises(ValueError):resolve_render_engine('CYCLES',['BLENDER_EEVEE'])
    def test_live_rna_selection(self):
        render=SimpleNamespace(engine='CYCLES',bl_rna=SimpleNamespace(properties={'engine':SimpleNamespace(enum_items=[SimpleNamespace(identifier='BLENDER_EEVEE')])}));scene=SimpleNamespace(render=render)
        self.assertEqual(set_render_engine(scene,'BLENDER_EEVEE_NEXT'),'BLENDER_EEVEE');self.assertEqual(render.engine,'BLENDER_EEVEE')
