# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest,numpy as np
from lab_recipes.visual_front_surface import front_depth,resample_source_boundary,_front_strip
from lab_recipes.fair_disk_patch import fair_disk_patch
from lab_recipes.original_lash_motion import audit_new_skin_occlusion

class VisualFrontSurfaceTests(unittest.TestCase):
    def test_front_depth_selects_actual_surface_and_is_frame_translation_equivariant(self):
        v=np.array([[1,-1,-1],[1,1,-1],[1,0,1],[2,-1,-1],[2,1,-1],[2,0,1]],float);f=np.array([[0,1,2],[3,4,5]]);q=np.array([[0,0,0],[0,3,3]],float);d=front_depth(q,v,f);self.assertEqual(d[0],2);self.assertTrue(np.isneginf(d[1]));v[:,0]+=10;q[:,0]+=10;self.assertEqual(front_depth(q,v,f)[0],12)
    def test_arc_resampling_removes_duplicate_and_large_parameter_jumps(self):
        p=np.array([[[0,0,0],[0,0,0],[.02,.001,0],[.02,.1,0]]]*2);e=np.array([[0,1],[1,2],[2,3]]);outer,path,arc,s=resample_source_boundary(p,e,65);self.assertTrue((np.linalg.norm(np.diff(outer,axis=0),axis=1)>0).all());self.assertLess(np.linalg.norm(np.diff(outer,axis=0),axis=1).max(),.002);np.testing.assert_array_equal(outer[[0,-1]],p[0,[0,-1]])
    def test_broken_boundary_is_not_silently_joined(self):
        p=np.array([[[0,0,0],[0,1,0],[0,5,0],[0,6,0]]]*2)
        with self.assertRaisesRegex(ValueError,'continuous'):resample_source_boundary(p,np.array([[0,1],[2,3]]),16)
    def test_source_route_strip_is_fixed_and_retains_actual_source_corner(self):
        p=np.array([[[0,0,0],[.1,0,1],[0,1,0],[.1,1,1]]]*2,float);p[1,[1,3],2]+=.1;path=np.array([[0,0,0],[.1,.5,0],[0,1,0]]);r=_front_strip(p,np.array([[0,2,3],[0,3,1]]),path,np.array([0,.5,1]),np.array([0,1]),2);poses,faces,domains,edges=r;self.assertTrue(np.any(np.all(poses[0]==path[1],axis=1)));np.testing.assert_array_equal(poses[:,np.unique(edges)],np.broadcast_to(poses[0,np.unique(edges)],poses[:,np.unique(edges)].shape))
    def test_disk_fairing_preserves_original_boundary_and_planarity(self):
        p=np.array([[[0,.5,.5],[0,0,0],[0,1,0],[0,1,1],[0,0,1]]]*2,float);f=np.array([[0,1,2],[0,2,3],[0,3,4],[0,4,1]]);r=fair_disk_patch(p,f,np.array([[1,2],[2,3]]),subdivisions=2);np.testing.assert_array_equal(r['poses'][:,:5],p);self.assertEqual(len(r['skin_boundary_edges']),8)
    def test_skin_occlusion_reports_new_hidden_vertices_separately_from_neutral(self):
        v=np.array([[1,-1,-1],[1,1,-1],[1,1,1],[1,-1,1],[.9,0,0],[1.1,.2,0]],float);f=np.array([[0,1,2],[0,2,3]]);p=np.repeat(v[None],2,axis=0);p[1,5,0]=.8;r=audit_new_skin_occlusion(v,f,[4,5],p);self.assertEqual(r['neutral_hidden_band_vertices'],1);self.assertEqual(r['samples'][1]['newly_hidden_band_vertices'],1);self.assertAlmostEqual(r['samples'][1]['maximum_new_depth_behind_skin'],.2)
if __name__=='__main__':unittest.main()
