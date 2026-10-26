# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,json,numpy as np
from pathlib import Path
def apply(construction,atlas_file,fit_file,cfg,out):
    scene=bpy.context.scene
    body=next(o for o in scene.objects if o.type=='MESH' and 'BodyFace' in o.name);mesh=body.data
    fit=json.loads(Path(fit_file).read_text())
    image=bpy.data.images.load(atlas_file,check_existing=True);a=np.empty(len(image.pixels),np.float32);image.pixels.foreach_get(a);a=a.reshape(image.size[1],image.size[0],4)
    def linear(c):return np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)
    errors={'srgb':0.,'linear':0.}
    for sample in fit['validation_samples']:
        value=a[image.size[1]-1-sample['y_top'],sample['x'],:3]
        for mode in errors:errors[mode]=max(errors[mode],float(np.max(abs(value-np.array(sample[mode])))))
    space=min(errors,key=errors.get)
    def sample_color(uv):
        x=float(np.clip(uv[0],0,1))*(image.size[0]-1);y=float(np.clip(uv[1],0,1))*(image.size[1]-1);ix=int(x);iy=int(y);tx=x-ix;ty=y-iy
        c=(a[iy,ix,:3]*(1-tx)+a[iy,min(ix+1,image.size[0]-1),:3]*tx)*(1-ty)+(a[min(iy+1,image.size[1]-1),ix,:3]*(1-tx)+a[min(iy+1,image.size[1]-1),min(ix+1,image.size[0]-1),:3]*tx)*ty
        return linear(c) if space=='srgb' else c
    old=mesh.color_attributes.active_color
    old_colors=[tuple(old.data[li if old.domain=='CORNER' else mesh.loops[li].vertex_index].color) for li in range(len(mesh.loops))] if old else [(1,1,1,1)]*len(mesh.loops)
    attr=mesh.color_attributes.new(name='dsh-lid-clean-albedo',type='FLOAT_COLOR',domain='CORNER')
    for li,color in enumerate(old_colors):attr.data[li].color=color
    mesh.color_attributes.active_color_index=len(mesh.color_attributes)-1;mesh.color_attributes.render_color_index=len(mesh.color_attributes)-1
    regions=construction['regions'];changed=0
    for face in mesh.polygons:
        material=mesh.materials[face.material_index]
        if material.name!='dsh-continuous-eyelid-skin':continue
        region=next(r for r in regions if face.index in r['faces'])
        coefficients=next(e for e in fit['eyes'] if e['eye']==region['eye']);coef=np.array(coefficients['coefficients']);center=np.array(coefficients['center']);scale=np.array(coefficients['scale'])
        for li in face.loop_indices:
            vi=mesh.loops[li].vertex_index;p=np.array(mesh.vertices[vi].co);u,v=(p[1:3]-center)/scale
            clean=np.clip(np.array([1,u,v,u*u,u*v,v*v])@coef,0,1);clean=linear(clean)
            t=region['vertex_t'].get(str(vi),0)
            weight=float(np.clip(t/cfg['skin_blend_rows_fraction'],0,1));weight=weight*weight*(3-2*weight)
            color=sample_color(mesh.uv_layers.active.data[li].uv)*(1-weight)+clean*weight
            value=(*np.clip(color,0,1),1);attr.data[li].color=value
            # glTF has one primary color semantic per primitive. Keep all existing
            # corner layers consistent on the newly authored patch only.
            for layer in mesh.color_attributes:
                if layer.domain=='CORNER':layer.data[li].color=value
            changed+=1
    # Bake the local fitted field into the source UV atlas. This makes the
    # exported albedo explicit and independent of vertex-color layer selection.
    mesh.calc_loop_triangles();paint=a.copy();painted=0;new_faces={i for r in regions for i in r['faces']}
    def srgb(c):return np.where(c<=.0031308,c*12.92,1.055*np.maximum(c,0)**(1/2.4)-.055)
    for triangle in mesh.loop_triangles:
        if triangle.polygon_index not in new_faces:continue
        loops=list(triangle.loops);uvs=np.array([mesh.uv_layers.active.data[li].uv[:] for li in loops]);xy=uvs*np.array([image.size[0]-1,image.size[1]-1]);colors=np.array([attr.data[li].color[:3] for li in loops]);matrix=np.column_stack((xy[1]-xy[0],xy[2]-xy[0]))
        if abs(np.linalg.det(matrix))<1e-12:continue
        lo=np.maximum(np.floor(xy.min(0)).astype(int),0);hi=np.minimum(np.ceil(xy.max(0)).astype(int),np.array(image.size)-1)
        xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1),np.arange(lo[1],hi[1]+1));points=np.column_stack((xx.ravel(),yy.ravel()));weights=(points-xy[0])@np.linalg.inv(matrix).T;weights=np.column_stack((1-weights.sum(1),weights));valid=np.all(weights>=-1e-5,axis=1)
        linear_color=weights[valid]@colors;pixels=srgb(linear_color) if space=='srgb' else linear_color;pts=points[valid].astype(int);paint[pts[:,1],pts[:,0],:3]=pixels;painted+=len(pts)
    painted_image=image.copy();painted_image.name='dsh-eyelid-source-derived-albedo';painted_image.pixels.foreach_set(paint.astype(np.float32).ravel());painted_image.update();painted_image.filepath_raw=str(out/'eyelid-albedo.png');painted_image.file_format='PNG';painted_image.save()
    # Reload the authored PNG: an image copy can retain the source packed bytes.
    painted_image=bpy.data.images.load(str(out/'eyelid-albedo.png'),check_existing=False);painted_image.pack()
    for fi in new_faces:
        for li in mesh.polygons[fi].loop_indices:
            for layer in mesh.color_attributes:
                if layer.domain=='CORNER':layer.data[li].color=(1,1,1,1)
    for material in mesh.materials:
        if material.name!='dsh-continuous-eyelid-skin':continue
        bs=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        for link in list(bs.inputs['Base Color'].links):material.node_tree.links.remove(link)
        texture=material.node_tree.nodes.new('ShaderNodeTexImage');texture.image=painted_image;material.node_tree.links.new(texture.outputs['Color'],bs.inputs['Base Color'])

    mesh.update();bpy.context.view_layer.update()
    return {'pixelSpaceObserved':space,'validationErrors':errors,'pixelSpaceError':errors[space],'changedCorners':changed,'paintedPixels':painted,'export':'explicit PNG base-color texture'}
