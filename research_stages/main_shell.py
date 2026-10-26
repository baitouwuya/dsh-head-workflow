# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,bmesh,pathlib,json,numpy as np,collections,math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
def build(cfg):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);src=bpy.data.objects[cfg['source']];m=src.data;M=np.array(src.matrix_world,float);units=float(np.linalg.norm(M[:3,0]));world=lambda p:np.asarray(p)@M[:3,:3].T+M[:3,3]
    base=np.array([list(x.co) for x in m.shape_keys.key_blocks['Basis'].data]);target=np.array([list(x.co) for x in m.shape_keys.key_blocks['jawOpen'].data]);fs=[list(f.vertices) for f in m.polygons];edges=collections.defaultdict(list)
    for i,t in enumerate(fs):
        for a,b in zip(t,t[1:]+t[:1]):edges[tuple(sorted((a,b)))].append(i)
    adj=collections.defaultdict(set)
    for edge,uses in edges.items():
        if len(uses)==2:adj[uses[0]].add(uses[1]);adj[uses[1]].add(uses[0])
    todo=set(range(len(fs)));groups=[]
    while todo:
        seed=todo.pop();g=[seed];stack=[seed]
        while stack:
            for i in adj[stack.pop()]:
                if i in todo:todo.remove(i);g.append(i);stack.append(i)
        groups.append(sorted(g))
    groups.sort(key=len,reverse=True)
    def subset(fids,name):
        used=sorted({v for i in fids for v in fs[i]});mapping={old:i for i,old in enumerate(used)}
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(base[used].tolist(),[],[[mapping[v] for v in fs[i]] for i in fids]);mesh.update()
        for mat in m.materials:mesh.materials.append(mat)
        uv=mesh.uv_layers.new(name='UVMap')
        for new,old in zip(mesh.polygons,fids):
            new.material_index=m.polygons[old].material_index;new.use_smooth=True
            for nl,ol in zip(new.loop_indices,m.polygons[old].loop_indices):uv.data[nl].uv=m.uv_layers.active.data[ol].uv
        return mesh,used
    quarantine=bpy.data.scenes.new('INTERNAL_ONLY_fragments_'+cfg['revision']);fragments=[]
    for gi,g in enumerate(groups[1:]):
        verts=world(base[list({v for i in g for v in fs[i]})]);lo=verts.min(axis=0);hi=verts.max(axis=0)
        if len(g)>cfg['maximum_fragment_faces'] or lo[0]<.005 or max(abs(lo[1]-.0011646),abs(hi[1]-.0011646))>.012 or lo[2]<.865 or hi[2]>.89:raise RuntimeError('Unexpected fragment outside authorized local mouth repair')
        mesh,used=subset(g,'INTERNAL_ONLY_retained_boolean_fragment_'+cfg['revision']+'_'+str(gi));o=bpy.data.objects.new(mesh.name,mesh);quarantine.collection.objects.link(o);o.matrix_world=src.matrix_world.copy();o['classification']='INTERNAL_ONLY';o['status']='RETAINED_BOOLEAN_FRAGMENT_NOT_IN_ASSEMBLY'
        fragments.append({'object':o.name,'source_faces':g,'bounds':[lo.tolist(),hi.tolist()]})
    mesh,used=subset(groups[0],'INTERNAL_ONLY_main_'+cfg['revision'])
    bm=bmesh.new();bm.from_mesh(mesh)
    short=[e for e in bm.edges if e.calc_length()*units<cfg.get('collapse_short_edges_m',0)]
    if short:bmesh.ops.collapse(bm,edges=short,uvs=False)
    bm.normal_update();cy,cz=cfg['center_yz'];selected=[]
    if cfg.get('beautify_method'):
        roi=[f for f in bm.faces if abs(world(f.calc_center_median())[1]-cy)<.018 and abs(world(f.calc_center_median())[2]-cz)<.018 and world(f.calc_center_median())[0]>-.012]
        roi_set=set(roi);es=[e for e in bm.edges if len(e.link_faces)==2 and all(f in roi_set for f in e.link_faces) and e.link_faces[0].material_index==e.link_faces[1].material_index]
        bmesh.ops.beautify_fill(bm,faces=roi,edges=es,method=cfg['beautify_method'])
        bm.normal_update()
    if cfg.get('dissolve_degrees'):
        region=[e for e in bm.edges if world(sum((v.co for v in e.verts),Vector())/2)[0]>-.012 and abs(world(sum((v.co for v in e.verts),Vector())/2)[1]-cy)<.018 and abs(world(sum((v.co for v in e.verts),Vector())/2)[2]-cz)<.018]
        bmesh.ops.dissolve_limit(bm,angle_limit=math.radians(cfg['dissolve_degrees']),use_dissolve_boundaries=False,verts=[],edges=region,delimit={'MATERIAL'})
        bmesh.ops.triangulate(bm,faces=list(bm.faces),quad_method='BEAUTY',ngon_method='BEAUTY');bm.normal_update()
    for e in bm.edges:
        midpoint=Vector(world(sum((v.co for v in e.verts),Vector())/2))
        if len(e.link_faces)==2 and midpoint.x>.005 and abs(midpoint.y-cy)<.015 and abs(midpoint.z-cz)<.015 and e.calc_face_angle()>math.radians(cfg['bevel_above_degrees']):selected.append(e)
    count=len(selected)
    if cfg['bevel_width_m']>0:bmesh.ops.bevel(bm,geom=selected,offset=cfg['bevel_width_m']/units,segments=cfg['bevel_segments'],affect='EDGES',clamp_overlap=True)
    bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free();mesh.update()
    tree=BVHTree.FromPolygons(base.tolist(),fs,all_triangles=True);out=[];errors=[]
    for v in mesh.vertices:
        hit,n,fi,d=tree.find_nearest(v.co);tri=fs[fi];weights=barycentric_transform(hit,*[Vector(base[i]) for i in tri],Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)));weights=np.maximum(np.array(weights),0);weights/=weights.sum();delta=weights@(target[tri]-base[tri]);out.append(np.array(v.co)+delta);errors.append(d)
    body=bpy.data.objects.new('INTERNAL_ONLY_SM_main_'+cfg['revision'],mesh);scene=bpy.data.scenes.new('INTERNAL_ONLY_integrated_'+cfg['revision'])
    for o in bpy.data.scenes[cfg['source_scene']].objects:
        if o!=src:scene.collection.objects.link(o)
    scene.collection.objects.link(body);body.matrix_world=src.matrix_world.copy();body.shape_key_add(name='Basis');key=body.shape_key_add(name='jawOpen');key.value=0;key.data.foreach_set('co',np.array(out,np.float32).ravel())
    v=np.array([list(x.co) for x in mesh.vertices]);f=[list(x.vertices) for x in mesh.polygons];audit=[]
    for deg in cfg['degrees']:
        posed=v+(np.array(out)-v)*(deg/15);a=bpy.app.driver_namespace['dsh_private_topology_core']['analyze'](world(posed),f,f,np.arange(len(f)),reference_local_vertices=world(v),local_vertices=world(posed));audit.append({'degrees':deg,**{k:a[k] for k in ['boundary_edges','nonmanifold_edges','same_direction_edges','degenerate_triangles','adjacent_normal_degrees','reference_normal_reversals']}})
    lining=[f.index for f in mesh.polygons if f.material_index==1];uses=collections.defaultdict(list)
    for fi,poly in enumerate(mesh.polygons):
        t=list(poly.vertices)
        for a,b in zip(t,t[1:]+t[:1]):uses[tuple(sorted((a,b)))].append(fi)
    seam=[e for e,u in uses.items() if len(u)==2 and (mesh.polygons[u[0]].material_index==1)!=(mesh.polygons[u[1]].material_index==1)]
    report={'classification':'INTERNAL_ONLY','status':'UNACCEPTED','profile':cfg,'source_profile':json.loads((root/cfg['source_report']).read_text())['profile'],'object':body.name,'scene':scene.name,'retained_fragments':fragments,'bevel_edges':count,'short_edges_collapsed':len(short),'maximum_shape_transfer_projection_m':max(errors)*units,'lining_faces':lining,'entrance_vertices':sorted({v for e in seam for v in e}),'audit':audit}
    (root/(cfg['revision']+'-main-shell.json')).write_text(json.dumps(report,indent=2));return report
