# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Private SM iris-cap closure with exact seam identity and glint apertures.



No exports, source edits, glint edits, or source texture repaints. Call close_cap

from the approved Blender connection. Raw front vertices/faces/corner data stay

unchanged. Exact-coordinate UV duplicates are identified only for geometric

topology accounting and closure ownership; they are never proximity welded.

"""

import collections

import hashlib

import json

import math

import os

from pathlib import Path





def _private_root(bpy):

    root=Path(bpy.app.driver_namespace['dsh_internal_research_root']).resolve(strict=True)

    base=(Path(os.environ['LOCALAPPDATA'])/'dsh'/'internal-research').resolve()

    if base not in root.parents or str(root).startswith('\\\\'):

        raise RuntimeError('Private local research root required')

    return root





def canonical_topology(vertices,faces):

    """Exact float32 identity; all degenerate faces remain explicit failures."""

    import numpy as np

    p=np.asarray(vertices,np.float32)

    owner={};representatives=[];groups=collections.defaultdict(list)

    for i,point in enumerate(p):

        # Normalize signed zero, which compares exactly equal geometrically.

        key=tuple(float(x) for x in point)

        rep=owner.setdefault(key,i);representatives.append(rep);groups[rep].append(i)

    valid=[];degenerate=[];uses=collections.defaultdict(list)

    for fi,face in enumerate(faces):

        ids=[representatives[int(v)] for v in face]

        if len(ids)!=3:raise RuntimeError('Native cap closure requires explicit triangles')

        xyz=p[ids].astype(float);area=float(np.linalg.norm(np.cross(xyz[1]-xyz[0],xyz[2]-xyz[0])))

        if len(set(ids))<3 or area<=1e-15:

            degenerate.append({'face':fi,'raw_vertices':list(map(int,face)),'canonical_vertices':ids,'double_area_m2':area})

            continue

        valid.append(fi)

        for a,b in zip(ids,ids[1:]+ids[:1]):uses[tuple(sorted((a,b)))].append((fi,a,b))

    return {'representatives':representatives,'duplicate_groups':[ids for ids in groups.values() if len(ids)>1],

            'unique_vertices':len(owner),'valid_face_ids':valid,'degenerate_faces':degenerate,

            'uses':uses,'boundary_edges':sum(len(v)==1 for v in uses.values()),

            'nonmanifold_edges':sum(len(v)>2 for v in uses.values()),

            'same_direction_pairs':sum(len(v)==2 and v[0][1:]==v[1][1:] for v in uses.values())}





def boundary_loops(topology,vertices):

    import numpy as np

    if topology['nonmanifold_edges'] or topology['same_direction_pairs']:

        raise RuntimeError('Canonical native cap has ambiguous incidence or inconsistent winding')

    outgoing={};edge_face={};incident=collections.defaultdict(set);fan_neighbors=collections.defaultdict(lambda:collections.defaultdict(set))

    for records in topology['uses'].values():

        for fi,a,b in records:

            if (fi,a) in outgoing:raise RuntimeError('Source face has multiple outgoing half-edges at a vertex')

            outgoing[fi,a]=b;incident[a].add(fi);incident[b].add(fi)

        if len(records)==1:

            fi,a,b=records[0];edge_face[a,b]=fi

        else:

            (f,a,b),(g,_,_)=records

            for v in (a,b):fan_neighbors[v][f].add(g);fan_neighbors[v][g].add(f)

    fan_rows=[]

    for v,source_faces in sorted(incident.items()):

        remaining_faces=set(source_faces);fans=[]

        while remaining_faces:

            seed=min(remaining_faces);remaining_faces.remove(seed);fan={seed};todo=[seed]

            while todo:

                current=todo.pop()

                for neighbor in fan_neighbors[v][current]:

                    if neighbor in remaining_faces:remaining_faces.remove(neighbor);fan.add(neighbor);todo.append(neighbor)

            fans.append(sorted(fan))

        fan_rows.append({'vertex':v,'fan_count':len(fans),'face_fans':fans})

    topology['source_vertex_fans']=fan_rows

    pairing={};walks={}

    for incoming,source_face in edge_face.items():

        a,v=incoming;current=source_face;visited=set();walk=[]

        while True:

            if current in visited:raise RuntimeError('Source face fan cycles without reaching an outgoing boundary')

            visited.add(current);walk.append(current)

            c=outgoing.get((current,v))

            if c is None:raise RuntimeError('Source fan has no outgoing face half-edge')

            uses=topology['uses'][tuple(sorted((v,c)))]

            if len(uses)==1:

                if (v,c) not in edge_face:raise RuntimeError('Source boundary direction mismatch')

                pairing[incoming]=(v,c);walks[incoming]=walk;break

            other=next((record for record in uses if record[0]!=current),None)

            if other is None or other[1:]!=(c,v):raise RuntimeError('Source interior fan edge has inconsistent opposite traversal')

            current=other[0]

    if set(pairing.values())!=set(edge_face):raise RuntimeError('Boundary half-edge fan pairing is not one-to-one')

    remaining=set(edge_face);loops=[];p=np.asarray(vertices,float);fan_cycles=[]

    while remaining:

        start=min(remaining);current=start;edges=[]

        while True:

            if current not in remaining:raise RuntimeError('Boundary half-edge was consumed by a different fan cycle')

            edges.append(current);remaining.remove(current);current=pairing[current]

            if current==start:break

        cycle_id=len(fan_cycles);fan_cycles.append({'edges':[list(e) for e in edges],

            'transitions':[{'incoming':list(e),'outgoing':list(pairing[e]),'source_face_walk':walks[e]} for e in edges]})

        # A face-fan walk can be a figure eight at an exact shared vertex. Split

        # its contiguous closed subwalks at repeated vertex occurrences; retain

        # the complete authoritative fan cycle above, including its pairings.

        # This never chooses neighbors by angle or overwrites a vertex successor.

        path_vertices=[edges[0][0]];path_edges=[];where={path_vertices[0]:0};pieces=[]

        for edge in edges:

            if edge[0]!=path_vertices[-1]:raise RuntimeError('Figure-eight subwalk lost continuity')

            path_edges.append(edge);v=edge[1]

            if v in where:

                k=where[v];pieces.append(path_edges[k:]);path_edges=path_edges[:k]

                for removed in path_vertices[k+1:]:where.pop(removed)

                path_vertices=path_vertices[:k+1]

            else:where[v]=len(path_vertices);path_vertices.append(v)

        if path_edges:raise RuntimeError('Boundary figure-eight decomposition left an open subwalk')

        for piece in pieces:

            loop=[a for a,b in piece]

            if len(loop)<3 or len(set(loop))!=len(loop):raise RuntimeError('Canonical boundary subcycle is not simple')

            yz=p[loop,1:];area=float(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(yz,np.roll(yz,-1,axis=0)))/2)

            loops.append({'vertices':loop,'projected_yz_area_m2':area,'parent_face_fan_cycle':cycle_id,

                          'adjacent_source_faces':[edge_face[e] for e in piece],

                          'face_fan_transitions':[{'incoming':list(e),'outgoing':list(pairing[e]),'source_face_walk':walks[e]} for e in piece]})

    topology['boundary_face_fan_cycles']=fan_cycles

    loops.sort(key=lambda r:abs(r['projected_yz_area_m2']),reverse=True)

    return loops





def _copy_packed_front(source,target):

    original=source.attributes.get('custom_normal');copied=target.attributes.get('custom_normal')

    if original is None or copied is None:raise RuntimeError('Packed custom normals unavailable')

    props=[p.identifier for p in original.data[0].bl_rna.properties if p.identifier!='rna_type' and not p.is_readonly]

    if not props:raise RuntimeError('Packed normal values are not writable')

    def native(value):return tuple(value) if hasattr(value,'__len__') else value

    for i,row in enumerate(original.data):

        for prop in props:setattr(copied.data[i],prop,native(getattr(row,prop)))

    equal=all(native(getattr(row,p))==native(getattr(copied.data[i],p)) for i,row in enumerate(original.data) for p in props)

    if not equal:raise RuntimeError('Packed source front-normal copy failed')

    return equal





def edge_connected_shells(vertices,faces):

    topology=canonical_topology(vertices,faces)

    neighbors=collections.defaultdict(set)

    for records in topology['uses'].values():

        if len(records)==2:

            a,b=records[0][0],records[1][0];neighbors[a].add(b);neighbors[b].add(a)

    remaining=set(topology['valid_face_ids']);groups=[]

    while remaining:

        seed=min(remaining);remaining.remove(seed);group={seed};todo=[seed]

        while todo:

            for other in neighbors[todo.pop()]:

                if other in remaining:remaining.remove(other);group.add(other);todo.append(other)

        groups.append(sorted(group))

    return sorted(groups,key=lambda group:(-len(group),group[0]))





def _shell_metrics(vertices,faces):

    import numpy as np

    t=canonical_topology(vertices,faces);p=np.asarray(vertices,np.float32).astype(float)

    normals={};angles=[]

    for fi in t['valid_face_ids']:

        q=p[faces[fi]];n=np.cross(q[1]-q[0],q[2]-q[0]);normals[fi]=n/np.linalg.norm(n)

    for records in t['uses'].values():

        if len(records)==2:

            a,b=[r[0] for r in records];angles.append(math.degrees(math.acos(float(np.clip(normals[a]@normals[b],-1,1)))))

    used={t['representatives'][v] for face in faces for v in face}

    return {'faces':len(faces),'canonical_used_vertices':len(used),'boundary_edges':t['boundary_edges'],

            'nonmanifold_edges':t['nonmanifold_edges'],'same_direction_pairs':t['same_direction_pairs'],

            'degenerate_faces':t['degenerate_faces'],'adjacent_observations':len(angles),

            'maximum_adjacent_degrees':max(angles) if angles else None,'adjacent_over90':sum(a>90 for a in angles)}





def constrained_ears(loop,vertices):

    """Triangulate a simple YZ boundary without adding a centroid or losing edges."""

    import numpy as np

    p=np.asarray(vertices,float);remaining=list(loop);result=[]

    def cross(a,b,c):

        x=p[b,1:]-p[a,1:];y=p[c,1:]-p[a,1:];return float(x[0]*y[1]-x[1]*y[0])

    area=sum(p[a,1]*p[b,2]-p[a,2]*p[b,1] for a,b in zip(loop,loop[1:]+loop[:1]))

    if abs(area)<=1e-20:raise RuntimeError('Hole polygon has no observed projected area')

    sign=1 if area>0 else -1

    while len(remaining)>3:

        candidates=[]

        for i,b in enumerate(remaining):

            a=remaining[i-1];c=remaining[(i+1)%len(remaining)]

            turn=sign*cross(a,b,c)

            if turn<=1e-20:continue

            inside=False

            for v in remaining:

                if v in (a,b,c):continue

                if all(sign*cross(x,y,v)>=-1e-20 for x,y in [(a,b),(b,c),(c,a)]):inside=True;break

            if not inside:candidates.append((turn,i,[a,b,c]))

        if not candidates:raise RuntimeError('No constrained ear found; source hole is ambiguous or self-intersecting')

        _,i,triangle=max(candidates);result.append(triangle);remaining.pop(i)

    if sign*cross(*remaining)<=1e-20:raise RuntimeError('Final constrained ear is degenerate or inverted')

    result.append(remaining)

    expected={tuple(sorted((a,b))) for a,b in zip(loop,loop[1:]+loop[:1])}

    uses=collections.Counter(tuple(sorted((a,b))) for f in result for a,b in zip(f,f[1:]+f[:1]))

    if {edge for edge,n in uses.items() if n==1}!=expected or any(n>2 for n in uses.values()):

        raise RuntimeError('Constrained ears lost source hole boundary ownership')

    return result





def rounded_island_prism(world,original_faces,source_uv_faces,group,depth,width,segments,maximum_source_movement_m=.0005):
    """Own closed ellipsoid carrying the unchanged source island image via native UV projection."""
    import numpy as np
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from mathutils.geometry import barycentric_transform
    used=sorted({v for fi in group for v in original_faces[fi]});front=np.array(world)[used];center=front.mean(axis=0)
    vals,axes=np.linalg.eigh((front-center).T@(front-center));axes=axes[:,::-1]
    if np.linalg.det(axes)<0:axes[:,-1]*=-1
    radii=np.max(np.abs((front-center)@axes),axis=0);radii=np.maximum(radii,[.0001,.00008,.00005])
    n=96;k=64;unit=[[0,0,1]];faces=[]
    for j in range(1,k):
        th=np.pi*j/k
        unit.extend([[np.sin(th)*np.cos(ph),np.sin(th)*np.sin(ph),np.cos(th)] for ph in np.linspace(0,2*np.pi,n,endpoint=False)])
    bottom=len(unit);unit.append([0,0,-1])
    for i in range(n):faces.append([0,1+i,1+(i+1)%n])
    for j in range(k-2):
        a=1+j*n;b=a+n
        for i in range(n):
            z=(i+1)%n;faces.extend([[a+i,b+i,b+z],[a+i,b+z,a+z]])
    a=1+(k-2)*n
    for i in range(n):faces.append([a+i,bottom,a+(i+1)%n])
    points=np.array(unit)*radii@axes.T+center
    source_tri=[original_faces[fi] for fi in group];tree=BVHTree.FromPolygons(world,source_tri,all_triangles=True);uvs=[];materials=[];origins=[]
    for f in faces:
        row=[]
        for vi in f:
            hit,normal,fi,d=tree.find_nearest(Vector(points[vi]));tri=source_tri[fi]
            uv=barycentric_transform(hit,*[Vector(world[i]) for i in tri],*[Vector((*u,0)) for u in source_uv_faces[group[fi]]]);row.append(tuple(uv[:2]))
        uvs.append(row);materials.append(0);origins.append(-1)
    actual=_shell_metrics(points,faces)
    result_tree=BVHTree.FromPolygons(points,faces,all_triangles=True);distances=[result_tree.find_nearest(Vector(p))[3] for p in front]
    if max(distances)>maximum_source_movement_m:raise RuntimeError('Own island closure exceeds configured source silhouette distance')
    return points.tolist(),faces,uvs,materials,origins,{'method':'Own convex ellipsoid fitted to native island, unchanged source image and barycentric native UV mapping','source_front_faces':group,'source_front_vertices':used,'after':actual,'maximum_source_front_vertex_distance_m':max(distances),'source_front_vertex_to_result_distances_m':distances,'front_not_claimed_coordinate_identical':True,'radii_m':radii.tolist(),'center':center.tolist()}

def untangle_hole(vertices,faces,loop,maximum_movement_m=.00002,clearances_m=(.0000005,.000001,.000002,.000003)):

    """Bounded one-vertex projected repair; exact duplicate classes move together.



    Candidates retain every original face/UV and must keep all original front

    normals in the positive-X hemisphere. No global smoothing or proximity weld.

    """

    import numpy as np

    base=np.asarray(vertices,float);triangles=np.asarray(faces,int).reshape(-1,3)

    canonical=canonical_topology(base,faces)

    aliases=collections.defaultdict(list)

    for i,rep in enumerate(canonical['representatives']):aliases[rep].append(i)

    yz=base[loop,1:];signed=sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(yz,np.roll(yz,-1,axis=0)))

    if abs(signed)<=1e-20:raise RuntimeError('Hole projected orientation is unobservable')

    sign=1 if signed>0 else -1

    def source_normals(p):

        q=p[triangles];return np.cross(q[:,1]-q[:,0],q[:,2]-q[:,0])

    original_normals=source_normals(base)

    attempts=[];candidates=[]

    def evaluate(p,moved,description):

        p=p.copy()

        if moved:p[moved]=p[moved].astype(np.float32).astype(float)

        distance=np.linalg.norm(p-base,axis=1);maximum=float(distance.max())

        if maximum>maximum_movement_m:return

        try:ears=constrained_ears(list(reversed(loop)),p)

        except RuntimeError:return

        normals=source_normals(p)

        if np.any(normals[:,0]<=0) or np.any(np.sum(normals*original_normals,axis=1)<=0):return

        metrics=_shell_metrics(p,faces+ears)

        record={'method':description,'moved_source_vertices':moved,'maximum_movement_m':maximum,

                'adjacent_over90':metrics['adjacent_over90'],'maximum_adjacent_degrees':metrics['maximum_adjacent_degrees'],

                'degenerate_faces':len(metrics['degenerate_faces']),'ears':ears}

        attempts.append(record)

        if metrics['degenerate_faces']:return

        # Prefer the smallest successful repair with a modest geometric margin.

        # The actual acceptance threshold remains90, not this search preference.

        angle=metrics['maximum_adjacent_degrees'];bad=metrics['adjacent_over90']

        score=(1,bad,angle,maximum) if bad else ((0,0,maximum,angle) if angle<=85 else (0,1,angle,maximum))

        candidates.append((score,p,record))

    evaluate(base,[],'already_simple')

    if candidates and candidates[0][2]['adjacent_over90']==0:return candidates[0][1],{'changed':False,'selected':candidates[0][2],'candidates':attempts}

    x_offsets=(0.,-.000001,.000001,-.000002,.000002,-.000005,.000005,-.000010,.000010)

    for v in loop:

        ids=aliases[canonical['representatives'][v]]

        for dx in x_offsets[1:]:

            p=base.copy();p[ids,0]+=dx

            evaluate(p,ids,'single_exact_class_depth_adjustment')

    for v in loop:

        for a,b in zip(loop,loop[1:]+loop[:1]):

            if v in (a,b):continue

            edge=base[b,1:]-base[a,1:];length=float(np.linalg.norm(edge))

            if length<=1e-15:continue

            perpendicular=np.array([-edge[1],edge[0]])/length

            signed_distance=float((base[v,1:]-base[a,1:])@perpendicular)

            for clearance in clearances_m:

                delta=(sign*float(clearance)-signed_distance)*perpendicular

                if np.linalg.norm(delta)>maximum_movement_m:continue

                ids=aliases[canonical['representatives'][v]]

                for dx in x_offsets:

                    p=base.copy()

                    for i in ids:p[i,1:]+=delta;p[i,0]+=dx

                    evaluate(p,ids,'single_exact_class_projected_clearance_and_depth')

    if not candidates:raise RuntimeError('No bounded hole untangle preserves observed source-front orientation; candidates='+json.dumps(attempts))

    _,result,selected=min(candidates,key=lambda row:row[0])

    moved=np.flatnonzero(np.linalg.norm(result-base,axis=1)>0)

    return result,{'changed':True,'maximum_movement_limit_m':maximum_movement_m,'selected':selected,

        'candidates':attempts,'vertex_moves':[{'vertex':int(i),'before':base[i].tolist(),'after':result[i].tolist(),

            'distance_m':float(np.linalg.norm(result[i]-base[i]))} for i in moved],

        'source_front_faces_preserved':True,'texture_image_and_UVs_unchanged':True}





def close_cap(source,eye,collection,depth=.008,rings=16,revision='eyes-001',

              inner_depth_m=0.,expected_outer_vertices=24,island_depth_m=.0001,

              tangent_fraction=.2,posterior_radius_fraction=.6,island_bevel_width_m=.000002,island_bevel_segments=3,maximum_island_source_movement_m=.00002,maximum_hole_vertex_movement_m=.00002):

    """Close native edge-connected front shells independently, preserving fronts.



    Exactly coincident UV seams are identified within each declared shell. Shared

    vertices across different shells are duplicated with explicit ancestry and

    never welded together. Source iris and glint objects remain unchanged.

    """

    import bpy

    import numpy as np

    from mathutils import Vector

    root=_private_root(bpy);path=root/('native-cap-closure-'+eye['label']+'-'+revision+'.json')

    if path.exists():raise RuntimeError('Private cap report already exists; choose a new revision')

    original_local=np.asarray([tuple(v.co) for v in source.data.vertices],np.float32).astype(float)

    original_faces=[list(f.vertices) for f in source.data.polygons]

    world=np.asarray([tuple(source.matrix_world@v.co) for v in source.data.vertices])

    if len(original_local)!=89 or len(original_faces)!=143:raise RuntimeError('Expected bound89-vertex143-face native cap')

    original_topology=canonical_topology(original_local,original_faces)

    if original_topology['unique_vertices']!=87 or len(original_topology['valid_face_ids'])!=143 or original_topology['boundary_edges']!=33:

        raise RuntimeError('Corrected native binding requires87unique/143valid/33boundary')

    groups=edge_connected_shells(original_local,original_faces)

    expected_island={'right':[23,32,44],'left':[11,33,45]}[eye['label']]

    if [len(g) for g in groups]!=[140,3] or groups[1]!=expected_island:

        raise RuntimeError('Native edge-connected shell binding changed: '+str(groups))

    source_uv=source.data.uv_layers.active

    if source_uv is None or len(source.data.uv_layers)!=1:raise RuntimeError('Expected one native SM UV map')

    material_indices={f.material_index for f in source.data.polygons}

    if len(material_indices)!=1:raise RuntimeError('Multiple front material bindings require explicit support')

    source_material_index=next(iter(material_indices))

    original_world=world.copy();adjusted_local=original_local.copy();inv=source.matrix_world.inverted()

    main_source_topology=canonical_topology(original_local,[original_faces[i] for i in groups[0]])

    main_source_loops=boundary_loops(main_source_topology,world)

    negative=[row for row in main_source_loops if row['projected_yz_area_m2']<0]

    if len(negative)!=1 or len(negative[0]['vertices'])!=4:raise RuntimeError('Measured mainnegative4 hole binding changed')

    world,hole_repair=untangle_hole(world,original_faces,negative[0]['vertices'],maximum_hole_vertex_movement_m)

    moved_source_vertices=set(int(i) for i in np.flatnonzero(np.linalg.norm(world-original_world,axis=1)>0))

    for i in moved_source_vertices:

        adjusted_local[i]=np.asarray(tuple(inv@Vector(world[i])),np.float32).astype(float)

        world[i]=tuple(source.matrix_world@Vector(adjusted_local[i]))

    stored_moves=[{'source_vertex':i,'before_world':original_world[i].tolist(),'after_world':world[i].tolist(),

        'distance_m':float(np.linalg.norm(world[i]-original_world[i]))} for i in sorted(moved_source_vertices)]

    if any(row['distance_m']>maximum_hole_vertex_movement_m+1e-7 for row in stored_moves):raise RuntimeError('Stored microrepair exceeds its movement bound')

    hole_repair['stored_vertex_moves']=stored_moves

    hole_repair['stored_front_and_fill_metrics']=_shell_metrics(world,original_faces+constrained_ears(list(reversed(negative[0]['vertices'])),world))

    vertices=world.tolist();local_vertices=adjusted_local.tolist();faces=[list(f) for f in original_faces]

    roles=['original_front']*143;face_shell=[None]*143;source_vertex_ancestry=list(range(89))

    face_uv=[[tuple(source_uv.data[i].uv) for i in f.loop_indices] for f in source.data.polygons]

    raw_owner={};shell_maps=[];split_rows=[];loop_rows=[];source_shell_rows=[]

    inv=source.matrix_world.inverted()

    def append_world(p,source_vertex=-1):

        i=len(vertices);vertices.append(np.asarray(p,float).tolist());local_vertices.append(tuple(inv@Vector(p)));source_vertex_ancestry.append(source_vertex);return i

    def add(face,uv,role,shell):faces.append(face);face_uv.append(uv);roles.append(role);face_shell.append(shell)

    for shell_id,group in enumerate(groups):

        used=sorted({v for fi in group for v in original_faces[fi]});mapping={}

        for v in used:

            if v in raw_owner:

                out=append_world(world[v],v);local_vertices[out]=adjusted_local[v].tolist()

                split_rows.append({'source_vertex':v,'output_vertex':out,'shell':shell_id,'previous_shell':raw_owner[v],'coordinate_error':0.})

            else:raw_owner[v]=shell_id;out=v

            mapping[v]=out

        shell_maps.append(mapping)

        for fi in group:faces[fi]=[mapping[v] for v in original_faces[fi]];face_shell[fi]=shell_id

        subset=[original_faces[fi] for fi in group]

        topology=canonical_topology(original_local,subset);loops=boundary_loops(topology,world)

        lengths=[len(row['vertices']) for row in loops]

        expected=[expected_outer_vertices,4] if shell_id==0 else [5]

        if lengths!=expected or loops[0]['projected_yz_area_m2']<=0 or any(row['projected_yz_area_m2']>=0 for row in loops[1:]):

            raise RuntimeError('Declared shell boundary orientation/size changed: '+str((shell_id,lengths)))

        source_shell_rows.append({'shell':shell_id,'source_face_ids':group,'boundary_lengths':lengths,

            'source_vertex_fans':topology['source_vertex_fans'],'face_fan_cycles':topology['boundary_face_fan_cycles']})

        # Choose a raw source owner within THIS shell for each exact-coordinate class.

        representative={}

        for v in used:representative.setdefault(topology['representatives'][v],v)

        normal_sum=collections.defaultdict(lambda:np.zeros(3))

        for fi in group:

            p=world[original_faces[fi]];n=np.cross(p[1]-p[0],p[2]-p[0])

            for v in original_faces[fi]:normal_sum[topology['representatives'][v]]+=n

        for loop_id,row in enumerate(loops):

            src_loop=row['vertices'];loop=[mapping[representative[v]] for v in src_loop]

            center=world[src_loop].mean(axis=0);first_face=len(faces)

            if loop_id==0 and shell_id==0:

                shell_depth=depth

                back=center-np.array([shell_depth,0,0]);controls=[]

                for v in src_loop:

                    p0=world[v];radial=p0-center;radial[0]=0

                    n=normal_sum[v];n=n/np.linalg.norm(n)

                    tangent=radial-n*float(radial@n);length=float(np.linalg.norm(tangent))

                    if length<=1e-12 or float(tangent@radial)<=0:raise RuntimeError('Source-front outward tangent is ambiguous')

                    tangent/=length

                    travel=min(shell_depth*.3,float(np.linalg.norm(radial))*tangent_fraction)

                    p1=p0+travel*tangent

                    p2=back+posterior_radius_fraction*radial

                    controls.append((p0,p1,p2,back))

                previous=loop

                for j in range(1,rings):

                    t=j/rings;current=[]

                    for p0,p1,p2,p3 in controls:

                        p=(1-t)**3*p0+3*(1-t)**2*t*p1+3*(1-t)*t*t*p2+t**3*p3

                        current.append(append_world(p))

                    for i in range(len(loop)):

                        a,b=previous[i],previous[(i+1)%len(loop)];aa,bb=current[i],current[(i+1)%len(loop)]

                        add([b,a,aa],[(0,0)]*3,'tangent_bezier_posterior',shell_id);add([b,aa,bb],[(0,0)]*3,'tangent_bezier_posterior',shell_id)

                    previous=current

                pole=append_world(back)

                for a,b in zip(previous,previous[1:]+previous[:1]):add([b,a,pole],[(0,0)]*3,'tangent_bezier_posterior',shell_id)

            elif loop_id>0:

                shell_depth=inner_depth_m;recessed=[]

                for v,out_v in zip(src_loop,loop):

                    recessed.append(out_v if inner_depth_m==0 else append_world(world[v]-np.array([inner_depth_m,0,0])))

                edge_uv=[]

                for i,(a,b) in enumerate(zip(src_loop,src_loop[1:]+src_loop[:1])):

                    fi=group[row['adjacent_source_faces'][i]];f=source.data.polygons[fi]

                    uvmap={topology['representatives'][int(v)]:tuple(source_uv.data[li].uv) for v,li in zip(f.vertices,f.loop_indices)}

                    edge_uv.append((uvmap[a],uvmap[b]))

                uv_by_vertex={v:edge_uv[i][0] for i,v in enumerate(recessed)}

                for i,(a,b) in enumerate(zip(loop,loop[1:]+loop[:1])):

                    aa,bb=recessed[i],recessed[(i+1)%len(loop)];ua,ub=edge_uv[i]

                    for tri,uvs in [([b,a,aa],[ub,ua,ua]),([b,aa,bb],[ub,ua,ub])]:

                        if len(set(tri))==3:add(tri,uvs,'main_negative_aperture_wall',shell_id)

                for triangle in constrained_ears(list(reversed(recessed)),vertices):

                    add(triangle,[uv_by_vertex[v] for v in triangle],'main_negative_aperture_ear_fill',shell_id)

            else:

                shell_depth=island_depth_m

            loop_rows.append({'shell':shell_id,'source_canonical_loop':src_loop,'output_loop':loop,

                'projected_yz_area_m2':row['projected_yz_area_m2'],'closure_face_range':[first_face,len(faces)],

                'posterior_depth_m':shell_depth,'role':'positive_outer' if loop_id==0 else 'negative_inner',

                'source_adjacent_global_faces':[group[i] for i in row['adjacent_source_faces']]})

    # Replace only the independently declared tiny island by its own rounded

    # front/rear prism. All main-shell front faces remain exactly native.

    original_uvs=[[tuple(source_uv.data[i].uv) for i in f.loop_indices] for f in source.data.polygons]

    ip,iff,iuv,imat,iorigin,island_repair=rounded_island_prism(world,original_faces,original_uvs,groups[1],island_depth_m,island_bevel_width_m,island_bevel_segments,maximum_island_source_movement_m)

    island_map=[append_world(point) for point in ip]

    keep=[i for i,shell in enumerate(face_shell) if shell==0]

    old_face_to_new={old:new for new,old in enumerate(keep)}

    original_face_ids=[i if i<143 else -1 for i in keep]

    faces=[faces[i] for i in keep];face_uv=[face_uv[i] for i in keep];roles=[roles[i] for i in keep];face_shell=[0]*len(keep)

    island_start=len(faces)

    for face,uv,material,origin in zip(iff,iuv,imat,iorigin):

        faces.append([island_map[v] for v in face]);face_uv.append(uv);face_shell.append(1);original_face_ids.append(origin)

        roles.append('island_micro_front' if material==0 else 'island_micro_posterior')

    for row in loop_rows:

        if row['shell']==0:

            row['closure_output_face_ids']=[old_face_to_new[i] for i in range(*row['closure_face_range']) if i in old_face_to_new]

        else:

            row['closure_output_face_ids']=list(range(island_start,len(faces)))

            row['pre_repair_reference_output_loop']=row.pop('output_loop')

            row['output_loop_changed_by_declared_micro_repair']=True

        row.pop('closure_face_range')

    shell_reports=[]

    for shell_id in range(2):

        ids=[i for i,shell in enumerate(face_shell) if shell==shell_id];subset=[faces[i] for i in ids]

        metrics=_shell_metrics(local_vertices,subset)

        if metrics['boundary_edges'] or metrics['nonmanifold_edges'] or metrics['same_direction_pairs'] or metrics['degenerate_faces']:

            raise RuntimeError('Independent shell closure failed: '+json.dumps({'shell':shell_id,'metrics':metrics}))

        shell_reports.append({'shell':shell_id,'output_face_ids':ids,'canonical_identity_scope':'This declared shell only','metrics_local':metrics})

    name='INTERNAL_ONLY__'+eye['label']+'_closed_native_SM_globe__'+revision

    mesh=bpy.data.meshes.new(name);mesh.from_pydata(local_vertices,[],faces);mesh.update()

    obj=bpy.data.objects.new(name,mesh);collection.objects.link(obj);obj.matrix_world=source.matrix_world.copy()

    for mat in source.data.materials:mesh.materials.append(mat)

    back_mat=bpy.data.materials.new(name+'__OWN_POSTERIOR');back_mat.diffuse_color=(.7,.7,.7,1);mesh.materials.append(back_mat)

    for i,f in enumerate(mesh.polygons):

        original_id=original_face_ids[i];protected=face_shell[i]==0 and original_id>=0

        f.use_smooth=source.data.polygons[original_id].use_smooth if protected else True

        f.material_index=source.data.polygons[original_id].material_index if protected else (len(mesh.materials)-1 if roles[i] in ['tangent_bezier_posterior','island_micro_posterior'] else source_material_index)

    for layer in source.data.uv_layers:

        copied=mesh.uv_layers.new(name=layer.name)

        for fi in range(len(faces)):

            for li,uv in zip(mesh.polygons[fi].loop_indices,face_uv[fi]):copied.data[li].uv=uv

    boundary_edges={tuple(sorted((a,b))) for row in loop_rows for a,b in zip(row.get('output_loop',[]),row.get('output_loop',[])[1:]+row.get('output_loop',[])[:1])}

    original_edges={tuple(sorted(e.vertices)):e for e in source.data.edges}

    for edge in mesh.edges:

        pair=tuple(sorted(edge.vertices))

        if pair in boundary_edges:edge.use_edge_sharp=True

        else:

            source_pair=tuple(sorted(source_vertex_ancestry[v] for v in pair))

            if -1 not in source_pair and source_pair in original_edges:edge.use_edge_sharp=original_edges[source_pair].use_edge_sharp

    normals=[tuple(row.vector) for row in mesh.corner_normals];protected_loops=[]

    for fi,source_fi in enumerate(original_face_ids):

        if face_shell[fi]!=0 or source_fi<0:continue

        for dest,src in zip(mesh.polygons[fi].loop_indices,source.data.polygons[source_fi].loop_indices):

            normals[dest]=tuple(source.data.corner_normals[src].vector);protected_loops.append((dest,src))

    mesh.normals_split_custom_set(normals)

    original_normal=source.data.attributes.get('custom_normal');copied_normal=mesh.attributes.get('custom_normal')

    props=[prop.identifier for prop in original_normal.data[0].bl_rna.properties if prop.identifier!='rna_type' and not prop.is_readonly]

    def native(value):return tuple(value) if hasattr(value,'__len__') else value

    for dest,src in protected_loops:

        for prop in props:setattr(copied_normal.data[dest],prop,native(getattr(original_normal.data[src],prop)))

    mesh.update()

    packed_equal=all(native(getattr(copied_normal.data[dest],prop))==native(getattr(original_normal.data[src],prop)) for dest,src in protected_loops for prop in props)

    if not packed_equal:raise RuntimeError('Protected main-shell packed front normals changed')

    decoded_error=max(max(abs(a-b) for a,b in zip(mesh.corner_normals[dest].vector,source.data.corner_normals[src].vector)) for dest,src in protected_loops)

    corner_errors=[];unmoved_errors=[]

    for fi,source_fi in enumerate(original_face_ids):

        if face_shell[fi]!=0 or source_fi<0:continue

        for v,sv in zip(mesh.polygons[fi].vertices,original_faces[source_fi]):

            corner_errors.append(float((obj.matrix_world@mesh.vertices[v].co-Vector(original_world[sv])).length))

            if sv not in moved_source_vertices:unmoved_errors.append((mesh.vertices[v].co-source.data.vertices[sv].co).length)

        for dest,src in zip(mesh.polygons[fi].loop_indices,source.data.polygons[source_fi].loop_indices):

            if tuple(mesh.uv_layers.active.data[dest].uv)!=tuple(source_uv.data[src].uv):raise RuntimeError('Protected main front UV changed')

    corner_error=max(corner_errors)

    if max(unmoved_errors,default=0)!=0:raise RuntimeError('Main front geometry changed outside explicit microrepair vertices')

    if corner_error>maximum_hole_vertex_movement_m+1e-7:raise RuntimeError('Main front microrepair exceeded declared world-space movement')

    for name_attr,domain,values in [('native_cap_source_vertex','POINT',source_vertex_ancestry),

                                   ('native_cap_source_face','FACE',original_face_ids),

                                   ('native_cap_declared_shell','FACE',face_shell)]:

        attr=mesh.attributes.new(name_attr,'INT',domain)

        for row,value in zip(attr.data,values):row.value=value

    attr=mesh.attributes.new('native_cap_source_corner_vertex','INT','CORNER')

    for row in attr.data:row.value=-1

    for fi,source_fi in enumerate(original_face_ids):

        if face_shell[fi]!=0 or source_fi<0:continue

        for li,sv in zip(mesh.polygons[fi].loop_indices,original_faces[source_fi]):attr.data[li].value=sv

    attr=mesh.attributes.new('native_cap_exact_source_face','BOOLEAN','FACE')

    for i,row in enumerate(attr.data):

        source_fi=original_face_ids[i]

        row.value=face_shell[i]==0 and source_fi>=0 and not moved_source_vertices.intersection(original_faces[source_fi])

    obj['internal_only']=True;obj['acceptance']='UNACCEPTED_CAP_SHELL_CLOSURE';obj['source_front_object']=source.name

    actual=np.asarray([tuple(obj.matrix_world@v.co) for v in mesh.vertices])

    for row in shell_reports:row['metrics_world']=_shell_metrics(actual,[faces[i] for i in row['output_face_ids']])

    report={'status':'UNACCEPTED_CAP_SHELL_CLOSURE','source':source.name,'revision':revision,

        'native_main_front_vertices':len({v for fi in groups[0] for v in original_faces[fi]}),'exactly_preserved_main_front_vertices':len({v for fi in groups[0] for v in original_faces[fi]}-moved_source_vertices),'native_main_front_faces_preserved_topologically':140,'main_front_geometry_has_declared_microrepair':bool(moved_source_vertices),'micro_repaired_source_front_faces':groups[1],'front_corner_coordinate_error':corner_error,'unmoved_front_corner_error':max(unmoved_errors,default=0),'hole_untangle':hole_repair,'island_repair':island_repair,

        'source_images_reused_no_repaint':True,'glint_objects_unchanged':True,'packed_front_normals_equal':packed_equal,

        'decoded_front_normal_component_error':float(decoded_error),'source_shells':source_shell_rows,

        'split_cross_shell_vertices':split_rows,'shell_closures':shell_reports,'loops':loop_rows,

        'canonical_identity':'Exact float32 positions within each declared edge-connected shell; never across separate shells',

        'source_vertex_ancestry':source_vertex_ancestry,'face_shell_ids':face_shell,'face_roles':roles,

        'closure_parameters':{'main_depth_m':depth,'island_depth_m':island_depth_m,'inner_depth_m':inner_depth_m,

            'rings':rings,'tangent_fraction':tangent_fraction,'posterior_radius_fraction':posterior_radius_fraction,'island_bevel_width_m':island_bevel_width_m,'island_bevel_segments':island_bevel_segments,'maximum_island_source_movement_m':maximum_island_source_movement_m,'maximum_hole_vertex_movement_m':maximum_hole_vertex_movement_m},

        'topology':{'boundary_edges':sum(row['metrics_world']['boundary_edges'] for row in shell_reports),

            'nonmanifold_edges':sum(row['metrics_world']['nonmanifold_edges'] for row in shell_reports),

            'same_direction_pairs':sum(row['metrics_world']['same_direction_pairs'] for row in shell_reports),

            'maximum_adjacent_degrees':max(row['metrics_world']['maximum_adjacent_degrees'] for row in shell_reports),

            'adjacent_over90':sum(row['metrics_world']['adjacent_over90'] for row in shell_reports)}}

    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

    return obj,actual,faces,report



