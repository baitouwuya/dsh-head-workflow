# SPDX-License-Identifier: GPL-3.0-or-later
"""Continuous upper/lower Y-column strips with stationary outer boundaries."""
import bpy,collections,math,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
from .eye_plan import plan

def hull(points):
    pts=sorted(set(map(tuple,points)));cross=lambda o,a,b:np.cross(np.array(a)-o,np.array(b)-o);lo=[];hi=[]
    for p in pts:
        while len(lo)>1 and cross(lo[-2],lo[-1],p)<=0:lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi)>1 and cross(hi[-2],hi[-1],p)<=0:hi.pop()
        hi.append(p)
    return np.array(lo[:-1]+hi[:-1])

def globe(e,y,z):
    gx,gy,gz=e['sphere_center'];r=e['sphere_radius'];a=e['affine_globe']
    return gx+a['depth_scale']*math.sqrt(max(r*r*.02,r*r-(y-gy)**2-(z-gz)**2))+a['shear_y']*(y-gy)+a['shear_z']*(z-gz)

def depth_fit(points,regularization):
    points=np.array(points);center=points[:,1:3].mean(0);scale=np.ptp(points[:,1:3],axis=0).max();u=(points[:,1:3]-center)/scale
    _,ids=np.unique(np.round(u,7),axis=0,return_index=True);u=u[ids];v=points[ids,0];n=len(u)
    def kernel(d):
        r2=np.sum(d*d,axis=-1);return .5*r2*np.log(np.maximum(r2,1e-30))
    k=kernel(u[:,None]-u[None,:])+np.eye(n)*regularization;p=np.column_stack((np.ones(n),u));a=np.block([[k,p],[p.T,np.zeros((3,3))]])
    coefficients=np.linalg.solve(a,np.r_[v,np.zeros(3)])
    def evaluate(yz):
        q=(np.array(yz)-center)/scale;return kernel(q[:,None]-u[None,:])@coefficients[:n]+np.column_stack((np.ones(len(q)),q))@coefficients[n:]
    return evaluate

