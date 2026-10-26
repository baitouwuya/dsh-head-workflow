# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""SM-source topology surgery. All new caps are internal. No donor outer skin."""
import bpy,bmesh,pathlib,json,collections,math
import numpy as np
from mathutils import Vector

def build():
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root'])
    cfg=json.loads((root/'assembly-profile.json').read_text());opts=cfg['skin_repair']
    src=bpy.data.objects['INTERNAL_ONLY__SM_000_protected_facial_skin'];m=src.data
    ids=[x.value for x in m.attributes['native_SM_vertex_id'].data];canonical={};verts=[];mapping={}
    for i,k in enumerate(ids):
        if k not in canonical:canonical[k]=len(verts);verts.append(list(src.matrix_world@m.vertices[i].co))
        mapping[i]=canonical[k]
    faces=[tuple(mapping[i] for i in f.vertices) for f in m.polygons]
    origin=list(range(len(faces)));uvs=[[list(m.uv_layers.active.data[i].uv) for i in f.loop_indices] for f in m.polygons]
    def incidence():
        es=collections.defaultdict(list)
        for i,f in enumerate(faces):
            for a,b in zip(f,f[1:]+f[:1]):es[tuple(sorted((a,b)))].append(i)
        return es
    removed=[]
    while True:
        edges=incidence();bad={i for u in edges.values() if len(u)>2 for i in u}
        if not bad:break
        area=lambda i:np.linalg.norm(np.cross(np.array(verts[faces[i][1]])-verts[faces[i][0]],np.array(verts[faces[i][2]])-verts[faces[i][0]]))
        i=min(bad,key=area);removed.append(origin[i]);faces.pop(i);origin.pop(i);uvs.pop(i)
    edges=incidence();vertex_faces=collections.defaultdict(list)
    for fi,f in enumerate(faces):
        for vi in f:vertex_faces[vi].append(fi)
    split=[]
    for vi,fis in vertex_faces.items():
        nei={fi:set() for fi in fis}
        for fi in fis:
            for vj in faces[fi]:
                if vj==vi:continue
                u=edges[tuple(sorted((vi,vj)))]
                if len(u)==2:nei[u[0]].add(u[1]);nei[u[1]].add(u[0])
        remain=set(fis);groups=[]
        while remain:
            seed=remain.pop();group={seed};stack=[seed]
            while stack:
                for j in nei[stack.pop()]:
                    if j in remain:remain.remove(j);group.add(j);stack.append(j)
            groups.append(group)
        for group in groups[1:]:
            nv=len(verts);verts.append(verts[vi][:]);split.append([vi,nv])
            for fi in group:faces[fi]=tuple(nv if x==vi else x for x in faces[fi])
    edges=incidence();boundary=[e for e,u in edges.items() if len(u)==1]
    b_adj=collections.defaultdict(list)
    for a,b in boundary:b_adj[a].append(b);b_adj[b].append(a)
    if any(len(n)!=2 for n in b_adj.values()):raise RuntimeError('Boundary not a union of simple loops after fan split')
    remaining=set(boundary);loops=[]
    while remaining:
        a,b=next(iter(remaining));loop=[a];prev=a;cur=b;remaining.remove(tuple(sorted((a,b))))
        while cur!=a:
            loop.append(cur);nxt=next(x for x in b_adj[cur] if x!=prev)
            remaining.remove(tuple(sorted((cur,nxt))));prev,cur=cur,nxt
        loops.append(loop)
    mesh=bpy.data.meshes.new('INTERNAL_ONLY_SM_surgery_'+cfg['revision']);mesh.from_pydata(verts,[],faces)
    layer=mesh.uv_layers.new(name='UVMap')
    for fi,f in enumerate(mesh.polygons):
        for li,uv in zip(f.loop_indices,uvs[fi]):layer.data[li].uv=uv
    for mat in m.materials:mesh.materials.append(mat)
    bm=bmesh.new();bm.from_mesh(mesh);bm.verts.ensure_lookup_table()
    base_bverts=list(bm.verts)
    center=np.mean(verts,axis=0);cap_loops=[]
    for loop in loops:
        points=np.array([verts[i] for i in loop]);ctr=points.mean(axis=0)
        direction=center-ctr;direction/=max(np.linalg.norm(direction),1e-12)
        ring=[bm.verts.new(Vector((1-opts['cap_inset_ratio'])*p+opts['cap_inset_ratio']*ctr+opts['cap_depth_m']*direction)) for p in points]
        for i in range(len(loop)):
            j=(i+1)%len(loop);bm.faces.new([base_bverts[loop[i]],base_bverts[loop[j]],ring[j],ring[i]])
        cap=bm.faces.new(ring)
        cap_loops.append(len(loop))
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(mesh);bm.free();mesh.update()
    ob=bpy.data.objects.new('INTERNAL_ONLY__SM_repaired_'+cfg['revision'],mesh)
    bpy.data.scenes['INTERNAL_ONLY__SM_Assembly'].collection.objects.link(ob)
    ob['classification']='INTERNAL_ONLY';ob['status']='UNACCEPTED';ob['source_object']=src.name
    v=np.array([list(x.co) for x in mesh.vertices]);f=[list(x.vertices) for x in mesh.polygons];t=np.array(f)
    a=bpy.app.driver_namespace['dsh_private_topology_core']['analyze'](v,f,t,list(range(len(f))))
    report={'classification':'INTERNAL_ONLY','profile':cfg,'object':ob.name,'source_faces_removed':removed,'split_vertex_fans':split,'cap_loops':cap_loops,'audit':a}
    (root/(cfg['revision']+'-skin-repair.json')).write_text(json.dumps(report,indent=2))
    return report
