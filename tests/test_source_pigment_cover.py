# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import unittest,numpy as np
from lab_recipes.source_pigment_cover import add_source_pigment_covers

class PigmentCoverTests(unittest.TestCase):
    def fixture(self,dark):
        v=np.array([[1,y,z] for y in [-1,0,1] for z in [-1,0,1]]+[[1.1,-.2,-.2],[1.1,.2,-.2],[1.1,0,.2]],float);f=[]
        for y in range(2):
            for z in range(2):a=y*3+z;b=(y+1)*3+z;f.extend([[a,b,b+1],[a,b+1,a+1]])
        f=np.array(f+[[9,10,11]]);comp=np.r_[np.zeros(9,int),np.ones(3,int)];s={'vertices':v,'faces':f,'component':comp,'uv_0':(v[:,1:]+1)/2,'triangle_loops':f};q=np.array([[1,-.4,-.4],[1,.4,.4],[1,-.4,.4],[1,.4,-.4]]);roles={'skin_component':0,'eye_components':{'side':[1]},'lash_bands':{'side':[1]}};cfg={'controls':{'blink':{'samples':[0,.5,1]}},'pigmentCover':{'samplingResolution':[32,32]}};img=np.full((32,32,3),220,np.uint8)
        if dark:img[8:20,10:22]=20
        return s,{'side_visible':q},roles,cfg,img
    def test_source_image_and_geometry_are_unchanged_and_cover_starts_subsurface(self):
        s,p,r,c,image=self.fixture(True);v=s['vertices'].copy();before=image.copy();result=add_source_pigment_covers(s,{},p,r,c,2.,image);self.assertGreater(result['report']['side']['dark_source_faces'],0);poses=result['arrays']['side-pigment-cover_poses'];self.assertTrue((poses[0,:,0]<.5).all());self.assertTrue((poses[-1,:,0]>.5).all());np.testing.assert_array_equal(s['vertices'],v);np.testing.assert_array_equal(image,before);self.assertEqual(result['patch_specs'][0]['normal_mode'],'source_static')
    def test_no_dark_source_pixels_creates_no_unnecessary_cover(self):
        s,p,r,c,image=self.fixture(False);result=add_source_pigment_covers(s,{},p,r,c,2.,image);self.assertFalse(result['arrays']);self.assertEqual(result['report']['side']['dark_source_faces'],0)
if __name__=='__main__':unittest.main()
