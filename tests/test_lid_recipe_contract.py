# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Tests for input defects reproduced from the rejected Lab adapters."""
import copy
import ast
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
import numpy as np
from lab_recipes.aperture_contract import (
    rim_from_upper_lower_chains, validate_ordered_rim,
    weighted_clearance_projection, construction_envelope_from_samples,
)
from lab_recipes.lid_surface import build


def fixture():
    upper=[(.02,-.01,0),(.02,0,.005),(.02,.01,0)]
    lower=[(.02,-.01,0),(.02,0,-.005),(.02,.01,0)]
    eye={'rim_xyz':rim_from_upper_lower_chains(upper,lower),
         'sphere_center':[0,0,0],'sphere_radius':.02,
         'affine_globe':{'depth_scale':1,'shear_y':0,'shear_z':0}}
    parameters={'corner_extension_m':.001,'length_segments':32,
                'cross_section_samples':12,'envelope_smoothing_m':.0001,
                'closure_height_fraction':0,'globe_softplus_epsilon_m2':1e-10,
                'smoothmax_epsilon_m':1e-5,'collar_width_m':.002,
                'shell_thickness_m':.0003,'closure_overlap_m':.0005,
                'clearance_m':.0001,'upper_closure_depth_offset_m':.0005}
    return eye,parameters