def build(character,cfg,appearance,atlas,atlas_meta):
    scene=bpy.context.scene;body=next(o for o in scene.objects if o.type=='MESH' and 'BodyFace' in o.name);old=body.data
    P=np.array([v.co[:] for v in old.vertices]);sourceP=P.copy();K={k.name:np.array([v.co[:] for v in k.data]) for k in old.shape_keys.key_blocks};ranges={k.name:(k.slider_min,k.slider_max) for k in old.shape_keys.key_blocks}
    groupnames=[g.name for g in body.vertex_groups];WG=[{g.group:g.weight for g in v.groups} for v in old.vertices];uv=old.uv_layers.active;normals=[tuple(n.vector) for n in old.corner_normals]
    colors={a.name:a for a in old.color_attributes if a.domain=='CORNER'};active=old.color_attributes.active_color_index;render=old.color_attributes.render_color_index
    old.calc_loop_triangles();triangles=[tuple(t.vertices) for t in old.loop_triangles];bvh=BVHTree.FromPolygons(P.tolist(),triangles,all_triangles=True)
    cut=plan(character,cfg);removed=cut['removed'];remap=cut['remap'];boundary_delta={}
    for e in cut['eyes']:
        ring=e['outer'];k=int(np.argmin(P[ring,1]));ring=ring[k:]+ring[:k];peak=int(np.argmax(P[ring,1]))
        for chain in [ring[:peak+1],list(reversed(ring[peak:]+ring[:1]))]:
            q=P[chain];t=(q[:,1]-q[0,1])/(q[-1,1]-q[0,1]);degree=min(cfg['boundary_fit_degree'],len(chain)-1)
            target=q.copy()
            for axis in [0,2]:
                fitted=np.polynomial.polynomial.polyval(t,np.polynomial.polynomial.polyfit(t,q[:,axis],degree));fitted+=(q[0,axis]-fitted[0])*(1-t)+(q[-1,axis]-fitted[-1])*t;target[:,axis]=q[:,axis]*(1-cfg['boundary_fit_strength'])+fitted*cfg['boundary_fit_strength']
            for i,d in zip(chain,target-q):boundary_delta[i]=d
    boundary=set(boundary_delta);frontier=boundary.copy();visited=boundary.copy();adj=collections.defaultdict(set)
    for edge in old.edges:
        a,b=[remap.get(i,i) for i in edge.vertices];adj[a].add(b);adj[b].add(a)
    displacement=np.zeros_like(P)
    for i,d in boundary_delta.items():displacement[i]=d
    bid=sorted(boundary);bd=np.array([boundary_delta[i] for i in bid])
    for level in range(1,cfg['boundary_fade_rings']+1):
        frontier=set().union(*(adj[i] for i in frontier))-visited;visited|=frontier
        for i in frontier:
            distances=np.linalg.norm(P[bid]-P[i],axis=1);ids=np.argsort(distances)[:3];weights=1/np.maximum(distances[ids],1e-8)**2;weights/=weights.sum();displacement[i]=weights@bd[ids]*(1-level/(cfg['boundary_fade_rings']+1))
    for a,b in remap.items():displacement[a]=displacement[b]
    # Opposite chains can contain almost equal float32 Y values. Snap those
    # columns together before tessellation instead of emitting zero-width quads.
    clusters=[]
    for i in sorted(bid,key=lambda i:P[i,1]):
        if not clusters or P[i,1]-P[clusters[-1][0],1]>1e-7:clusters.append([i])
        else:clusters[-1].append(i)
    for group in clusters:
        y=float(P[group,1].mean())
        for i in group:displacement[i,1]=y-P[i,1]
    for a,b in remap.items():displacement[a]=displacement[b]
    P+=displacement
    for name in K:K[name]+=displacement
    V=P.tolist();maps=[([i],[1.]) for i in range(len(P))];edge_splits=collections.defaultdict(list);regions=[];pose_fields={};newfaces=[]
    def sample(p):
        hit,n,ti,d=bvh.ray_cast(Vector((.15,p[1],p[2])),Vector((-1,0,0)))
        if hit is None:hit,n,ti,d=bvh.find_nearest(Vector(p))
        ids=triangles[ti];abc=[Vector(sourceP[i]) for i in ids];w=np.array(barycentric_transform(hit,*abc,Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1))));w=np.maximum(w,0);w/=w.sum();return list(ids),w.tolist()
    def add(p,mapping=None):
        i=len(V);V.append(list(p));maps.append(mapping if mapping is not None else sample(p));return i
    for e in cut['eyes']:
        ring=e['outer'];op=P[ring];poly=hull(np.array(e['rim_xyz'])[:,1:]);R=cfg['rows'];minimum=op[:,1].min();maximum=op[:,1].max()
        # Retain every source boundary column; do not create sub-float duplicate columns.
        ys=list(np.unique(op[:,1]))
        for y in np.r_[poly[:,0],np.linspace(minimum,maximum,cfg['columns'])]:
            if minimum<=y<=maximum and min(abs(np.array(ys)-y))>1e-7:ys.append(float(y))
        ys=np.array(sorted(ys))
        columns=[];vt={};newids=[];coords_by_pose={w:{} for w in [0,.25,.5,.75,1]}
        for y in ys:
            hits=[]
            for a,b in zip(ring,ring[1:]+ring[:1]):
                pa,pb=P[a],P[b]
                if min(pa[1],pb[1])-1e-12<=y<=max(pa[1],pb[1])+1e-12 and abs(pb[1]-pa[1])>1e-12:
                    t=float(np.clip((y-pa[1])/(pb[1]-pa[1]),0,1));p=pa*(1-t)+pb*t
                    if t<1e-9:i=a
                    elif t>1-1e-9:i=b
                    else:
                        i=add(p,([a,b],[1-t,t]));edge_splits[tuple(sorted((a,b)))].append((i,a,b,t))
                    hits.append((p[2],i,p))
            hits=sorted(hits,key=lambda h:h[0]);low,up=hits[0],hits[-1]
            zz=[]
            for a,b in zip(poly,np.roll(poly,-1,axis=0)):
                if min(a[0],b[0])-1e-12<=y<=max(a[0],b[0])+1e-12 and abs(a[0]-b[0])>1e-12:zz.append(a[1]+(y-a[0])/(b[0]-a[0])*(b[1]-a[1]))
            opening=len(zz)>0 and min(zz)<max(zz)-1e-10
            if zz:iz=[min(zz),max(zz)]
            else:
                endpoint=poly[int(np.argmin(abs(poly[:,0]-y)))];weight=float(np.clip(min(y-minimum,maximum-y)/max(min(endpoint[0]-minimum,maximum-endpoint[0]),1e-12),0,1));mid=(low[0]+up[0])/2;z=mid*(1-weight)+endpoint[1]*weight;iz=[z,z]
            col=[]
            for side,outer in enumerate([low,up]):
                ids=[outer[1]];vt[str(outer[1])]=0
                if cfg['row_sampling']=='uniform_z' and abs(iz[side]-outer[0])>1e-9:
                    zs=np.arange(math.ceil(min(iz[side],outer[0])/cfg['z_step']),math.floor(max(iz[side],outer[0])/cfg['z_step'])+1)*cfg['z_step'];zs=[z for z in zs if min(abs(z-outer[0]),abs(z-iz[side]))>1e-6];ts=sorted((np.array(zs)-outer[0])/(iz[side]-outer[0]))+[1.]
                else:ts=[row/R for row in range(1,R+1)]
                for t in ts:
                    if np.linalg.norm(up[2]-low[2])<1e-10:i=outer[1]
                    elif t==1 and side==1 and not opening:i=col[0][-1]
                    else:
                        z=outer[0]*(1-t)+iz[side]*t;x=outer[2][0]*(1-t)+(globe(e,y,z)+cfg['globe_clearance'])*t;i=add((x,y,z));newids.append(i);vt[str(i)]=t
                    ids.append(i)
                    for w in coords_by_pose:
                        gap=iz[1]-iz[0];closed=iz[0]+cfg['closure_fraction']*gap;overlap=cfg['closure_overlap']*min(1,gap/.003);rim=iz[side]*(1-w)+(closed+(overlap if side==0 else -overlap))*w
                        coords_by_pose[w][i]=[V[i][0],y,outer[0]*(1-t)+rim*t]
                col.append(ids)
            columns.append(col)
        # One smooth depth field per pose eliminates per-spoke pyramids.
        for w,coordinates in coords_by_pose.items():
            anchor_ids=set(ring)
            if cfg['outer_neighbor_anchors']:
                for face in old.polygons:
                    if face.index not in removed and any(i in ring for i in face.vertices):anchor_ids.update(face.vertices)
            anchors=P[sorted(anchor_ids)].tolist()
            for y,col in zip(ys,columns):
                for ids in col:
                    if y<poly[:,0].min() or y>poly[:,0].max():continue
                    i=ids[-1];p=coordinates.get(i,V[i]);anchors.append([globe(e,p[1],p[2])+cfg['globe_clearance'],p[1],p[2]])
            ids=sorted(set(newids));yz=np.array([coordinates[i][1:] for i in ids])
            if cfg['depth_mode'] in ['linear_globe','shell_blend']:
                depth_values={}
                for y,col in zip(ys,columns):
                    for strip in col:
                        outer=np.array(V[strip[0]]);inner=coordinates.get(strip[-1],V[strip[-1]]);inside_y=poly[:,0].min()<=y<=poly[:,0].max();inner_x=globe(e,inner[1],inner[2])+cfg['globe_clearance']
                        if not inside_y:
                            if cfg['cap_depth']=='rim_blend':
                                bottom=np.array(V[col[0][0]]);top=np.array(V[col[1][0]]);fraction=float(np.clip((inner[2]-bottom[2])/max(top[2]-bottom[2],1e-12),0,1));cap_x=bottom[0]*(1-fraction)+top[0]*fraction
                                endpoint=poly[int(np.argmin(abs(poly[:,0]-y)))];u=(y-minimum)/max(endpoint[0]-minimum,1e-12) if y<poly[:,0].min() else (maximum-y)/max(maximum-endpoint[0],1e-12);u=float(np.clip(u,0,1));u=u*u*(3-2*u);inner_x=cap_x*(1-u)+(globe(e,*endpoint)+cfg['globe_clearance'])*u
                            else:
                                hit,_,_,_=bvh.ray_cast(Vector((.15,inner[1],inner[2])),Vector((-1,0,0)))
                                inner_x=hit.x if hit is not None else outer[0]
                        for i in strip[1:]:
                            t=vt.get(str(i),0)
                            if cfg['depth_mode']=='shell_blend':
                                p=coordinates.get(i,V[i]);shell=globe(e,p[1],p[2])+cfg['globe_clearance']+(outer[0]-globe(e,outer[1],outer[2])-cfg['globe_clearance'])*(1-t)**cfg['boundary_residual_power']
                                if not inside_y:
                                    bottom=np.array(V[col[0][0]]);top=np.array(V[col[1][0]]);fraction=float(np.clip((p[2]-bottom[2])/max(top[2]-bottom[2],1e-12),0,1));base_x=bottom[0]*(1-fraction)+top[0]*fraction
                                    endpoint=poly[int(np.argmin(abs(poly[:,0]-y)))];u=(y-minimum)/max(endpoint[0]-minimum,1e-12) if y<poly[:,0].min() else (maximum-y)/max(maximum-endpoint[0],1e-12);u=float(np.clip(u,0,1));u=u*u*(3-2*u);shell=base_x*(1-u)+shell*u
                                depth_values[i]=shell
                            else:depth_values[i]=outer[0]*(1-t)+inner_x*t
                x=np.array([depth_values[i] for i in ids])
            else:
                fit=depth_fit(anchors,cfg['depth_regularization']);x=fit(yz)
            for i,depth in zip(ids,x):
                yz=np.array(coordinates[i][1:]);inside=all(np.cross(b-a,yz-a)>=-1e-12 for a,b in zip(poly,np.roll(poly,-1,axis=0)))
                if cfg['globe_floor'] and inside:depth=max(depth,globe(e,*yz)+cfg['globe_clearance'])
                coordinates[i][0]=float(depth)
        for i in set(newids):V[i]=coords_by_pose[0][i];maps[i]=sample(V[i])
        region={'eye':e['label'],'outer':ring,'removedFaces':sorted(e['removed']),'new_vertices':sorted(set(newids)),'vertex_t':vt,'faces':[],'rows':R,'columns':len(ys)}
        for left,right in zip(columns,columns[1:]):
            for side in [0,1]:
                a,b=left[side],right[side];i=j=0
                while i<len(a)-1 or j<len(b)-1:
                    advance_a=j==len(b)-1 or (i<len(a)-1 and np.linalg.norm(np.array(V[a[i+1]])[1:]-np.array(V[b[j]])[1:])<np.linalg.norm(np.array(V[a[i]])[1:]-np.array(V[b[j+1]])[1:]))
                    if advance_a:ids=[a[i],b[j],a[i+1]];i+=1
                    else:ids=[a[i],b[j],b[j+1]];j+=1
                    if side==1:ids.reverse()
                    ids=list(dict.fromkeys(ids))
                    if len(ids)>=3:newfaces.append((ids,region))
        for w in [.25,.5,.75,1]:pose_fields['blink'+e['label'].capitalize()+'_'+str(int(w*100))]=coords_by_pose[w]
        regions.append(region)
    # Split retained boundary edges to share every added column vertex exactly.
    faces=[];uvs=[];mis=[];ns=[];cs={name:[] for name in colors};materials=list(old.materials)
    for f in old.polygons:
        if f.index in removed:continue
        ids=[];fu=[];fn=[];fc={name:[] for name in colors};oldids=list(f.vertices);loops=list(f.loop_indices)
        for j,(oa,ob) in enumerate(zip(oldids,oldids[1:]+oldids[:1])):
            a,b=remap.get(oa,oa),remap.get(ob,ob);li,lj=loops[j],loops[(j+1)%len(loops)];entries=[(0,a)]
            for i,sa,sb,t in edge_splits.get(tuple(sorted((a,b))),[]):entries.append((t if a==sa else 1-t,i))
            for t,i in sorted(set(entries)):
                ids.append(i);fu.append(tuple(np.array(uv.data[li].uv)*(1-t)+np.array(uv.data[lj].uv)*t));fn.append((0,0,0) if a in visited or b in visited else tuple(np.array(normals[li])*(1-t)+np.array(normals[lj])*t))
                for name,attr in colors.items():fc[name].append(tuple(np.array(attr.data[li].color)*(1-t)+np.array(attr.data[lj].color)*t))
        if len(ids)>len(oldids):
            # A polygon with many collinear edge splits can produce numerical
            # sliver triangles in Blender's ngon tessellator. Use an interior
            # source-face point and keep every boundary segment explicitly.
            center=add(P[[remap.get(i,i) for i in oldids]].mean(0), (oldids,[1/len(oldids)]*len(oldids)))
            center_uv=np.mean([uv.data[li].uv[:] for li in loops],axis=0);center_normal=np.mean([normals[li] for li in loops],axis=0);center_normal/=max(np.linalg.norm(center_normal),1e-30)
            center_colors={name:np.mean([attr.data[li].color[:] for li in loops],axis=0) for name,attr in colors.items()}
            for j,(a,b) in enumerate(zip(ids,ids[1:]+ids[:1])):
                if a==b:continue
                k=(j+1)%len(ids);faces.append([center,a,b]);uvs.append([center_uv,fu[j],fu[k]]);mis.append(f.material_index);ns.append([tuple(center_normal),fn[j],fn[k]])
                for name in colors:cs[name].append([center_colors[name],fc[name][j],fc[name][k]])
        else:
            faces.append(ids);uvs.append(fu);mis.append(f.material_index);ns.append(fn)
            for name in colors:cs[name].append(fc[name])
    mat=bpy.data.materials.new('dsh-continuous-eyelid-skin');mat.use_nodes=True;bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bs.inputs['Roughness'].default_value=appearance['roughness'];image=bpy.data.images.load(str(atlas),check_existing=False);image.pack();tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image;mat.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color']);materials.append(mat)
    for ids,region in newfaces:
        region['faces'].append(len(faces));faces.append(ids);mis.append(len(materials)-1);ns.append([(0,0,0)]*len(ids));uvs.append([(.5-(V[i][1]-atlas_meta['center_y'])/atlas_meta['scale'],.5+(V[i][2]-atlas_meta['center_z'])/atlas_meta['scale']) for i in ids])
        for name in colors:cs[name].append([(1,1,1,1)]*len(ids))
    mesh=bpy.data.meshes.new('dsh-continuous-eye-strips');mesh.from_pydata(V,[],faces);mesh.update()
    for m in materials:mesh.materials.append(m)
    layer=mesh.uv_layers.new(name=uv.name)
    for f,values,mi in zip(mesh.polygons,uvs,mis):
        f.material_index=mi;f.use_smooth=True
        for li,value in zip(f.loop_indices,values):layer.data[li].uv=value
    for name,values in cs.items():
        attr=mesh.color_attributes.new(name=name,type=colors[name].data_type,domain='CORNER')
        for f,cols in zip(mesh.polygons,values):
            for li,col in zip(f.loop_indices,cols):attr.data[li].color=col
    if colors:mesh.color_attributes.active_color_index=active;mesh.color_attributes.render_color_index=render
    mesh.normals_split_custom_set([n for row in ns for n in row]);body.data=mesh;newbase=np.array(V,np.float32)
    for name,values in K.items():
        arr=newbase.copy()
        if not name.startswith('blink'):
            arr[:len(P)]=values
            for i in range(len(P),len(V)):
                ids,weights=maps[i];arr[i]+=sum((values[j]-K['Basis'][j])*w for j,w in zip(ids,weights))
        for i,p in pose_fields.get(name,{}).items():arr[i]=p
        key=body.shape_key_add(name=name);key.data.foreach_set('co',arr.ravel());key.slider_min,key.slider_max=ranges[name];key.value=0
    for name in groupnames:
        if not body.vertex_groups.get(name):body.vertex_groups.new(name=name)
    for i,(ids,weights) in enumerate(maps):
        groups=collections.defaultdict(float)
        for j,w in zip(ids,weights):
            for group,value in WG[j].items():groups[group]+=w*value
        for group,w in groups.items():
            if w>1e-8:body.vertex_groups[group].add([i],float(w),'REPLACE')
    bpy.context.view_layer.update()
    return {'method':'Y-monotone vertical strips','regions':regions,'growth':cut['growth'],'old_vertex_count':len(P),'new_vertex_count':len(V),'removed_faces':len(removed),'boundary_max_shift':float(np.linalg.norm(displacement,axis=1).max())}
