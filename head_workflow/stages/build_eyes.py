# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Reconstruction stage; invoked by the head workflow runner."""

def run(h):
    import bpy,math,json,numpy as np
    
    from mathutils import Vector
    
    def in_polygon(y,z,poly):
        return all((b[0]-a[0])*(z-a[1])-(b[1]-a[1])*(y-a[0])>=-1e-10 for a,b in zip(poly,np.roll(poly,-1,axis=0)))
    
    for old in getattr(h,'eyeballs',[]):
        if old.name in bpy.data.objects:bpy.data.objects.remove(old,do_unlink=True)
    h.eyeballs=[];report=[]
    for e in h.eyes:
        label=e['label'];gx,gy,gz=e['sphere_center'];r=e['sphere_radius'];aff=e['affine_globe'];size=h.config['eye_texture_size']
        arr=np.empty((size,size,4),np.float32);valid=np.zeros((size,size),bool);white_samples=[];depth_samples=[]
        for iy in range(size):
            z=gz-r+2*r*iy/(size-1)
            for ix in range(size):
                y=gy-r+2*r*ix/(size-1)
                if in_polygon(y,z,e['polygon']):
                    tex_sample=h.composite(e,y,z)
                    if tex_sample:
                        co=tex_sample['color'];arr[iy,ix]=co;valid[iy,ix]=True;depth_samples.append([y,z,float(tex_sample['co'][0])])
                        if min(co[:3])>.45 and max(co[:3])-min(co[:3])<.22:white_samples.append(co)
        white=np.median(white_samples,axis=0) if white_samples else np.array([.75,.80,.85,1])
        arr[~valid]=white;arr[:,:,3]=1
        im=bpy.data.images.new('dsh-'+label+'-original-eye-appearance',width=size,height=size,alpha=True);im.colorspace_settings.name='sRGB';im.pixels.foreach_set(arr.ravel());im.pack()
        mat=bpy.data.materials.new('dsh-'+label+'-original-eye');mat.use_nodes=True;bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Roughness'].default_value=.48;tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=im;mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
        back=bpy.data.materials.new('dsh-'+label+'-sclera');back.use_nodes=True;bb=next(n for n in back.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bb.inputs['Base Color'].default_value=tuple(white);bb.inputs['Roughness'].default_value=.5
        ds=np.array(depth_samples);u=(ds[:,0]-gy)/r;v=(ds[:,1]-gz)/r;design=np.array([u*0+1,u,v,u*u,u*v,v*v]).T;coef=np.linalg.lstsq(design,ds[:,2],rcond=None)[0]
        e['front_depth_coefficients']=coef.tolist()
        def depth(y,z):
            u=(y-gy)/r;v=(z-gz)/r;return float(np.dot(coef,[1,u,v,u*u,u*v,v*v]))
        e['front_center_x']=depth(gy,gz)
        verts=[[gx+aff['depth_scale']*r,gy,gz]];lat=h.config['eye_latitudes'];lon=h.config['eye_longitudes']
        for i in range(1,lat):
            phi=math.pi*i/lat
            for j in range(lon):
                th=2*math.pi*j/lon;y=gy+r*math.sin(phi)*math.cos(th);z=gz+r*math.sin(phi)*math.sin(th);x=gx+aff['depth_scale']*r*math.cos(phi)+aff['shear_y']*(y-gy)+aff['shear_z']*(z-gz)
                verts.append([x,y,z])
        rear=len(verts);verts.append([gx-aff['depth_scale']*r,gy,gz]);faces=[]
        for j in range(lon):faces.append([0,1+j,1+(j+1)%lon])
        for i in range(lat-2):
            for j in range(lon):a=1+i*lon+j;b=1+i*lon+(j+1)%lon;c=b+lon;d=a+lon;faces.append([a,d,c,b])
        for j in range(lon):faces.append([rear,1+(lat-2)*lon+(j+1)%lon,1+(lat-2)*lon+j])
        mesh=bpy.data.meshes.new('dsh-'+label+'-closed-globe');mesh.from_pydata(verts,[],faces);mesh.update();obj=bpy.data.objects.new(mesh.name,mesh);h.scene.collection.objects.link(obj);mesh.materials.append(mat);mesh.materials.append(back);uv=mesh.uv_layers.new(name='UVMap')
        for f in mesh.polygons:
            f.use_smooth=True;mean=np.mean([verts[i] for i in f.vertices],axis=0);front=mean[0]-gx-aff['shear_y']*(mean[1]-gy)-aff['shear_z']*(mean[2]-gz)
            f.material_index=0 if front>=0 else 1
            for li in f.loop_indices:
                p=verts[mesh.loops[li].vertex_index];uv.data[li].uv=((p[1]-gy+r)/(2*r),(p[2]-gz+r)/(2*r))
        obj.parent=h.rig;vg=obj.vertex_groups.new(name=h.config['head_bone']);vg.add(list(range(len(verts))),1,'REPLACE');mod=obj.modifiers.new('dsh-head-skin','ARMATURE');mod.object=h.rig
        h.eyeballs.append(obj);e['object_name']=obj.name
        report.append({'label':label,'vertices':len(verts),'faces':len(faces),'image_size':size,'source_appearance_samples':int(valid.sum()),'sclera_color':white.tolist(),'front_depth_fit_rms':float(np.sqrt(np.mean((design@coef-ds[:,2])**2))),'front_depth_coefficients':coef.tolist()})
    (h.root/'eye-construction.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
    h.render('eyes-neutral')
