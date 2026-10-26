# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,numpy as np,json,pathlib,collections
from mathutils import Vector
def build(cfg):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root'])
    src=bpy.data.objects[cfg['source']];m=src.data
    local=[tuple(v.co) for v in m.vertices];world=np.array([list(src.matrix_world@v.co) for v in m.vertices])
    native=[a.value for a in m.attributes['native_SM_vertex_id'].data];first={}
    for i,k in enumerate(native):first.setdefault(k,i)
    fs=[list(p.vertices) for p in m.polygons];edgeuses=collections.defaultdict(list)
    for fi,f in enumerate(fs):
        for a,b in zip(f,f[1:]+f[:1]):edgeuses[tuple(sorted((native[a],native[b])))].append((fi,native[a],native[b]))
    boundary={e:u[0] for e,u in edgeuses.items() if len(u)==1}
    groups=json.loads((root/'SM-native-topology-defects.json').read_text())['boundary_groups']
    data=[];face_before=len(fs);inverse=src.matrix_world.inverted()
    for group in groups:
        if group['edges'] not in cfg['loop_edge_counts']:continue
        selected=set(group['native_vertex_ids']);es={e:u for e,u in boundary.items() if e[0] in selected and e[1] in selected}
        nxt={u[1]:u[2] for u in es.values()};start=next(iter(nxt));loop=[start];k=nxt[start]
        while k!=start:loop.append(k);k=nxt[k]
        if len(loop)!=len(selected):raise RuntimeError('Non-simple boundary')
        points=np.array([world[first[k]] for k in loop]);ctr=points.mean(axis=0);out=[]
        for i,k in enumerate(loop):
            prev=loop[(i-1)%len(loop)];post=loop[(i+1)%len(loop)]
            fi0=boundary[tuple(sorted((prev,k)))][0];fi1=boundary[tuple(sorted((k,post)))][0]
            c=(world[fs[fi0]].mean(axis=0)+world[fs[fi1]].mean(axis=0))/2
            d=points[i]-c;out.append(d/max(np.linalg.norm(d),1e-12))
        out=np.array(out);rings=[[first[k] for k in loop]]
        for inset,extrapolation in cfg['rings']:
            positions=(1-inset)*points+inset*ctr+extrapolation*out
            ids=[]
            for v in positions:ids.append(len(local));local.append(tuple(inverse@Vector(v)));native.append(-len(native)-1)
            prev=rings[-1];rings.append(ids)
            for i in range(len(loop)):
                j=(i+1)%len(loop)
                fs.extend([[prev[j],prev[i],ids[i]],[prev[j],ids[i],ids[j]]])
        # Private cap interior uses a fresh central point; intersection/visibility remain audited.
        cid=len(local);local.append(tuple(inverse@Vector(ctr)));native.append(-len(native)-1)
        for i in range(len(loop)):fs.append([rings[-1][(i+1)%len(loop)],rings[-1][i],cid])
        data.append({'boundary_edges':len(loop),'native_ids':loop,'new_vertices':sum(len(x) for x in rings[1:])+1})
    mesh=bpy.data.meshes.new('INTERNAL_ONLY_SM_closed_portals_'+cfg['revision']);mesh.from_pydata(local,[],fs);mesh.update()
    for mat in m.materials:mesh.materials.append(mat)
    uv=mesh.uv_layers.new(name='UVMap')
    for i,l in enumerate(m.uv_layers.active.data):uv.data[i].uv=l.uv
    for i,f in enumerate(mesh.polygons):f.use_smooth=m.polygons[i].use_smooth if i<len(m.polygons) else True
    nid=mesh.attributes.new('native_SM_vertex_id','INT','POINT')
    for a,k in zip(nid.data,native):a.value=k
    norms=[tuple(n.vector) for n in mesh.corner_normals]
    for i,n in enumerate(m.corner_normals):norms[i]=tuple(n.vector)
    mesh.normals_split_custom_set(norms)
    if 'custom_normal' in m.attributes and 'custom_normal' in mesh.attributes:
        for i,v in enumerate(m.attributes['custom_normal'].data):mesh.attributes['custom_normal'].data[i].value=v.value
    ob=bpy.data.objects.new('INTERNAL_ONLY_SM_portals_'+cfg['revision'],mesh);ob.matrix_world=src.matrix_world.copy()
    scene=bpy.data.scenes.new('INTERNAL_ONLY_visibility_'+cfg['revision'])
    for o in bpy.data.scenes['INTERNAL_ONLY__ResearchCheckpoint_REJECTED'].objects:
        if o!=src:scene.collection.objects.link(o)
    scene.collection.objects.link(ob)
    v=np.array([list(ob.matrix_world@x.co) for x in mesh.vertices]);f=[list(x.vertices) for x in mesh.polygons]
    a=bpy.app.driver_namespace['dsh_private_topology_core']['analyze'](v,f,f,list(range(len(f))),native)
    report={'classification':'INTERNAL_ONLY','status':'UNACCEPTED','profile':cfg,'object':ob.name,'scene':scene.name,'closures':data,'original_faces_preserved':face_before,'audit':a}
    (root/(cfg['revision']+'-portal-closure.json')).write_text(json.dumps(report,indent=2))
    return report
