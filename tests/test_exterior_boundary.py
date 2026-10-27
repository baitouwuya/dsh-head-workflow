# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import sys,unittest
from pathlib import Path
import numpy as np
from lab_recipes.lid_surface import build
from lab_recipes.exterior_skin_boundary import fit_exterior_skin_boundary

class ExteriorBoundaryTests(unittest.TestCase):
    def fixture(self):
        grid=[-2,-1,0,1,2];v=np.array([[.2,y,z] for y in grid for z in grid]);f=[]
        for y in range(4):
            for z in range(4):
                if y in [1,2] and z in [1,2]:continue
                a=y*5+z;b=(y+1)*5+z;f.extend([[a,b,b+1],[a,b+1,a+1]])
        f=np.array(f);rim=np.array([[.2,-.8,0],[.2,0,-.6],[.2,.8,0],[.2,0,.6]])
        eye={'rim_xyz':rim.tolist(),'sphere_center':[0,0,0],'sphere_radius':1.,'affine_globe':{'depth_scale':.1,'shear_y':0,'shear_z':0}};d={'corner_extension_m':.01,'length_segments':12,'cross_section_samples':8,'envelope_smoothing_m':.01,'closure_height_fraction':0,'globe_softplus_epsilon_m2':.001,'smoothmax_epsilon_m':.001,'collar_width_m':.08,'shell_thickness_m':.02,'closure_overlap_m':.04,'clearance_m':.01,'upper_closure_depth_offset_m':.02,'linear_contour':True,'conservative_envelope':True,'uniform_cross_section':True};ev,ff=build(eye,True,d);ps=np.array([ev(x) for x in [0,.25,.5,.75,1]]);anchor=np.r_[np.arange(11)*8+2,len(ps[0])-2,len(ps[0])-1];order=np.r_[anchor[-2],anchor[:-2],anchor[-1]];inner=np.arange(11)*8+6
        args=(ps,ff,anchor,order,inner,8,v,f,np.arange(len(v)),np.arange(len(f)),np.arange(len(f)),rim,True);kw=dict(attachment_tolerance=1e-6,source_double_area_floor=1e-12,maximum_anchor_refit=2.,maximum_lateral_vertical_refit=2.,route_padding=.3,maximum_route_padding=2.,route_depth_margin=.1,maximum_route_length=3.);return args,kw
    def test_actual_constructor_wrapper_keeps_inner_and_source_and_reports_composed_map(self):
        args,kw=self.fixture();source=args[6].copy();r=fit_exterior_skin_boundary(*args,**kw);self.assertTrue(r['exterior_certificate_required']);self.assertTrue(r['complete_edge_certificate_pass']);self.assertEqual(r['construction_to_final_vertex_ids'].shape,(args[0].shape[1],));np.testing.assert_array_equal(args[6],source);self.assertLess(r['refit_report']['inner_rail_maximum_change'],1e-6)
        np.testing.assert_array_equal(r['construction_to_final_vertex_ids'][args[4]],r['inner_rail_vertices'])
    def test_refit_displacement_limit_is_required_not_silently_expanded(self):
        args,kw=self.fixture();kw['maximum_anchor_refit']=.001
        with self.assertRaisesRegex(ValueError,'displacement limit'):fit_exterior_skin_boundary(*args,**kw)
if __name__=='__main__':unittest.main()
