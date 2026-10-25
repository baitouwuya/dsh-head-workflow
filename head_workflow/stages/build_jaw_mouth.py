# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Reconstruction stage; invoked by the head workflow runner."""

def run(h):
    import bpy,math,json,collections,numpy as np
    from mathutils import Vector,Quaternion
    
    h.set_blink(0,0)
    cy=sum(h.lip['y_range'])/2;ry=(h.lip['y_range'][1]-h.lip['y_range'][0])/2;cz=float(np.polyval(h.lip['fit_z_of_y_coefficients'],cy))
    for obj in h.scene.objects:obj.select_set(False)
    h.rig.select_set(True);bpy.context.view_layer.objects.active=h.rig
    bpy.ops.object.mode_set(mode='EDIT')
    parent=h.rig.data.edit_bones[h.config['head_bone']]
    jaw=h.rig.data.edit_bones.new('dsh_Jaw');jaw.head=(float(parent.head.x)-.006,cy,cz+.016);jaw.tail=(.016,cy,cz-.012);jaw.parent=parent;jaw.use_connect=False
    for e in h.eyes:
        name='dsh_Eye_'+('L' if e['label']=='left' else 'R')
        bone=h.rig.data.edit_bones.new(name);bone.head=e['sphere_center'];bone.tail=Vector(e['sphere_center'])+Vector((.006,0,0));bone.parent=parent;bone.use_connect=False;e['bone_name']=name
    bpy.ops.object.mode_set(mode='OBJECT')
    h.jaw=h.rig.pose.bones['dsh_Jaw'];h.jaw.rotation_mode='QUATERNION';h.jaw_axis=h.rig.data.bones['dsh_Jaw'].matrix_local.to_3x3().inverted()@Vector((0,1,0));h.jaw_axis.normalize();h.jaw_range=h.config['jaw_max_degrees']
    for obj,e in zip(h.eyeballs,h.eyes):
        obj.vertex_groups.clear();vg=obj.vertex_groups.new(name=e['bone_name']);vg.add(list(range(len(obj.data.vertices))),1,'REPLACE')
    
    def smooth(x):
        x=max(0,min(1,x));return x*x*(3-2*x)
    # Classify compact original mouth components; blue hair pieces remain rigid.
    hp=np.array([v.co[:] for v in h.src_hair.data.vertices]);h.mouth_hair_components=[]
    for ci,ids in enumerate(h.hair_components):
        a=hp[ids]
        if a[:,1].min()>cy-.015 and a[:,1].max()<cy+.015 and a[:,2].min()>cz-.016 and a[:,2].max()<cz+.007:h.mouth_hair_components.append(ci)
    h.jaw_weight_audit=[]
    for obj in [h.body,h.hair]:
        headgroup=obj.vertex_groups[h.config['head_bone']];jawgroup=obj.vertex_groups.new(name='dsh_Jaw');count=0
        for vert in obj.data.vertices:
            x,y,z=vert.co
            if x<-.045 or abs(y-cy)>.050 or z>cz+.008 or z<cz-.037:continue
            if obj==h.hair and h.work_hair_components[vert.index] not in h.mouth_hair_components:continue
            original=next((g.weight for g in vert.groups if g.group==headgroup.index),0)
            if original<1e-5:continue
            line=float(np.polyval(h.lip['fit_z_of_y_coefficients'],max(h.lip['y_range'][0],min(h.lip['y_range'][1],y))))
            base=smooth((cz+.003-z)/.016)
            local=smooth((line+.00008-z)/.00040)
            influence=math.exp(-((y-cy)/(ry*1.65))**4)
            influence*=math.exp(-((z-cz)/.012)**4)
            factor=base*(1-influence)+local*influence
            factor*=smooth((.052-abs(y-cy))/.018)
            w=original*factor
            if w>1e-6:
                headgroup.add([vert.index],original-w,'REPLACE');jawgroup.add([vert.index],w,'REPLACE');count+=1
        h.jaw_weight_audit.append({'mesh':obj.name,'jaw_weighted_vertices':count})
    # Use the closed, frontmost cut loop. Its coordinates and all front-edge weights are copied exactly.
    candidates=[p for p in h.boundaries[h.body.name]['mouth'] if p['cycle']]
    part=max(candidates,key=lambda p:p['mean_x'])
    start=part['ids'][0];ring=[];prev=None;cur=start
    while cur not in ring:
        ring.append(cur);options=[i for i in part['adj'][str(cur)] if i!=prev];prev,cur=cur,options[0]
    base=np.array([v.co[:] for v in h.body.data.vertices]);rim=base[ring]
    area=sum(rim[j,1]*rim[(j+1)%len(rim),2]-rim[(j+1)%len(rim),1]*rim[j,2] for j in range(len(rim)))
    if area<0:ring.reverse();rim=base[ring]
    h.oral_rim_source_ids=ring
    n=len(ring);verts=[];weights=[];rings=9
    headidx=h.body.vertex_groups[h.config['head_bone']].index;jawidx=h.body.vertex_groups['dsh_Jaw'].index
    rimweights=[]
    for vi in ring:
        d={g.group:g.weight for g in h.body.data.vertices[vi].groups};rimweights.append(d.get(jawidx,0))
    for row in range(rings):
        t=row/(rings-1)
        for j,p in enumerate(rim):
            q=p.copy();q[0]-=.014*t
            q[1]=cy+(p[1]-cy)*(1+.2*math.sin(math.pi*t)-.35*t)
            # Expand the inner volume behind the closed lip seam.
            mid=float(np.polyval(h.lip['fit_z_of_y_coefficients'],p[1]))
            sign=1 if p[2]>=mid else -1
            q[2]+=sign*.0028*math.sin(math.pi*t*.75)
            verts.append(q.tolist());weights.append(rimweights[j]*(1-.25*t)+.4*.25*t)
    faces=[]
    for row in range(rings-1):
        for j in range(n):faces.append([row*n+j,row*n+(j+1)%n,(row+1)*n+(j+1)%n,(row+1)*n+j])
    center=np.mean(np.array(verts[-n:]),axis=0);cap=len(verts);verts.append(center.tolist());weights.append(.4)
    for j in range(n):faces.append([(rings-1)*n+j,(rings-1)*n+(j+1)%n,cap])
    mesh=bpy.data.meshes.new('dsh-connected-oral-lining');mesh.from_pydata(verts,[],faces);mesh.update();h.oral=bpy.data.objects.new(mesh.name,mesh);h.scene.collection.objects.link(h.oral)
    mat=bpy.data.materials.new('dsh-oral-interior');mat.use_nodes=True;bs=next(nd for nd in mat.node_tree.nodes if nd.type=='BSDF_PRINCIPLED');bs.inputs['Base Color'].default_value=(.09,.014,.022,1);bs.inputs['Roughness'].default_value=.7;mesh.materials.append(mat)
    for f in mesh.polygons:f.use_smooth=True
    h.oral.parent=h.rig;hg=h.oral.vertex_groups.new(name=h.config['head_bone']);jg=h.oral.vertex_groups.new(name='dsh_Jaw')
    for i,w in enumerate(weights):hg.add([i],1-w,'REPLACE');jg.add([i],w,'REPLACE')
    mod=h.oral.modifiers.new('dsh-oral-skin','ARMATURE');mod.object=h.rig
    h.oral.shape_key_add(name='Basis',from_mix=False)
    h.old_controls=h.config['original_controls']
    for name in h.old_controls:
        sourcekey=h.body.data.shape_keys.key_blocks[name];d=np.array([sourcekey.data[i].co[:] for i in ring])-rim;arr=np.array(verts,np.float32)
        for row in range(rings):arr[row*n:(row+1)*n]+=d*(1-.5*row/(rings-1))
        arr[-1]+=d.mean(0)*.5
        key=h.oral.shape_key_add(name=name,from_mix=False);key.data.foreach_set('co',arr.ravel());key.value=0
    h.mouth_parts=[h.oral]
    # Small procedurally constructed rounded teeth.
    def solid_material(name,color,roughness):
        mat=bpy.data.materials.new(name);mat.use_nodes=True;b=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');b.inputs['Base Color'].default_value=color;b.inputs['Roughness'].default_value=roughness;return mat
    teethmat=solid_material('dsh-teeth',(.72,.68,.56,1),.45)
    tonguemat=solid_material('dsh-tongue',(.38,.07,.095,1),.62)
    def bind_part(obj,bone):
        obj.parent=h.rig;vg=obj.vertex_groups.new(name=bone);vg.add(list(range(len(obj.data.vertices))),1,'REPLACE');mod=obj.modifiers.new('dsh-mouth-skin','ARMATURE');mod.object=h.rig;h.mouth_parts.append(obj)
    for lower in [False,True]:
        for j in range(6):
            y=cy+(j-2.5)*.00080;x=.0207-.0008*(abs(j-2.5)/2.5)**2;z=cz-(.0022 if lower else .00065)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,radius=1,location=(0,0,0));obj=bpy.context.object;obj.name='dsh-'+('lower' if lower else 'upper')+'-tooth-'+str(j+1)
            for vertex in obj.data.vertices:vertex.co=(x+vertex.co.x*.00055,y+vertex.co.y*.00037,z+vertex.co.z*.00065)
            obj.data.materials.append(teethmat)
            for f in obj.data.polygons:f.use_smooth=True
            bind_part(obj,'dsh_Jaw' if lower else h.config['head_bone'])
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=1,location=(0,0,0));obj=bpy.context.object;obj.name='dsh-tongue'
    for vertex in obj.data.vertices:vertex.co=(.015+vertex.co.x*.0040,cy+vertex.co.y*.0023,cz-.0035+vertex.co.z*.0009)
    obj.data.materials.append(tonguemat)
    for f in obj.data.polygons:f.use_smooth=True
    bind_part(obj,'dsh_Jaw')
    def set_jaw(value):
        h.jaw.rotation_quaternion=Quaternion(h.jaw_axis,math.radians(h.jaw_range)*max(0,min(1,value)));bpy.context.view_layer.update()
    h.set_jaw=set_jaw
    (h.root/'jaw-and-oral-construction.json').write_text(json.dumps({'jaw_bone':'dsh_Jaw','range_degrees':h.jaw_range,'axis_bone_local':list(h.jaw_axis),'head':list(h.rig.data.bones['dsh_Jaw'].head_local),'rim_vertices':n,'oral_vertices':len(verts),'jaw_weights':h.jaw_weight_audit,'mouth_hair_components':h.mouth_hair_components},indent=2))
    h.set_jaw(0);h.render('jaw-neutral',views={'front':h.views['front']})
    h.set_jaw(1);h.render('jaw-open',views={'front':h.views['front'],'left45':h.views['left45'],'profile':h.views['profile']});h.set_jaw(0)
    print('JAW_READY',len(h.rig.data.bones),'rim',n,'parts',len(h.mouth_parts))
