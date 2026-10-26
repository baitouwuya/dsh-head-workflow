# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,pathlib,json,numpy as np,collections,math
from mathutils import Matrix,Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform,tessellate_polygon
def build(cfg):
 r=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);src=bpy.data.objects[cfg['source']];m=src.data;M=np.array(src.matrix_world);V=np.array([v.co for v in m.vertices])@M[:3,:3].T+M[:3,3];F=[list(p.vertices) for p in m.polygons];C=V[np.array(F)].mean(axis=1);cy,cz=cfg['center_yz'];ry,rz=cfg['patch_radii'];sel=set(map(int,np.flatnonzero((((C[:,1]-cy)/ry)**2+((C[:,2]-cz)/rz)**2<1)&(C[:,0]>cfg['patch_min_x']))))
 uses=collections.defaultdict(list)
 for i in sel:
  for a,b in zip(F[i],F[i][1:]+F[i][:1]):uses[tuple(sorted((a,b)))].append((a,b))
 nxt={u[0][0]:u[0][1] for e,u in uses.items() if len(u)==1}
 if len(nxt)!=sum(len(u)==1 for u in uses.values()):raise RuntimeError('Patch boundary branches')
 first=min(nxt);ring=[first];p=nxt[first]
 while p!=first:
  if p in ring:raise RuntimeError('Boundary cycle broken')
  ring.append(p);p=nxt[p]
 if len(ring)!=len(nxt):raise RuntimeError('Patch must be one disk')
 theta=np.unwrap(np.arctan2((V[ring,2]-cz)/rz,(V[ring,1]-cy)/ry))
 if np.any(np.diff(theta)<=0):raise RuntimeError('Patch boundary not star-shaped')
 keep=[i for i in range(len(F)) if i not in sel];P=V.tolist();faces=[F[i] for i in keep];uvs=[[tuple(m.uv_layers.active.data[j].uv) for j in m.polygons[i].loop_indices] for i in keep];materials=[m.polygons[i].material_index for i in keep]
 smooth=lambda t:np.clip(t,0,1)**2*(3-2*np.clip(t,0,1))
 base_weight=smooth((cz+cfg['skin_transition_m']-V[:,2])/(2*cfg['skin_transition_m']))*(1-smooth((np.abs(V[:,1]-cy)-.02)/.02))*smooth((V[:,2]-.84)/.015)*smooth((V[:,0]+.015)/.02)
 weights=base_weight.tolist();loft=[]
 if cfg.get('boundary_subdivisions',1)>1:
  subdivisions=cfg['boundary_subdivisions'];edge_inserts={};newring=[]
  for a,b in zip(ring,ring[1:]+ring[:1]):
   inserts=[]
   for k in range(1,subdivisions):
    t=k/subdivisions;i=len(P);P.append(((1-t)*V[a]+t*V[b]).tolist());weights.append((1-t)*base_weight[a]+t*base_weight[b]);inserts.append(i)
   edge_inserts[(a,b)]=inserts;edge_inserts[(b,a)]=inserts[::-1];newring.extend([a]+inserts)
  newfaces=[];newuvs=[];newmaterials=[]
  for face,uv,mat in zip(faces,uvs,materials):
   polygon=[];puv=[];pcoords=[];basis=[np.array([0.,0.,0.]),np.array([1.,0.,0.]),np.array([0.,1.,0.])]
   for j,(a,b) in enumerate(zip(face,face[1:]+face[:1])):
    polygon.append(a);puv.append(uv[j]);pcoords.append(basis[j]);extra=edge_inserts.get((a,b),[])
    for k,i in enumerate(extra):
     t=(k+1)/subdivisions;polygon.append(i);puv.append(tuple((1-t)*np.array(uv[j])+t*np.array(uv[(j+1)%len(face)])));pcoords.append((1-t)*basis[j]+t*basis[(j+1)%3])
   if len(polygon)==3:newfaces.append(face);newuvs.append(uv);newmaterials.append(mat);continue
   center=len(P);P.append(np.mean([P[i] for i in face],axis=0).tolist());weights.append(float(np.mean([weights[i] for i in face])));centeruv=tuple(np.mean(uv,axis=0))
   for j in range(len(polygon)):
    k=(j+1)%len(polygon);newfaces.append([center,polygon[j],polygon[k]]);newuvs.append([centeruv,puv[j],puv[k]]);newmaterials.append(mat)
  faces,uvs,materials=newfaces,newuvs,newmaterials;ring=newring;V=np.array(P);base_weight=np.array(weights);theta=np.unwrap(np.arctan2((V[ring,2]-cz)/rz,(V[ring,1]-cy)/ry))

 source_tree=BVHTree.FromPolygons(V,F,all_triangles=True)
 def uv_of(p):
  hit,n,fi,d=source_tree.ray_cast(Vector((.1,p[1],p[2])),Vector((-1,0,0)))
  if hit is None:hit,n,fi,d=source_tree.find_nearest(Vector(p))
  tri=F[fi];f=m.polygons[fi];u=[tuple(m.uv_layers.active.data[i].uv) for i in f.loop_indices]
  x=barycentric_transform(hit,*[Vector(V[i]) for i in tri],*[Vector((*a,0)) for a in u]);return tuple(x[:2])
 vertex_uv={i:uv_of(V[i]) for i in ring}
 outer=V[ring];throat=np.column_stack((np.full(len(ring),cfg['throat_x']),cy+cfg['mouth_radii'][0]*np.cos(theta),cz+cfg['mouth_radii'][1]*np.sin(theta)))
 control1=outer.copy();control1[:,1:]=outer[:,1:]+(throat[:,1:]-outer[:,1:])*.35
 control2=throat.copy();control2[:,0]+=cfg['lip_round_m']
 throatweight=.5-.5*np.tanh(np.sin(theta)/cfg['corner_softness'])
 prev=ring
 def append_ring(points,weight,material):
  nonlocal prev
  curr=list(range(len(P),len(P)+len(points)));P.extend(points.tolist());weights.extend(weight.tolist())
  for i,p in zip(curr,points):vertex_uv[i]=uv_of(p) if material==0 else (0,0)
  for i in range(len(prev)):
   j=(i+1)%len(prev)
   for f in [[prev[i],prev[j],curr[j]],[prev[i],curr[j],curr[i]]]:
    faces.append(f);materials.append(material);uvs.append([vertex_uv[x] for x in f])
  prev=curr
 for k in range(1,cfg['lip_rows']+1):
  t=k/cfg['lip_rows'];points=(1-t)**3*outer+3*(1-t)**2*t*control1+3*(1-t)*t*t*control2+t**3*throat;w=(1-t)*base_weight[ring]+t*throatweight
  append_ring(points,w,0)
 entrance=prev.copy()
 for k in range(1,cfg['cavity_rows']):
  t=k/cfg['cavity_rows'];a=np.pi*t/2
  radii=np.array(cfg['mouth_radii'])*np.cos(a)+np.array(cfg['cavity_bulge'])*np.sin(np.pi*t)**2
  points=np.column_stack((np.full(len(ring),cfg['throat_x']-(cfg['throat_x']-cfg['rear_x'])*np.sin(a)),cy+radii[0]*np.cos(theta),cz+radii[1]*np.sin(theta)))
  w=.5+(throatweight-.5)*np.cos(a);append_ring(points,w,1)
 pole=len(P);P.append([cfg['rear_x'],cy,cz]);weights.append(.5)
 for i in range(len(prev)):faces.append([prev[i],prev[(i+1)%len(prev)],pole]);materials.append(1);uvs.append([(0,0)]*3)
 P=np.array(P);weights=np.array(weights);target=P+weights[:,None]*np.array(cfg['jaw_translation_m'])
 name='INTERNAL_ONLY_SM_patch_'+cfg['revision'];mesh=bpy.data.meshes.new(name);origin=np.array([0,cy,cz]);local=(P-origin)*1000;mesh.from_pydata(local.tolist(),[],faces);mesh.update()
 for mat in m.materials:mesh.materials.append(mat)
 if len(mesh.materials)==1:mesh.materials.append(next(mat for mat in bpy.data.materials if mat.name.startswith('INTERNAL_ONLY_own_oral_dark')))
 uv=mesh.uv_layers.new(name='UVMap')
 for f,mat,row in zip(mesh.polygons,materials,uvs):
  f.material_index=mat;f.use_smooth=True
  for i,u in zip(f.loop_indices,row):uv.data[i].uv=u
 body=bpy.data.objects.new(name,mesh);body.matrix_world=Matrix.Translation(Vector(origin))@Matrix.Scale(.001,4);body['classification']='INTERNAL_ONLY'
 scene=bpy.data.scenes.new('INTERNAL_ONLY_integrated_'+cfg['revision'])
 for o in bpy.data.scenes[cfg['reference_scene']].objects:
  if o.name==cfg['replace_object']:continue
  if '_closed_native_SM_globe__' in o.name:continue
  scene.collection.objects.link(o)
 for label in ['right','left']:scene.collection.objects.link(bpy.data.objects['INTERNAL_ONLY__'+label+'_closed_native_SM_globe__cap011'])
 scene.collection.objects.link(body);body.shape_key_add(name='Basis');k=body.shape_key_add(name='jawOpen');k.value=0;k.data.foreach_set('co',((target-origin)*1000).astype(np.float32).ravel())
 # Remove unused source points only from the new mesh; retain all original records in the source.
 audits=[]
 for deg in cfg['degrees']:
  posed=P+(target-P)*(deg/15);a=bpy.app.driver_namespace['dsh_private_topology_core']['analyze'](posed,faces,faces,np.arange(len(faces)),reference_local_vertices=P,local_vertices=posed);audits.append({'degrees':deg,**{k:a[k] for k in ['boundary_edges','nonmanifold_edges','same_direction_edges','degenerate_triangles','adjacent_normal_degrees','reference_normal_reversals']}})
 report={'classification':'INTERNAL_ONLY','status':'UNACCEPTED','profile':cfg,'object':body.name,'scene':scene.name,'removed_source_face_ids':sorted(sel),'original_boundary_vertex_ids':ring,'source_outer_faces_preserved':len(keep),'lining_faces':[i for i,m in enumerate(materials) if m==1],'entrance_vertices':entrance,'audit':audits,'source_profile':{'source':cfg['source']}}
 (r/(cfg['revision']+'-patch-mouth.json')).write_text(json.dumps(report,indent=2));return report
