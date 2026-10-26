# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Localized Loop refinement; original vertex indices and control deltas survive."""
import bpy,collections,math,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from .eyes import globe,hull

def run(profile):
    obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and 'BodyFace' in o.name);reports=[]
    for level in range(profile['geometry']['subdivision']['levels']):
        m=obj.data;P=np.array([v.co[:] for v in m.vertices]);K={k.name:np.array([v.co[:] for v in k.data]) for k in m.shape_keys.key_blocks};ranges={k.name:(k.slider_min,k.slider_max) for k in m.shape_keys.key_blocks};N=len(P)
        groups=[g.name for g in obj.vertex_groups];weights=[{g.group:g.weight for g in v.groups} for v in m.vertices]
        tokens={};reps=[];canon=[]
        for i,p in enumerate(P):
            token=tuple(np.round(p,7))
            if token not in tokens:tokens[token]=len(reps);reps.append(i)
            canon.append(tokens[token])
        canon=np.array(canon);reps=np.array(reps);m.calc_loop_triangles();triangles=[t for t in m.loop_triangles];audit=m.attributes.get('dsh_repair_audit');data=[];edge_opp=collections.defaultdict(list);incident=collections.defaultdict(list);neighbors=collections.defaultdict(set);split_edges=set()
        for ti,t in enumerate(triangles):
            face=m.polygons[t.polygon_index];material=m.materials[face.material_index].name;selected='dsh-continuous-eyelid' in material or (audit and audit.data[face.index].value and 'SEM_new_lip' not in material and 'oral-interior' not in material)
            ids=list(t.vertices);ci=canon[ids];data.append((ids,list(t.loops),face.material_index,bool(selected)))
            for i in ci:incident[int(i)].append(bool(selected))
            for a,b,c in [(ci[0],ci[1],ci[2]),(ci[1],ci[2],ci[0]),(ci[2],ci[0],ci[1])]:
                if a==b:continue
                edge=tuple(sorted((int(a),int(b))));edge_opp[edge].append(int(c));neighbors[int(a)].add(int(b));neighbors[int(b)].add(int(a))
                if selected:split_edges.add(edge)
        smooth_maps={};boundary={i for edge,op in edge_opp.items() if len(set(op))!=2 for i in edge}
        for i,flags in incident.items():
            if not all(flags) or i in boundary:continue
            ns=sorted(neighbors[i]);n=len(ns)
            if n<3:continue
            beta=(.625-(.375+.25*math.cos(2*math.pi/n))**2)/n;smooth_maps[i]=([int(reps[i])]+[int(reps[j]) for j in ns],[1-n*beta]+[beta]*n)
        mappings=[([i],[1.]) for i in range(N)];parameter_maps=[([i],[1.]) for i in range(N)];newP=P.copy()
        for i,(ids,ws) in smooth_maps.items():
            delta=np.array(ws)@P[ids]-P[reps[i]];newP[canon==i]+=delta
        positions=newP.tolist();edge_new={}
        for edge in sorted(split_edges):
            a,b=edge;op=sorted(set(edge_opp[edge]));ids=[int(reps[a]),int(reps[b])];ws=[.5,.5]
            if len(op)==2:ids +=[int(reps[x]) for x in op];ws=[.375,.375,.125,.125]
            edge_new[edge]=len(positions);mappings.append((ids,ws));parameter_maps.append(([int(reps[a]),int(reps[b])],[.5,.5]));positions.append((np.array(ws)@P[ids]).tolist())
        uv=m.uv_layers.active;normals=[tuple(n.vector) for n in m.corner_normals];colors={a.name:a for a in m.color_attributes if a.domain=='CORNER'};color_types={n:a.data_type for n,a in colors.items()};outfaces=[];outuv=[];outnorm=[];outcolors={n:[] for n in colors};outmat=[];outaudit=[]
        def emit(ids,corner_weights,source_loops,material,selected):
            outfaces.append(ids);outmat.append(material);outaudit.append(selected);source_uv=np.array([uv.data[i].uv[:] for i in source_loops]);outuv.append([np.array(w)@source_uv for w in corner_weights]);source_norm=np.array([normals[i] for i in source_loops]);outnorm.append([(0,0,0) if selected else tuple(np.array(w)@source_norm) for w in corner_weights])
            for name,attr in colors.items():
                source=np.array([attr.data[i].color[:] for i in source_loops]);outcolors[name].append([np.array(w)@source for w in corner_weights])
        I=np.eye(3)
        for ids,loops,material,selected in data:
            mids=[edge_new.get(tuple(sorted((int(canon[ids[j]]),int(canon[ids[(j+1)%3]]))))) for j in range(3)]
            if all(i is not None for i in mids):
                a,b,c=ids;ab,bc,ca=mids;wa,wb,wc=I;wab=(wa+wb)/2;wbc=(wb+wc)/2;wca=(wc+wa)/2
                for f,ws in [([a,ab,ca],[wa,wab,wca]),([b,bc,ab],[wb,wbc,wab]),([c,ca,bc],[wc,wca,wbc]),([ab,bc,ca],[wab,wbc,wca])]:emit(f,ws,loops,material,True)
            elif any(i is not None for i in mids):
                center=len(positions);positions.append(P[ids].mean(0).tolist());mappings.append((ids,[1/3]*3));parameter_maps.append((ids,[1/3]*3));poly=[];pw=[]
                for j,i in enumerate(ids):
                    poly.append(i);pw.append(I[j])
                    if mids[j] is not None:poly.append(mids[j]);pw.append((I[j]+I[(j+1)%3])/2)
                for j in range(len(poly)):emit([center,poly[j],poly[(j+1)%len(poly)]],[[1/3]*3,pw[j],pw[(j+1)%len(poly)]],loops,material,True)
            else:emit(ids,I,loops,material,selected)
        newbase=np.array(positions);allkeys={}
        for name,values in K.items():
            arr=newbase.copy()
            if name.startswith('blink'):
                arr[:N]=values
                for ci,(ids,ws) in smooth_maps.items():arr[np.flatnonzero(canon==ci)]+=np.array(ws)@values[ids]-values[reps[ci]]
                for i in range(N,len(arr)):
                    ids,ws=mappings[i];arr[i]=np.array(ws)@values[ids]
            else:
                arr[:N]+=values-K['Basis']
                for i in range(N,len(arr)):
                    ids,ws=mappings[i];arr[i]+=np.array(ws)@(values[ids]-K['Basis'][ids])
            allkeys[name]=arr
        # Skin is allowed to refine but may not cut into the unchanged globes.
        active=set(i for ids,flag in zip(outfaces,outaudit) if flag for i in ids)
        def floor(arr):
            for eye in profile['character']['eyes']:
                poly=hull(np.array(eye['rim_xyz'])[:,1:]);ids=np.array(sorted(active),int);yz=arr[ids,1:];inside=np.ones(len(ids),bool)
                for a,b in zip(poly,np.roll(poly,-1,axis=0)):inside&=((b[0]-a[0])*(yz[:,1]-a[1])-(b[1]-a[1])*(yz[:,0]-a[0]))>=-1e-12
                for i in ids[inside]:arr[i,0]=max(arr[i,0],globe(eye,*arr[i,1:])+profile['geometry']['eyes']['globe_clearance'])
        reprojection=[]
        if profile['geometry']['subdivision']['reproject']:
            for name in ['Basis']+[name for name in allkeys if name.startswith('blink')]:
                smooth=allkeys[name];bvh=BVHTree.FromPolygons(smooth.tolist(),outfaces,all_triangles=True);linear=np.empty_like(smooth);linear[:N]=K[name]
                for i in range(N,len(linear)):
                    ids,ws=parameter_maps[i];linear[i]=np.array(ws)@K[name][ids]
                misses=0
                for i in active:
                    point,_,_,_=bvh.ray_cast(Vector((.2,float(linear[i,1]),float(linear[i,2]))),Vector((-1,0,0)))
                    if point is not None:linear[i,0]=point.x
                    else:misses+=1;linear[i,0]=smooth[i,0]
                allkeys[name]=linear;reprojection.append({'pose':name,'misses':misses})
            for name,values in K.items():
                if name=='Basis' or name.startswith('blink'):continue
                arr=allkeys['Basis'].copy();arr[:N]+=values-K['Basis']
                for i in range(N,len(arr)):
                    ids,ws=parameter_maps[i];arr[i]+=np.array(ws)@(values[ids]-K['Basis'][ids])
                allkeys[name]=arr
            newbase=allkeys['Basis'].copy();mappings=parameter_maps
        floor(allkeys['Basis']);base_delta=allkeys['Basis']-newbase
        for name in allkeys:
            if name=='Basis':continue
            if name.startswith('blink'):floor(allkeys[name])
            else:allkeys[name]+=base_delta
        materials=list(m.materials);mesh=bpy.data.meshes.new('dsh-refined-continuous-eyelids');mesh.from_pydata(allkeys['Basis'].tolist(),[],outfaces);mesh.update()
        for mat in materials:mesh.materials.append(mat)
        layer=mesh.uv_layers.new(name=uv.name);flag=mesh.attributes.new(name='dsh_repair_audit',type='BOOLEAN',domain='FACE')
        for f,mi,us,selected in zip(mesh.polygons,outmat,outuv,outaudit):
            f.material_index=mi;f.use_smooth=True;flag.data[f.index].value=selected
            for li,value in zip(f.loop_indices,us):layer.data[li].uv=value
        for name,values in outcolors.items():
            attr=mesh.color_attributes.new(name=name,type=color_types[name],domain='CORNER')
            for f,vs in zip(mesh.polygons,values):
                for li,v in zip(f.loop_indices,vs):attr.data[li].color=v
        mesh.normals_split_custom_set([n for ns in outnorm for n in ns]);obj.data=mesh
        for name,values in allkeys.items():
            key=obj.shape_key_add(name=name);key.data.foreach_set('co',values.astype(np.float32).ravel());key.slider_min,key.slider_max=ranges[name];key.value=0
        for name in groups:
            if not obj.vertex_groups.get(name):obj.vertex_groups.new(name=name)
        for i,(ids,ws) in enumerate(mappings):
            values=collections.defaultdict(float)
            for j,w in zip(ids,ws):
                for gi,gw in weights[j].items():values[gi]+=w*gw
            for gi,w in values.items():
                if w>1e-8:obj.vertex_groups[gi].add([i],float(w),'REPLACE')
        reports.append({'level':level+1,'vertices_before':N,'vertices_after':len(positions),'faces_after':len(outfaces),'smoothed_canonical_vertices':len(smooth_maps),'split_edges':len(edge_new),'reprojection':reprojection})
        print('LOCAL_SUBDIVISION',reports[-1],flush=True)
    bpy.context.view_layer.update();return reports
