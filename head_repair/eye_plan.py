# SPDX-License-Identifier: GPL-3.0-or-later
import bpy,json,collections
import numpy as np
from mathutils.bvhtree import BVHTree

def plan(character,cfg):
    scene=bpy.context.scene
    body=next(o for o in scene.objects if o.type=='MESH' and 'BodyFace' in o.name);old=body.data
    P=np.array([v.co[:] for v in old.vertices]);K={k.name:np.array([v.co[:] for v in k.data]) for k in old.shape_keys.key_blocks}
    key_ranges={k.name:(k.slider_min,k.slider_max) for k in old.shape_keys.key_blocks}
    groupnames=[g.name for g in body.vertex_groups]
    WG=[{g.group:g.weight for g in v.groups} for v in old.vertices]
    uv=old.uv_layers.active;normals=[tuple(n.vector) for n in old.corner_normals]
    colors={a.name:a for a in old.color_attributes if a.domain=='CORNER'};color_types={n:a.data_type for n,a in colors.items()}
    active_color=old.color_attributes.active_color_index;render_color=old.color_attributes.render_color_index
    old.calc_loop_triangles();triangles=[tuple(t.vertices) for t in old.loop_triangles]
    bvh=BVHTree.FromPolygons(P.tolist(),triangles,all_triangles=True)
    canon={};canonical=[canon.setdefault(tuple(np.round(p,7)),i) for i,p in enumerate(P)]
    removed=set();edge_tags=collections.defaultdict(set);eyes=[]
    for e in character['eyes']:
        center=np.array(e['center_yz']);rx,rz=cfg['cut_radii'];eye_removed=set()
        for face in old.polygons:
            p=P[list(face.vertices)].mean(0)
            if p[0]>cfg['cut_front'] and ((p[1]-center[0])/rx)**2+((p[2]-center[1])/rz)**2<1:
                eye_removed.add(face.index)
                ids=[canonical[i] for i in face.vertices]
                for a,b in zip(ids,ids[1:]+ids[:1]):edge_tags[tuple(sorted((a,b)))].add(e['label'])
        removed|=eye_removed;eyes.append(dict(e,center=center,removed=eye_removed))
    # Grow only pinched mask corners until each retained cut boundary is a simple cycle.
    vertex_faces=collections.defaultdict(set)
    centers=np.array([P[list(f.vertices)].mean(0) for f in old.polygons])
    for face in old.polygons:
        for i in face.vertices:vertex_faces[canonical[i]].add(face.index)
    face_edges=collections.defaultdict(list)
    for face in old.polygons:
        ids=[canonical[i] for i in face.vertices]
        for a,b in zip(ids,ids[1:]+ids[:1]):face_edges[tuple(sorted((a,b)))].append(face.index)
    face_neighbors=collections.defaultdict(set)
    for ids in face_edges.values():
        for i in ids:face_neighbors[i].update(set(ids)-{i})
    def fill_local_islands():
        removed_now=set().union(*(e['removed'] for e in eyes));unseen=set(range(len(old.polygons)))-removed_now;added=0
        while unseen:
            start=next(iter(unseen));todo=[start];component=set()
            while todo:
                fi=todo.pop()
                if fi in component:continue
                component.add(fi);unseen.discard(fi);todo.extend((face_neighbors[fi]-removed_now)-component)
            q=centers[sorted(component)]
            for e in eyes:
                d=(q[:,1:3]-e['center'])/np.array(cfg['cut_radii'])
                if np.all(q[:,0]>cfg['growth_front']) and np.all(np.sum(d*d,axis=1)<cfg['growth_radius']**2):e['removed']|=component;added+=len(component);break
        return added
    growth=[]
    for iteration in range(cfg['growth_steps']):
        island_faces=fill_local_islands() if cfg['fill_local_islands'] else 0
        removed=set().union(*(e['removed'] for e in eyes));ec=collections.Counter();tags=collections.defaultdict(set)
        for face in old.polygons:
            ids=[canonical[i] for i in face.vertices]
            if face.index not in removed:
                for a,b in zip(ids,ids[1:]+ids[:1]):ec[tuple(sorted((a,b)))]+=1
        for e in eyes:
            for fi in e['removed']:
                ids=[canonical[i] for i in old.polygons[fi].vertices]
                for a,b in zip(ids,ids[1:]+ids[:1]):tags[tuple(sorted((a,b)))].add(e['label'])
        additions=0;bad_total=0
        for e in eyes:
            degree=collections.Counter()
            for (a,b),count in ec.items():
                if count==1 and e['label'] in tags[(a,b)]:degree[a]+=1;degree[b]+=1
            bad=[i for i,n in degree.items() if n!=2];bad_edges=[];new=set()
            if not bad and degree:
                adjacency=collections.defaultdict(list)
                for (a,b),count in ec.items():
                    if count==1 and e['label'] in tags[(a,b)]:adjacency[a].append(b);adjacency[b].append(a)
                unseen=set(adjacency)
                while unseen:
                    seed=min(unseen);ring=[];previous=None;current=seed
                    while current not in ring:
                        ring.append(current);unseen.discard(current);opts=[i for i in adjacency[current] if i!=previous];previous,current=current,opts[0]
                    if sum(P[a,1]*P[b,2]-P[b,1]*P[a,2] for a,b in zip(ring,ring[1:]+ring[:1]))<0:ring.reverse()
                    k=int(np.argmin(P[ring,1]));ring=ring[k:]+ring[:k];peak=int(np.argmax(P[ring,1]))
                    for j,(a,b) in enumerate(zip(ring,ring[1:]+ring[:1])):
                        delta=P[b,1]-P[a,1]
                        if (j<peak and delta<=1e-8) or (j>=peak and delta>=-1e-8):bad_edges.append((a,b))
            bad_total+=len(bad)+len(bad_edges)
            candidates=set().union(*(vertex_faces[i] for i in bad)) if bad else set()
            for a,b in bad_edges:candidates|=vertex_faces[a]&vertex_faces[b]
            middle=sum(x['center'][0] for x in eyes)/2
            for fi in candidates:
                q=centers[fi];d=(q[1:3]-e['center'])/np.array(cfg['cut_radii']);own_side=(q[1]>middle)==(e['label']=='left')
                if fi not in removed and q[0]>cfg['growth_front'] and np.dot(d,d)<cfg['growth_radius']**2 and own_side:new.add(fi)
            e['removed']|=new;additions+=len(new)
        growth.append({'iteration':iteration,'badBoundaryVertices':bad_total,'addedFaces':additions,'localIslandFaces':island_faces})
        if not bad_total:break
        if not additions:
            raise RuntimeError('Boundary repair cannot grow within the local eye scope')
    else:raise RuntimeError('Boundary mask did not converge')
    if eyes[0]['removed']&eyes[1]['removed']:raise RuntimeError('Local eye masks overlap')
    removed=set().union(*(e['removed'] for e in eyes));edge_tags=collections.defaultdict(set)
    for e in eyes:
        for fi in e['removed']:
            ids=[canonical[i] for i in old.polygons[fi].vertices]
            for a,b in zip(ids,ids[1:]+ids[:1]):edge_tags[tuple(sorted((a,b)))].add(e['label'])

    counts=collections.Counter()
    for face in old.polygons:
        if face.index in removed:continue
        ids=[canonical[i] for i in face.vertices]
        for a,b in zip(ids,ids[1:]+ids[:1]):counts[tuple(sorted((a,b)))]+=1
    remap={};report={'regions':[]}
    for e in eyes:
        adjacency=collections.defaultdict(list)
        for (a,b),count in counts.items():
            if count==1 and e['label'] in edge_tags[(a,b)]:adjacency[a].append(b);adjacency[b].append(a)
        unseen=set(adjacency);loops=[]
        while unseen:
            seed=min(unseen);connected=set();todo=[seed]
            while todo:
                i=todo.pop()
                if i in connected:continue
                connected.add(i);todo.extend(adjacency[i])
            unseen-=connected
            if any(len(adjacency[i])!=2 for i in connected):raise RuntimeError('Branched outer eye boundary: '+e['label'])
            ring=[];previous=None;current=seed
            while current not in ring:
                ring.append(current);nexts=[i for i in adjacency[current] if i!=previous];previous,current=current,nexts[0]
            loops.append(ring)
        if len(loops)!=1:raise RuntimeError('Expected one outer eye boundary for '+e['label']+', found '+str(len(loops))+'; bounds '+str([(P[x].min(0).tolist(),P[x].max(0).tolist()) for x in loops]))
        ring=loops[0]
        if sum(P[a,1]*P[b,2]-P[b,1]*P[a,2] for a,b in zip(ring,ring[1:]+ring[:1]))<0:ring.reverse()
        e['outer']=ring
        for i in ring:
            for j in np.flatnonzero(np.max(abs(P-P[i]),axis=1)<1e-7):remap[int(j)]=i
        report['regions'].append({'eye':e['label'],'removedFaces':sorted(e['removed']),'outer':ring})

    return {'removed':removed,'remap':remap,'eyes':eyes,'growth':growth}
