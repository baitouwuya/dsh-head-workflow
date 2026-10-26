# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,json,math,collections,numpy as np
from mathutils import Vector,Quaternion
from mathutils.bvhtree import BVHTree
def measure(profile_all,manifest,construction,out):
    profile=profile_all['character'];sampling=profile_all['sampling'];man=manifest;c=construction
    bpy.ops.wm.open_mainfile(filepath=str(out/'head.blend'));body=next(o for o in bpy.context.scene.objects if o.type=='MESH' and 'BodyFace' in o.name);rimcoords=np.array([body.matrix_world@body.data.vertices[i].co for i in c['regions']['mouth']['rim_indices']]);bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(out/'head.glb'));meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE');jaw=rig.pose.bones[man['jaw']['bone']];jaw.rotation_mode='QUATERNION';axis=rig.data.bones[jaw.name].matrix_local.to_3x3().inverted()@Vector(man['jaw']['axis_blender_rig']);axis.normalize()
    def apply(vals):
     for o in meshes:
      if not o.data.shape_keys:continue
      ks=o.data.shape_keys.key_blocks
      for k in ks:k.value=0
      for n,v in vals.items():
       if n in ks:ks[n].value=v
      for cname,spec in man.get('automatic_correctives',{}).items():
       if cname in ks:ks[cname].value=float(np.interp(vals.get('degrees',0),[p[0] for p in spec['points']],[p[1] for p in spec['points']])) if 'points' in spec else max(0,min(1,vals.get('degrees',0)/spec['angle_degrees']))
      for side in ['Left','Right']:
       w=max(vals.get('blink',0),vals.get('blink'+side,0));st=int(w*4);t=w*4-st
       for q,v in [(st*25,1-t),((st+1)*25,t)]:
        if 'blink'+side+'_'+str(q) in ks:ks['blink'+side+'_'+str(q)].value=v
     jaw.rotation_quaternion=Quaternion(axis,math.radians(vals.get('degrees',0)));bpy.context.view_layer.update()
    def world(o):return np.array([o.matrix_world@v.co for v in o.data.vertices])
    body=next(o for o in meshes if 'BodyFace' in o.name);base=world(body);ridx=[int(np.argmin(np.linalg.norm(base-p,axis=1))) for p in rimcoords]
    def evaluated():
     ts=[];dg=bpy.context.evaluated_depsgraph_get();bp=None
     for o in meshes:
      ev=o.evaluated_get(dg);m=ev.to_mesh();v=[o.matrix_world@x.co for x in m.vertices];ts.append((o.name,BVHTree.FromPolygons(v,[list(f.vertices) for f in m.polygons])))
      if o==body:bp=np.array(v)
      ev.to_mesh_clear()
     return ts,bp

    def hull(points):
     pts=sorted(set(tuple(map(float,p)) for p in points));cross=lambda o,a,b:(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);lo=[];hi=[]
     for p in pts:
      while len(lo)>=2 and cross(lo[-2],lo[-1],p)<=0:lo.pop()
      lo.append(p)
     for p in reversed(pts):
      while len(hi)>=2 and cross(hi[-2],hi[-1],p)<=0:hi.pop()
      hi.append(p)
     return np.array(lo[:-1]+hi[:-1])
    def domain(poly,nx=121,nz=61):
     for x in np.linspace(poly[:,0].min(),poly[:,0].max(),nx)[1:-1]:
      zs=[]
      for a,b in zip(poly,np.roll(poly,-1,axis=0)):
       if min(a[0],b[0])<=x<=max(a[0],b[0]) and abs(a[0]-b[0])>1e-12:zs.append(a[1]+(x-a[0])/(b[0]-a[0])*(b[1]-a[1]))
      if len(zs)>1:
       for z in np.linspace(min(zs),max(zs),nz)[1:-1]:yield x,z

    def first(ts,origin,direction):
     hits=[]
     for name,t in ts:
      p,n,fi,d=t.ray_cast(Vector(origin),Vector(direction))
      if p is not None:hits.append((d,name,list(p),fi))
     return min(hits) if hits else None
    report={'input':'head.glb','blender':bpy.app.version_string,'rim_mapping_max_error':float(max(np.linalg.norm(base[i]-p) for i,p in zip(ridx,rimcoords))),'eyes':[],'mouth':[],'globes':[],'jaw_rest':list(map(list,rig.data.bones[jaw.name].matrix_local))}
    apply({'blink':1});ts,_=evaluated()
    for e in profile['eyes']:
     failed=[];count=0
     for y,z in domain(hull(np.array(e['rim_xyz'])[:,1:]),*sampling['eye_grid']):
      h=first(ts,(.15,y,z),(-1,0,0));count+=1
      if not h or 'closed-globe' in h[1]:failed.append([y,z,h])
     report['eyes'].append({'side':e['label'],'rays':count,'exposed_or_empty':len(failed),'failures':failed})
    for deg in sampling['jaw_degrees']:
     apply({'degrees':deg});ts,bp=evaluated();rim=bp[ridx]
     for angle in sampling['mouth_views']:
      rad=math.radians(angle);forward=np.array([math.cos(rad),math.sin(rad),0]);right=np.array([-math.sin(rad),math.cos(rad),0]);up=np.array([0,0,1]);poly=hull(np.array([rim@right,rim@up]).T);fails=[];count=0;names=collections.Counter();semantics=collections.Counter();occluders=[]
      for u,v in domain(poly,*sampling['mouth_grid']):
       origin=right*u+up*v+forward*.15;h=first(ts,origin,-forward);count+=1
       if h:
        names[h[1]]+=1;obj=next(o for o in meshes if o.name==h[1]);mat=obj.data.materials[obj.data.polygons[h[3]].material_index].name;part='lining' if 'oral-interior' in mat else 'teeth' if 'tooth' in obj.name else 'tongue' if 'tongue' in obj.name else 'new_lip' if 'SEM_new_lip' in mat else 'source_skin_or_other';semantics[part]+=1
        center=poly.mean(0);radial=np.array([u,v])-center;shrunk=poly*sampling['mouth_inner_fraction']+center*(1-sampling['mouth_inner_fraction']);crosses=[np.cross(b-a,np.array([u,v])-a) for a,b in zip(shrunk,np.roll(shrunk,-1,axis=0))];inner=all(x>=-1e-12 for x in crosses);rimdist=float(np.linalg.norm(rim-np.array(h[2]),axis=1).min())
        if deg>0 and inner and (part=='source_skin_or_other' or (part=='new_lip' and rimdist>sampling['lip_occluder_distance'])):occluders.append({'sample':[u,v],'first_hit':h,'part':part,'material':mat,'distance_to_rim':rimdist})
       if not h or h[2][0]<sampling['mouth_posterior_plane']:fails.append([u,v,h])
      report['mouth'].append({'degrees':deg,'view_degrees':angle,'domain':'convex projected deformed entrance rim; includes possible occluding lips','projected_hull':poly.tolist(),'rays':count,'empty_or_posterior_hits':len(fails),'failures':fails,'first_hit_meshes':dict(names),'first_hit_semantics':dict(semantics),'unwanted_corridor_occluders':len(occluders),'occluder_faces':occluders,'jaw_matrix_basis':list(map(list,jaw.matrix_basis))})
    apply({})
    for o in meshes:
     if 'closed-globe' not in o.name:continue
     v=world(o);_,inv=np.unique(np.round(v,7),axis=0,return_inverse=True);ec=collections.Counter()
     for f in o.data.polygons:
      ids=[int(inv[i]) for i in f.vertices]
      for i,j in zip(ids,ids[1:]+ids[:1]):ec[tuple(sorted((i,j)))]+=1
     report['globes'].append({'name':o.name,'boundary':sum(n==1 for n in ec.values()),'nonmanifold':sum(n!=2 for n in ec.values())})
    report['skin']={o.name:{'vertices':len(o.data.vertices),'nonfinite_weights':sum(not math.isfinite(g.weight) for v in o.data.vertices for g in v.groups),'max_weight_sum_error':max((abs(sum(g.weight for g in v.groups)-1) for v in o.data.vertices if v.groups),default=0)} for o in meshes}

    return report
