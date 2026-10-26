# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Remove obsolete eye planes on the copy; retain every protected hair face."""
import bpy,json,collections,numpy as np

def remove_eye_planes(source,component_ids,protected_faces):
    obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and 'BlueHairStar' in o.name);old=obj.data;labels=source['indices'];wanted=set(component_ids);adj=collections.defaultdict(set)
    for edge in old.edges:
        a,b=edge.vertices;adj[a].add(b);adj[b].add(a)
    unseen=set(adj);remove=set();components=[]
    while unseen:
        todo=[next(iter(unseen))];ids=set()
        while todo:
            i=todo.pop()
            if i in ids:continue
            ids.add(i);unseen.discard(i);todo.extend(adj[i]-ids)
        observed={labels[i] for i in ids if i<len(labels)};delete=bool(observed) and observed<=wanted
        if delete:remove|=ids
        if delete:components.append({'source_components':sorted(observed),'vertices':len(ids)})
    kept=[f for f in old.polygons if not all(i in remove for i in f.vertices)];removed=[f for f in old.polygons if all(i in remove for i in f.vertices)];protected={tuple(sorted(f)) for f in protected_faces}
    if any(tuple(sorted(f.vertices)) in protected for f in removed):raise RuntimeError('Legacy eye classification intersects protected hair')
    if not removed:return {'removed_faces':0,'components':components}
    import bmesh
    vertex_before=np.array([v.co[:] for v in old.vertices],np.float32)
    keys_before={k.name:np.array([v.co[:] for v in k.data],np.float32) for k in old.shape_keys.key_blocks}
    deleted_count=len(removed);removed_ids={f.index for f in removed}
    bm=bmesh.new();bm.from_mesh(old);bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index in removed_ids],context='FACES_ONLY')
    bm.to_mesh(old);bm.free();old.update()
    if not np.array_equal(vertex_before,np.array([v.co[:] for v in old.vertices],np.float32)):raise RuntimeError('Face-only filtering changed vertex positions')
    for k in old.shape_keys.key_blocks:
        if not np.array_equal(keys_before[k.name],np.array([v.co[:] for v in k.data],np.float32)):raise RuntimeError('Face-only filtering changed shape field '+k.name)
    after={tuple(sorted(f.vertices)) for f in old.polygons}
    if protected-after:raise RuntimeError('Face-only filtering removed a protected face')
    return {'removed_faces':deleted_count,'components':components,'protected_faces_removed':0,'vertex_positions_and_shape_fields_preserved':True}
