# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Small synthetic geometry regressions; contains no user model data."""
import unittest
import numpy as np
from lab_recipes import lid_surface as surface
from lab_recipes.triangle_depth_bound import TriangleDepthBound
from lab_recipes.blink_handoff import audit_linear_morph_segments

class SurfaceObstacleTests(unittest.TestCase):
    def setUp(self):
        self.eye={'rim_xyz':[[.1,-1,0],[.1,0,-.5],[.1,1,0],[.1,0,.5]],'sphere_center':[0,0,0],'sphere_radius':1.2,'affine_globe':{'depth_scale':.1,'shear_y':0,'shear_z':0}}
        self.params={'corner_extension_m':.04,'length_segments':16,'cross_section_samples':12,'envelope_smoothing_m':.01,'closure_height_fraction':0,'globe_softplus_epsilon_m2':.001,'smoothmax_epsilon_m':.001,'collar_width_m':.08,'shell_thickness_m':.02,'closure_overlap_m':.04,'clearance_m':.01,'upper_closure_depth_offset_m':.02,'linear_contour':True,'conservative_envelope':True,'uniform_cross_section':True}
        self.obstacle=TriangleDepthBound([[[.3,-1.2,-.7],[.35,1.2,-.7],[.35,1.2,.7]],[[.3,-1.2,-.7],[.35,1.2,.7],[.3,-1.2,.7]]])
    def test_fixed_outer_attachments_neutral_and_float32_faces(self):
        for upper in [False,True]:
            positions,faces=surface.build(self.eye,upper,self.params,triangle_depth_bound=self.obstacle)
            basis=positions(0).astype(np.float32).astype(float);outer=np.r_[np.arange(3,len(basis)-2,12),len(basis)-2,len(basis)-1]
            for value in [0,.25,.5,.75,1]:
                p=positions(value).astype(np.float32).astype(float);np.testing.assert_array_equal(p[outer],basis[outer]);self.assertTrue(np.isfinite(p).all())
                n=np.cross(p[faces[:,1]]-p[faces[:,0]],p[faces[:,2]]-p[faces[:,0]])
                self.assertGreater(np.linalg.norm(n,axis=1).min(),1e-12)
                self.assertGreaterEqual(p[:,0].min(),.35+.01-1e-6)
            np.testing.assert_array_equal(positions(0).astype(np.float32),basis.astype(np.float32))
            self.assertLess(np.linalg.norm(positions(1e-6)-positions(0),axis=1).max(),1e-5)
    def test_bound_queried_once_for_entire_swept_footprint(self):
        calls=[]
        def bound(lo,hi):calls.append((lo.copy(),hi.copy()));return self.obstacle(lo,hi)
        positions,faces=surface.build(self.eye,True,self.params,triangle_depth_bound=bound)
        for v in [0,.1,.5,1]:positions(v)
        self.assertEqual(len(calls),1)
        lo,hi=calls[0]
        for v in [0,.25,.5,.75,1]:
            q=positions(v)[faces,1:]
            self.assertTrue((q.min(1)>=lo-1e-7).all());self.assertTrue((q.max(1)<=hi+1e-7).all())
    def test_invalid_bound_and_nonuniform_sweep_fail(self):
        for bad in [lambda lo,hi:np.full(len(lo),np.nan),lambda lo,hi:np.full(len(lo),np.inf),lambda lo,hi:np.zeros((len(lo),1))]:
            with self.assertRaises(ValueError):surface.build(self.eye,True,self.params,triangle_depth_bound=bad)
        with self.assertRaises(ValueError):surface.build(self.eye,True,{**self.params,'uniform_cross_section':False},triangle_depth_bound=self.obstacle)
    def test_empty_footprints_are_explicit_fallback(self):
        positions,faces=surface.build(self.eye,True,self.params,triangle_depth_bound=lambda lo,hi:np.full(len(lo),-np.inf))
        self.assertTrue(np.isfinite(positions(.5)).all())
    def test_actual_linear_morph_intervals_do_not_collapse(self):
        positions,faces=surface.build(self.eye,True,self.params,triangle_depth_bound=self.obstacle)
        knots=[0,.25,.5,.75,1];samples=np.array([positions(v).astype(np.float32).astype(float) for v in knots])
        audit=audit_linear_morph_segments(samples[0],faces,knots,samples,source_double_area_floor=1e-12,collapse_area_ratio=1e-6)
        self.assertEqual(audit['newly_collapsed_face_count'],0)
        self.assertEqual(audit['inherited_source_degenerate_faces'],0)
    def test_invalid_weight_is_rejected(self):
        positions,_=surface.build(self.eye,True,self.params,triangle_depth_bound=self.obstacle)
        for weight in [-.01,1.01,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):positions(weight)
    def test_exact_outer_anchor_sampling_is_required(self):
        with self.assertRaises(ValueError):surface.build(self.eye,True,{**self.params,'cross_section_samples':14},triangle_depth_bound=self.obstacle)
    def test_flags_and_point_depth_shape_are_explicit(self):
        with self.assertRaises(ValueError):surface.build(self.eye,True,{**self.params,'linear_contour':'true'})
        positions,_=surface.build(self.eye,True,self.params,front_depth=lambda y,z:np.zeros((len(y),1)) if np.ndim(y) else 0.)
        with self.assertRaises(ValueError):positions(.5)
if __name__=='__main__':unittest.main()