class ApertureContractTests(unittest.TestCase):
    def test_explicit_chains_form_single_cycle_and_do_not_mutate_inputs(self):
        upper=[(.02,-.01,0),(.02,0,.005),(.02,.01,0)]
        lower=[(.02,-.01,0),(.02,0,-.005),(.02,.01,0)]
        original=copy.deepcopy((upper,lower))
        rim=rim_from_upper_lower_chains(upper,lower)
        self.assertEqual(len(rim),4)
        self.assertEqual((upper,lower),original)
        self.assertEqual(validate_ordered_rim(rim),rim)

    def test_interleaved_column_extrema_are_not_a_boundary_loop(self):
        # Archived freeze_aperture wrote bottom(y),top(y),bottom(y+1),top(y+1).
        interleaved=[(.02,-.01,-.002),(.02,-.01,.002),
                     (.02,0,-.005),(.02,0,.005),
                     (.02,.01,-.002),(.02,.01,.002)]
        with self.assertRaisesRegex(ValueError,'self-intersecting|zero projected area'):
            validate_ordered_rim(interleaved)

    def test_chain_station_order_is_explicit_not_guessed(self):
        with self.assertRaisesRegex(ValueError,'increasing'):
            rim_from_upper_lower_chains([(0,1,1),(0,0,1)],[(0,1,-1),(0,0,-1)])

    def test_upper_lower_inversion_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'upper/lower'):
            rim_from_upper_lower_chains([(0,0,-1),(0,1,-1)],[(0,0,1),(0,1,1)])

    def test_repeated_closing_vertex_is_rejected(self):
        eye,_=fixture()
        with self.assertRaisesRegex(ValueError,'repeated'):
            validate_ordered_rim(eye['rim_xyz']+[eye['rim_xyz'][0]])

    def test_ordered_but_pinched_sample_envelope_is_not_simple(self):
        upper=[(0,-1,1),(0,0,0),(0,1,1)]
        lower=[(0,-1,-1),(0,0,0),(0,1,-1)]
        with self.assertRaisesRegex(ValueError,'repeated'):
            rim_from_upper_lower_chains(upper,lower)

    def test_explicit_construction_hull_covers_pinched_samples_without_mutating(self):
        samples=[(.2,-1,-1),(.2,-1,1),(.2,0,0),(.2,1,-1),(.2,1,1)]
        before=copy.deepcopy(samples)
        hull=construction_envelope_from_samples(samples)
        self.assertEqual(samples,before)
        self.assertEqual(len(hull),4)
        self.assertEqual(validate_ordered_rim(hull),hull)
        yz=[p[1:] for p in hull]
        for _,y,z in samples:
            self.assertTrue(all((b[0]-a[0])*(z-a[1])-(b[1]-a[1])*(y-a[0])>=0
                                for a,b in zip(yz,yz[1:]+yz[:1])))

    def test_construction_hull_duplicate_projection_uses_frontmost_depth(self):
        samples=[(.1,0,0),(.3,0,0),(.2,1,0),(.2,0,1)]
        hull=construction_envelope_from_samples(samples)
        self.assertEqual(next(p[0] for p in hull if p[1:]==(0.,0.)),.3)
        self.assertEqual(hull,construction_envelope_from_samples(list(reversed(samples))))

    def test_construction_hull_rejects_collinear_or_nonfinite_samples(self):
        with self.assertRaisesRegex(ValueError,'collinear'):
            construction_envelope_from_samples([(0,0,0),(1,1,1),(2,2,2)])
        with self.assertRaisesRegex(ValueError,'finite'):
            construction_envelope_from_samples([(0,0,0),(1,1,0),(float('inf'),0,1)])

    def test_ordered_rim_validation_still_refuses_unordered_samples(self):
        eye,_=fixture()
        bowtie=[eye['rim_xyz'][i] for i in (0,2,1,3)]
        with self.assertRaises(ValueError):
            validate_ordered_rim(bowtie)
        # Explicit envelope construction is a separate, named caller decision.
        self.assertEqual(len(construction_envelope_from_samples(bowtie)),4)

    def test_invalid_input_fails_before_geometry_creation(self):
        eye,parameters=fixture();eye['rim_xyz'][0]=(float('nan'),0,0)
        with self.assertRaisesRegex(ValueError,'finite'):
            build(eye,True,parameters)

    def test_invalid_discretization_is_rejected(self):
        eye,parameters=fixture();parameters['length_segments']=2
        with self.assertRaisesRegex(ValueError,'length_segments'):
            build(eye,True,parameters)

    def test_zero_thickness_is_rejected(self):
        eye,parameters=fixture();parameters['shell_thickness_m']=0
        with self.assertRaisesRegex(ValueError,'shell_thickness'):
            build(eye,True,parameters)

    def test_valid_recipe_is_finite_and_has_no_zero_area_faces(self):
        eye,parameters=fixture()
        for upper in (True,False):
            positions,faces=build(eye,upper,parameters)
            for weight in (0,.25,.5,.75,1):
                p=positions(weight);tri=p[faces]
                self.assertTrue(np.isfinite(p).all())
                self.assertTrue((np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)>0).all())

    def test_clearance_projection_is_neutral_invariant(self):
        # Prior adapter moved these depths even at zero constructed blink weight.
        self.assertEqual(weighted_clearance_projection(.20,.25,0),.20)
        self.assertAlmostEqual(weighted_clearance_projection(.20,.25,1e-6)-.20,5e-8)
        self.assertAlmostEqual(weighted_clearance_projection(.20,.25,.25),.2125)
        self.assertEqual(weighted_clearance_projection(.20,.25,1),.25)

    def test_clearance_does_not_pull_safe_points_backward(self):
        self.assertEqual(weighted_clearance_projection(.3,.25,.5),.3)

    def test_clearance_rejects_nonfinite_or_out_of_range_weight(self):
        for weight in (float('nan'),-1,1.01):
            with self.assertRaises(ValueError):
                weighted_clearance_projection(.2,.25,weight)

    def test_existing_stage_clearance_no_longer_moves_neutral_vertex(self):
        # Compile the actual source's pure numeric nested functions so this
        # regression does not depend on Blender being installed in the test host.
        source=Path(__file__).resolve().parents[1]/'head_workflow/stages/fit_lids_and_blink.py'
        run=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='run')
        functions=[n for n in run.body if isinstance(n,ast.FunctionDef) and n.name in ('vertical_limits','is_foreground_hair','blink_coords')]
        body=object();hair=object()
        h=SimpleNamespace(body=body,hair=hair,globe_x=lambda e,y,z:.05,
                          config={'lash_components':[],'lid_falloff_upper':1,'lid_falloff_lower':1,'lid_close_fraction':.5})
        env={'np':np,'math':math,'h':h,'weighted_clearance_projection':weighted_clearance_projection}
        exec(compile(ast.Module(body=functions,type_ignores=[]),str(source),'exec'),env)
        eye={'polygon':np.array([[-1,-1],[1,-1],[1,1],[-1,1]]),'rim_xyz':[[0,-1,-1],[0,1,1]]}
        base=np.array([[.01,0,1.]])
        neutral,_=env['blink_coords'](body,base,eye,0)
        near,_=env['blink_coords'](body,base,eye,1e-6)
        self.assertTrue(np.array_equal(neutral,base))
        self.assertLess(np.linalg.norm(near-base),2e-6)


if __name__=='__main__':
    unittest.main()
