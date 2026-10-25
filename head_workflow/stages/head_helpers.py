# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Reconstruction stage; invoked by the head workflow runner."""

def run(h):
    import bpy, math, json, collections, numpy as np
    from mathutils import Vector
    from mathutils.geometry import barycentric_transform
    from mathutils.bvhtree import BVHTree
    
    # Read-only source samplers. All new geometry is built in the candidate scene.
    h.textures = {}
    h.bvhs = {}
    for obj in [h.src_body, h.src_hair]:
        h.bvhs[obj.name]=BVHTree.FromPolygons([v.co[:] for v in obj.data.vertices],[list(f.vertices) for f in obj.data.polygons],all_triangles=True)
        for mat in obj.data.materials:
            tex = next((n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image), None)
            if tex and mat.name not in h.textures:
                im=tex.image; pixels=np.empty(len(im.pixels), np.float32); im.pixels.foreach_get(pixels)
                h.textures[mat.name]=(pixels.reshape(im.size[1],im.size[0],4),im)
    
    def sample(obj,y,z):
        p,n,fi,distance=h.bvhs[obj.name].ray_cast(Vector((.15,y,z)),Vector((-1,0,0)))
        if p is None: return None
        f=obj.data.polygons[fi]; ids=list(f.vertices)[:3]
        a,b,c=[obj.data.vertices[i].co for i in ids]
        w=barycentric_transform(p,a,b,c,Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
        uv=sum((obj.data.uv_layers.active.data[li].uv*w[k] for k,li in enumerate(list(f.loop_indices)[:3])),Vector((0,0)))
        arr,im=h.textures[obj.data.materials[f.material_index].name]
        px=float(uv.x%1)*(arr.shape[1]-1); py=float(uv.y%1)*(arr.shape[0]-1)
        ix=int(px);iy=int(py);tx=px-ix;ty=py-iy
        color=(arr[iy,ix]*(1-tx)+arr[iy,min(ix+1,arr.shape[1]-1)]*tx)*(1-ty)+(arr[min(iy+1,arr.shape[0]-1),ix]*(1-tx)+arr[min(iy+1,arr.shape[0]-1),min(ix+1,arr.shape[1]-1)]*tx)*ty
        return {'co':np.array(p), 'color':color, 'uv':tuple(uv), 'face':fi,'ids':ids,'weights':np.array(w),'source':obj.name}
    h.sample=sample
    
    def globe_x(e,y,z):
        gx,gy,gz=e['sphere_center'];r=e['sphere_radius'];a=e['affine_globe']
        return gx+a['depth_scale']*math.sqrt(max(0,r*r-(y-gy)**2-(z-gz)**2))+a['shear_y']*(y-gy)+a['shear_z']*(z-gz)
    h.globe_x=globe_x
    
    def composite(e,y,z):
        a=h.sample(h.src_body,y,z);b=h.sample(h.src_hair,y,z)
        if b:
            col=b['color'];foreground_blue=col[2]>col[0]*1.3 and col[0]<.35 and b['co'][0]>max(p[0] for p in e['rim_xyz'])+.0015
            if not foreground_blue and (a is None or b['co'][0]>a['co'][0]): a=b
        return a
    h.composite=composite
    
    def hull(points):
        pts=sorted(set(tuple(map(float,p)) for p in points))
        def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
        lo=[];hi=[]
        for p in pts:
            while len(lo)>=2 and cross(lo[-2],lo[-1],p)<=0:lo.pop()
            lo.append(p)
        for p in reversed(pts):
            while len(hi)>=2 and cross(hi[-2],hi[-1],p)<=0:hi.pop()
            hi.append(p)
        return np.array(lo[:-1]+hi[:-1])
    h.hull=hull
    
    for e in h.eyes:
        e['polygon']=hull(np.array(e['rim_xyz'])[:,1:3])
    
    def clip_half(poly,a,b,keep_inside):
        def signed(v):return (b[0]-a[0])*(v[0][2]-a[1])-(b[1]-a[1])*(v[0][1]-a[0])
        result=[]
        for i,start in enumerate(poly):
            end=poly[(i+1)%len(poly)];ds=signed(start);de=signed(end)
            ins=ds>=-1e-12 if keep_inside else ds<=1e-12; ine=de>=-1e-12 if keep_inside else de<=1e-12
            if ins:result.append(start)
            if ins!=ine:
                t=ds/(ds-de);result.append(tuple(x+(y-x)*t for x,y in zip(start,end)))
        return result
    
    def difference(poly,cut):
        inside=poly;outside=[]
        for a,b in zip(cut,np.roll(cut,-1,axis=0)):
            if len(inside)<3:break
            part=clip_half(inside,a,b,False)
            if len(part)>=3:outside.append(part)
            inside=clip_half(inside,a,b,True)
        return outside,inside
    
    def rebuild_apertures(src,dst,regions):
        mesh=src.data;pos=np.empty((len(mesh.vertices),3),np.float32);mesh.vertices.foreach_get('co',pos.ravel())
        oldkeys={}
        for key in mesh.shape_keys.key_blocks:
            arr=np.empty_like(pos);key.data.foreach_get('co',arr.ravel());oldkeys[key.name]=arr
        verts=pos.tolist();new_maps=[];cache={};faces=[];uvs=[];mats=[];smooth=[];removed=[];face_refs=[]
        uv=mesh.uv_layers.active
        for f in mesh.polygons:
            ids=list(f.vertices);points=pos[ids];center=points.mean(0);eligible=[]
            for e in regions:
                cut=e['polygon'];lo=cut.min(0);hi=cut.max(0)
                if points[:,1].max()<lo[0] or points[:,1].min()>hi[0] or points[:,2].max()<lo[1] or points[:,2].min()>hi[1]:continue
                if center[0] < e.get('back',.004):continue
                if src==h.src_hair and e.get('label')!='mouth':
                    if hasattr(h,'source_hair_editable') and not any(h.source_hair_editable[i] for i in ids):continue
                    uvavg=np.mean([uv.data[li].uv[:] for li in f.loop_indices],0);arr,im=h.textures[mesh.materials[f.material_index].name];color=arr[int((uvavg[1]%1)*(arr.shape[0]-1)),int((uvavg[0]%1)*(arr.shape[1]-1))]
                    if not hasattr(h,'source_hair_editable') and color[2]>color[0]*1.3 and color[0]<.35 and center[0]>max(p[0] for p in e['rim_xyz'])+.0015:continue
                eligible.append(e)
            if not eligible:
                faces.append(ids);uvs.append([tuple(uv.data[li].uv) for li in f.loop_indices]);mats.append(f.material_index);smooth.append(f.use_smooth);face_refs.append((f.index,list(np.eye(len(ids)))));continue
            # Existing source polygons are triangles. We retain their outside pieces exactly.
            if len(ids)!=3:raise RuntimeError('Unexpected non-triangle source polygon')
            poly=[(pos[vi].astype(float),np.array(uv.data[li].uv),np.eye(3)[j]) for j,(vi,li) in enumerate(zip(ids,f.loop_indices))]
            pieces=[poly];did_cut=False
            for e in eligible:
                nxt=[]
                for piece in pieces:
                    out,inside=difference(piece,e['polygon']);nxt.extend(out)
                    if len(inside)>=3:did_cut=True
                pieces=nxt
            if did_cut:removed.append(f.index)
            for piece in pieces:
                polyids=[];puv=[];pw=[]
                for co,tuv,w in piece:
                    matches=np.flatnonzero(w>.99999999)
                    if len(matches):vi=ids[int(matches[0])]
                    else:
                        # Intersections are welded within this source mesh at 0.1 micrometre.
                        ck=tuple(np.round(co,7));vi=cache.get(ck)
                        if vi is None:
                            vi=len(verts);cache[ck]=vi;verts.append(co.tolist());new_maps.append((vi,ids,w.copy()))
                    polyids.append(vi);puv.append(tuple(tuv));pw.append(w)
                # Remove repeated consecutive corners produced by an on-edge intersection.
                clean=[];cu=[];cw=[]
                for vi,tu,ww in zip(polyids,puv,pw):
                    if not clean or clean[-1]!=vi:clean.append(vi);cu.append(tu);cw.append(ww)
                if len(clean)>1 and clean[0]==clean[-1]:clean.pop();cu.pop();cw.pop()
                if len(set(clean))>=3:
                    faces.append(clean);uvs.append(cu);mats.append(f.material_index);smooth.append(f.use_smooth);face_refs.append((f.index,cw))
        new=bpy.data.meshes.new('dsh-original-face-apertures');new.from_pydata(verts,[],faces);new.update()
        for mat in mesh.materials:new.materials.append(mat)
        layer=new.uv_layers.new(name=uv.name)
        for f,tu,mi,sm in zip(new.polygons,uvs,mats,smooth):
            f.material_index=mi;f.use_smooth=sm
            for li,u in zip(f.loop_indices,tu):layer.data[li].uv=u
        for oldattr in mesh.color_attributes:
            if oldattr.domain!='CORNER':continue
            attr=new.color_attributes.new(name=oldattr.name,type=oldattr.data_type,domain='CORNER')
            for f,(fi,ws) in zip(new.polygons,face_refs):
                original=np.array([oldattr.data[li].color[:] for li in mesh.polygons[fi].loop_indices])
                for li,w in zip(f.loop_indices,ws):attr.data[li].color=tuple(np.sum(original*np.array(w)[:,None],axis=0))
        if len(mesh.color_attributes):
            new.color_attributes.active_color_index=mesh.color_attributes.active_color_index
            new.color_attributes.render_color_index=mesh.color_attributes.render_color_index
        normals=[]
        for fi,ws in face_refs:
            original=np.array([mesh.corner_normals[li].vector[:] for li in mesh.polygons[fi].loop_indices])
            for w in ws:
                normal=np.sum(original*np.array(w)[:,None],axis=0);normal/=max(np.linalg.norm(normal),1e-12);normals.append(tuple(normal))
        new.normals_split_custom_set(normals)
        dst.data=new
        for name,arr in oldkeys.items():
            out=np.empty((len(verts),3),np.float32);out[:len(pos)]=arr
            for vi,ids,w in new_maps:out[vi]=np.sum(arr[ids]*w[:,None],axis=0)
            key=dst.shape_key_add(name=name,from_mix=False);key.data.foreach_set('co',out.ravel());key.value=0
        groups=[g.name for g in src.vertex_groups];srcweights=[{g.group:g.weight for g in v.groups} for v in mesh.vertices]
        for name in groups:
            if dst.vertex_groups.get(name) is None:dst.vertex_groups.new(name=name)
        for i,weights in enumerate(srcweights):
            for gi,w in weights.items():dst.vertex_groups[groups[gi]].add([i],w,'REPLACE')
        for vi,ids,ws in new_maps:
            weights=collections.defaultdict(float)
            for si,w in zip(ids,ws):
                for gi,value in srcweights[si].items():weights[gi]+=value*w
            for gi,w in weights.items():
                if w>1e-8:dst.vertex_groups[groups[gi]].add([vi],w,'REPLACE')
        if src==h.src_hair and hasattr(h,'source_hair_editable'):
            h.hair_editable_mask=np.zeros(len(verts),bool);h.hair_editable_mask[:len(pos)]=h.source_hair_editable
            h.work_hair_components=np.full(len(verts),-1,int);h.work_hair_components[:len(pos)]=h.hair_component_indices
            for vi,ids,ws in new_maps:h.hair_editable_mask[vi]=any(h.source_hair_editable[i] for i in ids)
            for vi,ids,ws in new_maps:h.work_hair_components[vi]=h.hair_component_indices[ids[int(np.argmax(ws))]]
        info={'source_vertices':len(pos),'new_vertices':len(verts)-len(pos),'removed_or_clipped_faces':len(removed),'faces':len(faces)}
        return info
    h.rebuild_apertures=rebuild_apertures
    
    def setup_render(scene):
        scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=640;scene.render.resolution_y=640;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
        world=bpy.data.worlds.new('dsh-head-review-world');world.use_nodes=True;bg=next(n for n in world.node_tree.nodes if n.type=='BACKGROUND');bg.inputs[0].default_value=(.25,.25,.25,1);bg.inputs[1].default_value=.8;scene.world=world
        scene.view_settings.view_transform='Standard'
        cd=bpy.data.cameras.new('dsh-head-review-camera');cam=bpy.data.objects.new(cd.name,cd);scene.collection.objects.link(cam);cam.data.type='ORTHO';cam.data.ortho_scale=h.config['render']['ortho_scale'];scene.camera=cam
        target=Vector(h.config['render']['target']);views={'front':(.5,.002,.903),'left45':(.355,.357,.903),'right45':(.355,-.353,.903),'profile':(0,.502,.903)}
        lights=[]
        for label,loc,power in [('key',(.5,-.3,1.3),5),('fill',(.25,.4,1.0),2)]:
            data=bpy.data.lights.new('dsh-head-'+label,'AREA');obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.location=loc;obj.rotation_euler=(target-obj.location).to_track_quat('-Z','Y').to_euler();data.energy=power;data.size=1;lights.append(obj)
        return cam,lights,target,h.config['render']['views']
    if not hasattr(h,'camera'):h.camera,h.lights,h.target,h.views=setup_render(h.scene)
    for obj in [h.camera]+h.lights:
        if obj.name not in h.source_scene.objects:h.source_scene.collection.objects.link(obj)
    h.source_scene.camera=h.camera;h.source_scene.world=h.scene.world;h.source_scene.render.engine='BLENDER_EEVEE';h.source_scene.render.resolution_x=640;h.source_scene.render.resolution_y=640;h.source_scene.render.resolution_percentage=100;h.source_scene.render.image_settings.file_format='PNG';h.source_scene.view_settings.view_transform='Standard'
    
    def render(label,scene=None,views=None):
        if not h.render_enabled:return
        scene=scene or h.scene;bpy.context.window.scene=scene
        for name,loc in (views or h.views).items():
            h.camera.location=loc;h.camera.rotation_euler=(h.target-h.camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(h.root/(label+'-'+name+'.png'));bpy.ops.render.render(write_still=True)
        bpy.context.window.scene=h.scene
    h.render=render
    for src,dst in h.copymap.items():
        if src.type=='MESH' and src not in [h.src_body,h.src_hair] and not any(token in src.name for token in h.config['garment_name_tokens']):
            src.hide_render=True;dst.hide_render=True
    print('HELPERS_READY')
