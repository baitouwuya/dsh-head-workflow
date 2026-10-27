# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import copy,hashlib,unittest
import numpy as np
from lab_recipes.skin_appearance import transfer_skin_colors, transfer_lid_anchor_colors, sample_texture_rgb, audit_uv_chart_excursions, audit_source_uv_charts, srgb_to_linear, linear_to_srgb
from lab_recipes.skin_appearance import interpolate_skin_color_strip,blend_skin_boundary_colors

class SkinAppearanceTests(unittest.TestCase):
    def setUp(self):
        self.image=np.zeros((8,20,3),np.uint8)
        self.image[:,:5]=[240,205,198];self.image[:,15:]=[240,205,198]
        self.faces=np.array([[0,1,2],[3,4,5]])
        self.uv=np.array([[.075,.2],[.175,.2],[.075,.8],[.825,.2],[.925,.2],[.825,.8]])

    def test_cross_chart_stripe_reproduced_and_value_transfer_eliminates_it(self):
        old_uv=self.uv[[0,3,2]];faces=np.array([[0,1,2]])
        before=audit_uv_chart_excursions(self.image,old_uv,faces)
        self.assertGreater(before['outside_corner_color_range_samples'],0)
        out=transfer_skin_colors(self.faces,self.uv,self.image,[0,1,0],[[1,0,0],[1,0,0],[0,0,1]],[0,1])
        expected=srgb_to_linear(np.array([240,205,198])/255)
        self.assertTrue(np.allclose(out['colors_linear_rgba'][:,:3],expected))
        self.assertTrue(np.allclose(out['colors_linear_rgba'][:,:3].mean(0),expected))
        self.assertNotIn('baseColorTexture',out['material']['pbrMetallicRoughness'])

    def test_binding_interpolates_uv_only_within_one_source_triangle(self):
        out=transfer_skin_colors(self.faces,self.uv,self.image,[0],[[.2,.3,.5]],[0])
        uv=np.array([.2,.3,.5])@self.uv[self.faces[0]]
        self.assertTrue(np.allclose(out['sampled_source_uv'][0],uv))
        self.assertTrue(np.allclose(out['colors_linear_rgba'][0,:3],sample_texture_rgb(self.image,uv[None])[0]))

    def test_original_image_uv_and_material_are_unmodified(self):
        old_image=self.image.copy();old_uv=self.uv.copy()
        material={'doubleSided':False,'pbrMetallicRoughness':{'baseColorTexture':{'index':3},'baseColorFactor':[.8,.9,1,1],'roughnessFactor':.7,'metallicFactor':.1}}
        original=copy.deepcopy(material)
        out=transfer_skin_colors(self.faces,self.uv,self.image,[0],[[1,0,0]],[0],material)
        self.assertTrue(np.array_equal(self.image,old_image));self.assertTrue(np.array_equal(self.uv,old_uv));self.assertEqual(material,original)
        self.assertEqual(out['material']['pbrMetallicRoughness']['roughnessFactor'],.7)
        self.assertEqual(out['material']['pbrMetallicRoughness']['baseColorFactor'],[.8,.9,1,1])

    def test_unapproved_skin_binding_rejected(self):
        with self.assertRaisesRegex(ValueError,'unapproved'):
            transfer_skin_colors(self.faces,self.uv,self.image,[1],[[1,0,0]],[0])

    def test_invalid_barycentric_binding_rejected(self):
        for weights in ([[.5,.5,.5]],[[-.2,.6,.6]],[[np.nan,0,1]]):
            with self.assertRaises(ValueError):
                transfer_skin_colors(self.faces,self.uv,self.image,[0],weights,[0])

    def test_linear_vertex_colors_roundtrip_to_original_srgb(self):
        sample=np.array([.1,.5,.9]);self.assertTrue(np.allclose(linear_to_srgb(srgb_to_linear(sample)),sample))

    def test_explicit_anchor_color_mapping_does_not_assume_lid_topology(self):
        out=transfer_lid_anchor_colors(self.faces,self.uv,self.image,[0,1],[[1,0,0],[0,1,0]],[1,0,1,1,0],[0,1])
        self.assertEqual(out['source_triangle_ids'].tolist(),[1,0,1,1,0])
        self.assertEqual(out['colors_linear_rgba'].shape,(5,4))

    def test_invalid_anchor_mapping_rejected(self):
        with self.assertRaisesRegex(ValueError,'mapping'):
            transfer_lid_anchor_colors(self.faces,self.uv,self.image,[0],[[1,0,0]],[1],[0])

    def test_actual_uv_chart_audit_detects_duplicated_geometric_seam(self):
        p=np.array([[0,0,0],[1,0,0],[0,1,0],[1,0,0],[1,1,0],[0,1,0.]])
        uv=np.array([[0,0],[.2,0],[0,.2],[.8,.8],[1,1],[.8,1.]])
        report=audit_source_uv_charts(p,[[0,1,2],[3,4,5]],uv,1e-7)
        self.assertEqual(report['uv_chart_count'],2)
        self.assertEqual(report['uv_discontinuous_shared_geometric_edge_pairs'],1)
        self.assertFalse(report['exporter_vertex_ids_or_material_names_used'])

    def test_uv_chart_audit_does_not_join_different_materials(self):
        p=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0.]])
        report=audit_source_uv_charts(p,[[0,1,2],[0,2,3]],p[:,:2],1e-7,triangle_material_ids=[7,8])
        self.assertEqual(report['uv_chart_count'],2)
        self.assertEqual(report['different_material_edge_pairs'],1)

    def test_blender_and_gltf_uv_origins_sample_identical_source_color(self):
        image=np.zeros((4,4,3),np.uint8);image[:2]=[240,190,180];image[2:]=[10,20,70]
        gltf=np.array([[.25,.125]])
        blender=gltf.copy();blender[:,1]=1-blender[:,1]
        self.assertTrue(np.array_equal(sample_texture_rgb(image,gltf),sample_texture_rgb(image,blender,'bottom-left')))
        with self.assertRaises(ValueError):sample_texture_rgb(image,gltf,'guessed')

    def test_color_strip_interpolates_colors_and_reports_extrapolation(self):
        out=interpolate_skin_color_strip([0,1],[[.5,.4,.3,1],[.7,.6,.5,1]],[-1,.5,2])
        self.assertTrue(np.allclose(out['colors_linear_rgba'][1],[.6,.5,.4,1]))
        self.assertEqual(out['clamped_query_count'],2)

    def test_boundary_color_retained_while_interior_uses_clean_skin(self):
        p=np.array([[0,0,0],[1,0,0],[2,0,0],[0,1,0],[1,1,0],[2,1,0.]])
        f=np.array([[0,1,3],[1,4,3],[1,2,4],[2,5,4]])
        dark=np.tile([.05,.04,.03,1],(6,1));skin=np.tile([.8,.6,.55,1],(6,1))
        out=blend_skin_boundary_colors(p,f,[0,3],[2,5],dark,skin)
        self.assertTrue(np.allclose(out['colors_linear_rgba'][[0,3]],dark[[0,3]]))
        self.assertTrue(np.allclose(out['colors_linear_rgba'][[2,5]],skin[[2,5]]))
        self.assertTrue((out['colors_linear_rgba'][[1,4],:3]>.3).all())

if __name__=='__main__':unittest.main()
