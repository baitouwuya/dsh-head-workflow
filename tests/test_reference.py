# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import json
from pathlib import Path
import unittest
import numpy as np
from head_workflow.reference.geometry import (boundary_loops,frame_for,normalize,
    sample_path,encode_curve,encode_piecewise,curve_points,anchor_frames)
from head_workflow.reference.fit import (validate,fit_lid_profile,evaluate_lid,
    bounded_fit,target_vector,sample_eye)
from head_workflow.reference.canvas import measure_canvas_lids,fit_canvas_lids

ROOT = Path(__file__).resolve().parents[1]
def load(name='F00'):
    return json.loads((ROOT/'profiles/reference'/f'{name}.json').read_text(encoding='utf-8-sig'))


class GeometryTests(unittest.TestCase):
    def test_boundary_order_ignores_face_order_and_vertex_numbering(self):
        faces = np.array([[0,1,2],[0,2,3]])
        self.assertEqual(boundary_loops(faces)[0].tolist(),[0,1,2,3])
        perm = np.array([2,0,3,1])
        loop = boundary_loops(perm[faces[::-1]])[0]
        self.assertEqual(set(loop),set(range(4)))
        self.assertEqual(len(loop),4)

    def test_bad_boundary_rejected(self):
        with self.assertRaises(ValueError):
            boundary_loops(np.array([[0,1,2],[1,0,3],[0,1,4]]))

    def test_translation_scale_and_side_canonicalization(self):
        points = np.array([[1.,-2.,3.],[1.5,-2.1,3.3],[2.,-2.,3.]])
        a = normalize(points,frame_for(points,np.arange(3)))
        transformed = points*17+np.array([4.,5.,6.])
        b = normalize(transformed,frame_for(transformed,np.arange(3)))
        np.testing.assert_allclose(a,b,atol=1e-12)
        mirrored = points*np.array([-1,1,1])
        np.testing.assert_allclose(a,normalize(mirrored,frame_for(mirrored,np.arange(3))),atol=1e-12)

    def test_fixed_neutral_arclength_preserves_motion(self):
        neutral=np.array([[0.,0.,0.],[.25,.5,0.],[1.,0.,0.]])
        moved=neutral.copy();moved[:,2]=[0,1,0]
        s=sample_path(moved,neutral)
        np.testing.assert_allclose(s[:,2],sample_path(neutral,neutral)[:,1]*2)

    def test_polynomial_and_piecewise_endpoints(self):
        u=np.linspace(0,1,65)
        points=np.column_stack([u,u*(1-u),.1*u**3])
        for curve in (encode_curve(points),encode_piecewise(points)):
            np.testing.assert_allclose(curve_points(curve,u),points,atol=3e-7)
            np.testing.assert_allclose(curve_points(curve,[0,1]),points[[0,-1]],atol=3e-7)

    def test_anchor_orthonormality_and_roundtrip(self):
        p=load()['eyes']['positive_x']['aperture']['upper']
        u=np.linspace(0,1,41)
        origins,axes=anchor_frames(p,u)
        np.testing.assert_allclose(axes@axes.transpose(0,2,1),np.tile(np.eye(3),(41,1,1)),atol=1e-12)
        np.testing.assert_allclose(np.linalg.det(axes),1.,atol=1e-12)
        offset=np.tile([.03,.02,.01],(41,1))
        point=origins+np.einsum('nji,nj->ni',axes,offset)
        np.testing.assert_allclose(np.einsum('nij,nj->ni',axes,point-origins),offset,atol=1e-12)


class ReferenceTests(unittest.TestCase):
    def test_both_real_profiles_and_unknown_physical_thickness(self):
        for name in ('F00','M00'):
            p=validate(load(name))
            for eye in p['eyes'].values():
                self.assertIsNone(eye['lid_thickness']['physical_thickness'])
                self.assertIsNone(eye['socket_depth']['anatomical_socket_depth'])
                self.assertLess(max(c['reduction_max'] for m in eye['lid_margin'] for c in m.values()),.007)
                self.assertLess(max(s['centreline']['reduction_max'] for s in eye['lash_band']['samples']),.005)

    def test_nonfinite_wrong_grid_and_scale_rejected(self):
        for mutate in (lambda p:p['eyes']['positive_x']['aperture']['upper']['coefficients'][0].__setitem__(0,float('nan')),
                       lambda p:p['blink_weights'].__setitem__(2,.6),
                       lambda p:p.__setitem__('units','metres')):
            p=load();mutate(p)
            with self.assertRaises(ValueError):validate(p)

    def test_inconsistent_neutral_or_canthus_rejected(self):
        p=load();p['eyes']['positive_x']['lid_margin'][0]['upper']['coefficients'][0][1]+=.1
        with self.assertRaises(ValueError):validate(p)

    def test_order_does_not_change_target_loss(self):
        p=load();q=copy.deepcopy(p);q['eyes']=dict(reversed(list(q['eyes'].items())))
        np.testing.assert_array_equal(target_vector(p),target_vector(q))

    def test_compact_fit_and_intermediate_blink_are_local_interpolation(self):
        for name in ('F00','M00'):
            fitted=fit_lid_profile(load(name),shell_thickness=.012)
            for side,e in fitted['eyes'].items():
                self.assertLess(e['fit_rms'],.0015)
                self.assertLess(e['fit_max'],.006)
                u=np.linspace(0,1,33)
                a,b,c=[evaluate_lid(fitted,side,w,u) for w in (.25,.375,.5)]
                for key in ('upper','lower','lash'):
                    np.testing.assert_allclose(b[key],(a[key]+c[key])/2,atol=1e-12)
                np.testing.assert_allclose(b['lash'],b['anchor_origin']+np.einsum('nji,nj->ni',b['anchor_axes'],b['anchor_offsets']),atol=1e-12)
            self.assertEqual(fitted['thickness_source'],'caller')

    def test_missing_thickness_is_not_invented(self):
        self.assertIsNone(fit_lid_profile(load())['shell_thickness'])
        for v in (0,-1,float('nan'),.3):
            with self.assertRaises(ValueError):fit_lid_profile(load(),shell_thickness=v)

    def test_blink_range_rejected(self):
        m=fit_lid_profile(load())
        for w in (-.1,1.1,float('nan')):
            with self.assertRaises(ValueError):evaluate_lid(m,'positive_x',w,[.5])

    def test_public_artifact_has_no_source_geometry_or_assets(self):
        forbidden={'vertices','faces','uv','uvs','textures','materials','vertex_indices','rim_xyz','source_path'}
        def walk(x):
            if isinstance(x,dict):
                self.assertFalse(forbidden.intersection(x))
                for v in x.values():walk(v)
            elif isinstance(x,list):
                for v in x:walk(v)
            elif isinstance(x,str):
                self.assertNotIn('D:\\',x)
                self.assertNotIn('base64',x)
        for name in ('F00','M00','base-vrm'):walk(load(name))


class SolverTests(unittest.TestCase):
    def test_nonlinear_recovery_and_monotone_objective(self):
        fn=lambda p:np.array([p['x']**2,p['x']+2*p['y'],p['y']])
        result=bounded_fit(fn,fn({'x':.7,'y':-.3}),{'x':.2,'y':0.},{'x':(0.,1.),'y':(-1.,1.)})
        self.assertTrue(result['accepted'])
        self.assertAlmostEqual(result['parameters']['x'],.7,places=5)
        self.assertTrue(np.all(np.diff(result['history'])<0))

    def test_unreachable_target_reports_bound_not_success(self):
        visited=[]
        def fn(p):visited.append(p['x']);return [p['x']]
        result=bounded_fit(fn,[2.],{'x':.5},{'x':(0.,1.)})
        self.assertFalse(result['accepted'])
        self.assertEqual(result['at_bound'],['x'])
        self.assertTrue(all(0<=v<=1 for v in visited))

    def test_invalid_evaluator_bounds_and_target_fail(self):
        for fn,target,initial,bounds in (
            (lambda p:[float('nan')],[0.],{'x':0.},{'x':(-1.,1.)}),
            (lambda p:[0.,1.],[0.],{'x':0.},{'x':(-1.,1.)}),
            (lambda p:[0.],[0.],{'x':2.},{'x':(-1.,1.)}),
            (lambda p:[0.],[float('nan')],{'x':0.},{'x':(-1.,1.)})):
            with self.assertRaises(ValueError):bounded_fit(fn,target,initial,bounds)


class CanvasAdapterTests(unittest.TestCase):
    def test_existing_shell_parameter_recovery(self):
        # Entirely synthetic geometry; no private reference points in tests.
        t=np.linspace(0,2*np.pi,24,endpoint=False)
        eye={'rim_xyz':np.column_stack([np.full(24,.025),.04+.02*np.cos(t),.01*np.sin(t)]).tolist(),
             'sphere_center':[0.,.04,0.], 'sphere_radius':.03,
             'affine_globe':{'depth_scale':1.,'shear_y':0.,'shear_z':0.}}
        settings={'corner_extension_m':.0002,'length_segments':20,'cross_section_samples':8,
                  'envelope_smoothing_m':.0008,'closure_height_fraction':.1,
                  'globe_softplus_epsilon_m2':1e-8,'smoothmax_epsilon_m':1e-5,
                  'collar_width_m':.003,'shell_thickness_m':.0005,'clearance_m':.0001,
                  'closure_overlap_m':.0002,'upper_closure_depth_offset_m':.0006}
        measured=measure_canvas_lids(eye,settings)
        target={'lid_margin':[{k:encode_curve(measured[w,i]) for i,k in enumerate(('upper','lower'))} for w in range(5)],
                'lash_band':{'samples':[{'centreline':encode_curve(measured[w,0])} for w in range(5)]}}
        wrong={**settings,'closure_height_fraction':-.3,'upper_closure_depth_offset_m':0.}
        fit=fit_canvas_lids(eye,target,wrong,{'closure_height_fraction':(-.6,.6),'upper_closure_depth_offset_m':(-.002,.002)},max_iterations=8,tolerance=.0003)
        self.assertLess(fit['history'][-1],fit['history'][0]*.15)
        self.assertAlmostEqual(fit['parameters']['closure_height_fraction'],.1,delta=.015)
        self.assertAlmostEqual(fit['parameters']['upper_closure_depth_offset_m'],.0006,delta=.00003)
        self.assertEqual(fit['fitted_features'],['lid_margin'])
        with self.assertRaises(ValueError):measure_canvas_lids(eye,{**settings,'cross_section_samples':7})


if __name__=='__main__':unittest.main()
