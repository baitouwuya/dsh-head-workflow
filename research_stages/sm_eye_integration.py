# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Private direct SM eye assembly, diagnostic and unaccepted.

Exact bound native iris fronts are closed posteriorly. Thin closed lid volumes
use measured full-aperture contours; no broad skin/collar reconstruction occurs.
This does not import, copy or export VRoid data. Source objects remain untouched.
Call integrate(profile_dict) from the approved Blender connection.
"""
from pathlib import Path
import collections
import hashlib
import json
import math
import os
import re

CAP_NAMES = {'right': 'INTERNAL_ONLY__SM_008_protected_appearance',
             'left': 'INTERNAL_ONLY__SM_044_protected_appearance'}
COLLECTION = 'INTERNAL_ONLY__SM_CLOSED_EYES_AND_LIDS'
_UV_CACHE = {}


def _private_root(bpy):
    root = Path(bpy.app.driver_namespace['dsh_internal_research_root']).resolve(strict=True)
    base = (Path(os.environ['LOCALAPPDATA']) / 'dsh' / 'internal-research').resolve()
    if base not in root.parents or str(root).startswith('\\\\'):
        raise RuntimeError('Private local output root required')
    return root


def _uses(faces):
    result = collections.defaultdict(list)
    for fi, face in enumerate(faces):
        for a, b in zip(face, face[1:] + face[:1]):
            result[tuple(sorted((a, b)))].append((fi, a, b))
    return result


def _topology(vertices, faces):
    import numpy as np
    p = np.asarray(vertices, float)
    uses = _uses(faces)
    triangles = [f for f in faces if len(f) == 3]
    if len(triangles) != len(faces):
        raise RuntimeError('This stage requires explicit triangles')
    t = np.asarray(triangles, int)
    n = np.cross(p[t[:, 1]] - p[t[:, 0]], p[t[:, 2]] - p[t[:, 0]])
    lengths = np.linalg.norm(n, axis=1)
    degenerate = int((lengths <= 1e-15).sum())
    normals = n / np.maximum(lengths[:, None], 1e-30)
    angles = []
    for records in uses.values():
        if len(records) == 2:
            a, b = records[0][0], records[1][0]
            angles.append(math.degrees(math.acos(float(np.clip(normals[a] @ normals[b], -1, 1)))))
    return {'triangles': len(faces), 'boundary_edges': sum(len(v) == 1 for v in uses.values()),
            'nonmanifold_edges': sum(len(v) > 2 for v in uses.values()),
            'same_direction_pairs': sum(len(v) == 2 and v[0][1:] == v[1][1:] for v in uses.values()),
            'degenerate_triangles': degenerate, 'adjacent_observations': len(angles),
            'adjacent_max_degrees': max(angles) if angles else None,
            'adjacent_over90': sum(a > 90 for a in angles)}


def _boundary(faces):
    uses = _uses(faces)
    if any(len(v) > 2 or (len(v) == 2 and v[0][1:] == v[1][1:]) for v in uses.values()):
        raise RuntimeError('Native iris cap has ambiguous/nonmanifold winding')
    boundary = [(v[0][1], v[0][2]) for v in uses.values() if len(v) == 1]
    next_vertex = {}
    for a, b in boundary:
        if a in next_vertex:
            raise RuntimeError('Native iris cap boundary branches')
        next_vertex[a] = b
    if len(boundary) < 3 or len({b for _, b in boundary}) != len(boundary):
        raise RuntimeError('Native iris cap has no simple oriented boundary')
    start = boundary[0][0]
    loop = [start]
    while True:
        nxt = next_vertex.get(loop[-1])
        if nxt is None:
            raise RuntimeError('Native iris cap boundary is open')
        if nxt == start:
            break
        if nxt in loop:
            raise RuntimeError('Native iris cap boundary revisits a vertex')
        loop.append(nxt)
    if len(loop) != len(boundary):
        raise RuntimeError('Native iris cap has multiple boundary loops; explicit binding required')
    return loop


def _bounds(rim, y):
    import numpy as np
    hits = []
    for a, b in zip(rim, np.roll(rim, -1, axis=0)):
        if abs(float(b[1] - a[1])) < 1e-14:
            continue
        t = (y - a[1]) / (b[1] - a[1])
        if -1e-10 <= t <= 1 + 1e-10:
            p = a + np.clip(t, 0, 1) * (b - a)
            if not any(np.linalg.norm(p - q) < 1e-8 for q in hits):
                hits.append(p)
    if len(hits) not in (1, 2):
        raise RuntimeError('Measured eye opening is not single-valued at Y=' + str(y))
    hits.sort(key=lambda p: p[2])
    return hits[0], hits[-1]


def _bvh(vertices, faces):
    from mathutils.bvhtree import BVHTree
    return BVHTree.FromPolygons([tuple(v) for v in vertices], faces, all_triangles=True)


def _cast(tree, y, z, start):
    from mathutils import Vector
    hit, normal, face, distance = tree.ray_cast(Vector((start, y, z)), Vector((-1, 0, 0)))
    return (float(hit.x), int(face)) if hit is not None else None


def loop_subdivide_fields(fields, faces, levels):
    """One closed-triangle Loop stencil applied identically to every named field.

    Fields include all poses and UV coordinates. No normals are smoothed as a
    substitute for geometry; final float32 triangles are measured afterwards.
    """
    import numpy as np
    if type(levels) is not int or not 0 <= levels <= 3:
        raise RuntimeError('Loop levels must be an integer from 0 to 3')
    values = {name:np.asarray(value,float) for name,value in fields.items()}
    count = len(next(iter(values.values())))
    if any(len(value)!=count or value.ndim!=2 for value in values.values()):
        raise RuntimeError('Subdivision fields have incompatible vertex counts')
    faces = [list(map(int,f)) for f in faces]
    reports=[]
    for level in range(levels):
        uses=_uses(faces)
        if any(len(rows)!=2 or rows[0][1:]==rows[1][1:] for rows in uses.values()):
            raise RuntimeError('Closed, consistently wound triangle mesh required for Loop subdivision')
        adjacency=[set() for _ in range(count)]
        edge_list=sorted(uses)
        edge_ids={edge:count+i for i,edge in enumerate(edge_list)}
        endpoints=[];opposites=[]
        for a,b in edge_list:
            adjacency[a].add(b);adjacency[b].add(a)
            records=uses[a,b]
            other=[next(v for v in faces[record[0]] if v not in (a,b)) for record in records]
            endpoints.append([a,b]);opposites.append(other)
        valence=np.asarray([len(n) for n in adjacency],int)
        if valence.min()<3:raise RuntimeError('Loop subdivision has invalid closed-surface valence')
        beta=np.where(valence==3,3/16,3/(8*valence))
        neighbor_rows=np.asarray([i for i,neighbors in enumerate(adjacency) for n in neighbors],int)
        neighbor_ids=np.asarray([n for neighbors in adjacency for n in sorted(neighbors)],int)
        # Rows and IDs must follow the same ordering; the set iteration above
        # only repeats each row number, so sorting neighbors preserves pairing.
        endpoints=np.asarray(endpoints,int);opposites=np.asarray(opposites,int)
        updated={}
        for name,value in values.items():
            neighbor_sum=np.zeros_like(value)
            np.add.at(neighbor_sum,neighbor_rows,value[neighbor_ids])
            old=(1-valence*beta)[:,None]*value+beta[:,None]*neighbor_sum
            added=.375*value[endpoints].sum(axis=1)+.125*value[opposites].sum(axis=1)
            updated[name]=np.concatenate([old,added])
        children=[]
        for a,b,c in faces:
            ab=edge_ids[tuple(sorted((a,b)))];bc=edge_ids[tuple(sorted((b,c)))];ca=edge_ids[tuple(sorted((c,a)))]
            children.extend([[a,ab,ca],[b,bc,ab],[c,ca,bc],[ab,bc,ca]])
        reports.append({'level':level+1,'input_vertices':count,'output_vertices':len(next(iter(updated.values()))),
                        'input_triangles':len(faces),'output_triangles':len(children),
                        'same_stencil_fields':sorted(values)})
        values=updated;faces=children;count=len(next(iter(values.values())))
    return {name:value.astype(np.float32).astype(float) for name,value in values.items()},faces,reports


def _closed_cap(source, eye, collection, depth, rings, revision):
    import bpy
    import numpy as np
    from mathutils import Vector
    original_local = [tuple(v.co) for v in source.data.vertices]
    world = np.asarray([tuple(source.matrix_world @ v.co) for v in source.data.vertices])
    faces = [list(f.vertices) for f in source.data.polygons]
    if len(world) != 89 or len(faces) != 143:
        raise RuntimeError('Bound native iris cap is not the measured 89-vertex/143-triangle component')
    loop = _boundary(faces)
    center = world[loop].mean(axis=0)
    output = world.tolist()
    previous = loop
    for j in range(1, rings):
        theta = math.pi * j / (2 * rings)
        current = []
        for v in loop:
            p = center + math.cos(theta) * (world[v] - center)
            p[0] -= depth * math.sin(theta)
            current.append(len(output)); output.append(p.tolist())
        for i in range(len(loop)):
            a, b = previous[i], previous[(i + 1) % len(loop)]
            aa, bb = current[i], current[(i + 1) % len(loop)]
            faces.extend([[b, a, aa], [b, aa, bb]])
        previous = current
    pole = len(output); output.append((center - [depth, 0, 0]).tolist())
    for a, b in zip(previous, previous[1:] + previous[:1]):
        faces.append([b, a, pole])
    inv = source.matrix_world.inverted()
    local = original_local + [tuple(inv @ Vector(p)) for p in output[len(original_local):]]
    name = 'INTERNAL_ONLY__' + eye['label'] + '_closed_native_SM_globe__' + revision
    mesh = bpy.data.meshes.new(name); mesh.from_pydata(local, [], faces); mesh.update()
    obj = bpy.data.objects.new(name, mesh); collection.objects.link(obj); obj.matrix_world = source.matrix_world.copy()
    for mat in source.data.materials:
        mesh.materials.append(mat)
    inner = bpy.data.materials.new(name + '__own_posterior')
    inner.diffuse_color = (.7, .7, .7, 1); mesh.materials.append(inner)
    for i, f in enumerate(mesh.polygons):
        f.use_smooth = source.data.polygons[i].use_smooth if i < 143 else True
        f.material_index = source.data.polygons[i].material_index if i < 143 else len(mesh.materials) - 1
    for layer in source.data.uv_layers:
        copied = mesh.uv_layers.new(name=layer.name)
        for i, row in enumerate(layer.data):
            copied.data[i].uv = row.uv
    # Preserve the true front corner normals; generated posterior normals are local.
    target_normals = [tuple(n.vector) for n in mesh.corner_normals]
    for i, n in enumerate(source.data.corner_normals):
        target_normals[i] = tuple(n.vector)
    mesh.normals_split_custom_set(target_normals)
    # The old cap boundary was already a normal-space boundary. Keep that split
    # when adding posterior faces, then copy the original packed corner data.
    boundary_edges = {tuple(sorted((a,b))) for a,b in zip(loop,loop[1:]+loop[:1])}
    source_edges = {tuple(sorted(e.vertices)):e for e in source.data.edges}
    for edge in mesh.edges:
        key = tuple(sorted(edge.vertices))
        if key in boundary_edges: edge.use_edge_sharp = True
        elif key in source_edges: edge.use_edge_sharp = source_edges[key].use_edge_sharp
    original_attribute = source.data.attributes.get('custom_normal')
    copied_attribute = mesh.attributes.get('custom_normal')
    if original_attribute is None or copied_attribute is None:
        raise RuntimeError('Observed packed custom_normal attributes are unavailable')
    properties = [p.identifier for p in original_attribute.data[0].bl_rna.properties
                  if p.identifier!='rna_type' and not p.is_readonly]
    if not properties: raise RuntimeError('Packed normal RNA has no writable value')
    for i,row in enumerate(original_attribute.data):
        for prop in properties:
            value=getattr(row,prop)
            setattr(copied_attribute.data[i],prop,tuple(value) if hasattr(value,'__len__') else value)
    mesh.update()
    raw_equal = all(all(tuple(getattr(row,p))==tuple(getattr(copied_attribute.data[i],p))
                       if hasattr(getattr(row,p),'__len__') else getattr(row,p)==getattr(copied_attribute.data[i],p)
                       for p in properties) for i,row in enumerate(original_attribute.data))
    if not raw_equal: raise RuntimeError('Packed native cap front normals changed')
    decoded_error = max(max(abs(a-b) for a,b in zip(mesh.corner_normals[i].vector,row.vector))
                        for i,row in enumerate(source.data.corner_normals))
    attr = mesh.attributes.new('native_SM_cap_vertex_id', 'INT', 'POINT')
    for i, row in enumerate(attr.data):
        row.value = i if i < 89 else -1
    attr = mesh.attributes.new('native_SM_cap_face_id', 'INT', 'FACE')
    for i, row in enumerate(attr.data):
        row.value = i if i < 143 else -1
    obj['internal_only'] = True; obj['acceptance'] = 'UNACCEPTED_INTERNAL_EYE_STAGE'
    obj['source_front_object'] = source.name; obj['front_geometry_and_uv_preserved'] = True
    obj['supersedes_source_cap_only_after_operator_composition'] = source.name
    actual = np.asarray([tuple(obj.matrix_world @ v.co) for v in mesh.vertices])
    topo = _topology(actual, faces)
    if topo['boundary_edges'] or topo['nonmanifold_edges'] or topo['same_direction_pairs'] or topo['degenerate_triangles']:
        raise RuntimeError('Posterior native-cap closure failed structural checks: ' + json.dumps(topo))
    if any(tuple(mesh.vertices[i].co) != original_local[i] for i in range(89)):
        raise RuntimeError('Original SM iris front coordinates changed')
    return obj, actual, faces, {'source': source.name, 'preserved_front_vertices': 89,
        'preserved_front_faces': 143, 'source_boundary_vertices': len(loop), 'posterior_depth_m': depth,
        'topology': topo, 'source_images_reused_no_repaint': True,'packed_front_normals_equal':raw_equal,
        'decoded_front_normal_component_error':float(decoded_error)}


def _skin_uv(source, point, maximum_distance):
    """Measured nearest native skin support, with an explicit distance limit."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from mathutils.geometry import barycentric_transform
    cache_key = (source.as_pointer(), source.data.as_pointer(), tuple(v for row in source.matrix_world for v in row))
    if cache_key not in _UV_CACHE:
        source.data.calc_loop_triangles()
        triangles = list(source.data.loop_triangles)
        vertices = [tuple(source.matrix_world @ v.co) for v in source.data.vertices]
        tree = BVHTree.FromPolygons(vertices, [tuple(t.vertices) for t in triangles], all_triangles=True)
        _UV_CACHE[cache_key] = (triangles, vertices, tree)
    triangles, vertices, tree = _UV_CACHE[cache_key]
    hit, normal, triangle, distance = tree.find_nearest(Vector(point))
    if hit is None or distance > maximum_distance:
        raise RuntimeError('No nearby native skin UV support; distance=' + str(distance))
    if not source.data.uv_layers.active:
        raise RuntimeError('Native SM skin UV map is missing')
    tri = triangles[triangle]
    uv = [source.data.uv_layers.active.data[i].uv for i in tri.loops]
    weights = barycentric_transform(hit, *[Vector(vertices[i]) for i in tri.vertices],
        Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
    result = sum((uv[i] * weights[i] for i in range(3)), uv[0] * 0)
    return tuple(result), {'source_triangle': int(triangle), 'distance_m': float(distance), 'source_uv': list(result)}


def _lids(eye, cap_vertices, cap_faces, skin, collection, columns, rows, thickness,
          clearance, neutral_fraction, maximum_raise, uv_support_distance, revision, loop_levels):
    import bpy
    import numpy as np
    from mathutils import Vector
    rim = np.asarray(eye['rim_xyz'], float)
    ys = np.linspace(rim[:, 1].min(), rim[:, 1].max(), columns + 1)
    bounds = [_bounds(rim, float(y)) for y in ys]
    tree = _bvh(cap_vertices, cap_faces); start = float(np.asarray(cap_vertices)[:, 0].max() + .1)
    outputs = []; reports = []
    for upper in (True, False):
        side = 'upper' if upper else 'lower'
        descriptors = []; index = {}; front_faces = []
        for ci in range(columns + 1):
            for ri in range(rows + 1):
                key = (ci, 0 if ci in (0, columns) else ri)
                if key not in index:
                    index[key] = len(descriptors); descriptors.append((ci, ri / rows))
                index[ci, ri] = index[key]
        for ci in range(columns):
            for ri in range(rows):
                a, b, c, d = [index[k] for k in [(ci, ri), (ci + 1, ri), (ci + 1, ri + 1), (ci, ri + 1)]]
                if len({a, b, c}) == 3: front_faces.append([a, b, c])
                if len({a, c, d}) == 3: front_faces.append([a, c, d])
        depth_corrections = []
        def positions(blink):
            front = []
            for ci, t in descriptors:
                lo, hi = bounds[ci]; outer = hi if upper else lo
                gap = float(hi[2] - lo[2]); mid = .5 * (lo[2] + hi[2])
                inset = neutral_fraction * gap
                overlap = min(clearance * .5, gap * .02) * blink
                inner = (outer[2] - inset if upper else outer[2] + inset) * (1 - blink)
                inner += (mid - overlap if upper else mid + overlap) * blink
                z = float(outer[2] * (1 - t) + inner * t)
                fraction = (z - lo[2]) / gap if gap > 1e-12 else .5
                x = float(lo[0] * (1 - fraction) + hi[0] * fraction)
                hit = _cast(tree, float(ys[ci]), z, start)
                if hit:
                    needed = max(0., hit[0] + clearance - x)
                    depth_corrections.append(needed)
                    if needed > maximum_raise:
                        raise RuntimeError('Lid support would require a raised collar: '+json.dumps({'eye':eye['label'],'lid':side,'blink':blink,'y':float(ys[ci]),'z':z,'required_raise_m':needed}))
                    x += needed
                front.append([x, float(ys[ci]), z])
            # Posterior wall is a real second surface; no zero-thickness sheet.
            return np.asarray(front + [[p[0] - thickness, p[1], p[2]] for p in front], np.float32).astype(float)
        neutral = positions(0.)
        # Orient each front triangle toward +X; all posterior/side winding follows it.
        for f in front_faces:
            q = neutral[f]
            if np.cross(q[1] - q[0], q[2] - q[0])[0] < 0: f.reverse()
        border = _boundary(front_faces); count = len(descriptors)
        faces = front_faces + [[v + count for v in reversed(f)] for f in front_faces]
        for a, b in zip(border, border[1:] + border[:1]):
            faces.extend([[b, a, a + count], [b, a + count, b + count]])
        states = {str(percent): positions(percent / 100) for percent in (0, 25, 50, 75, 100)}
        uv_by_column = []; uv_evidence = []
        for lo, hi in bounds:
            uv, evidence = _skin_uv(skin, hi if upper else lo, uv_support_distance)
            uv_by_column.append(uv); uv_evidence.append(evidence)
        uv_values=np.array([uv_by_column[descriptors[i % count][0]] for i in range(len(neutral))])
        pre_subdivision_reports={key:_topology(value,faces) for key,value in states.items()}
        fields=dict(states);fields['UV']=uv_values
        fields,faces,subdivision_reports=loop_subdivide_fields(fields,faces,loop_levels)
        uv_values=fields.pop('UV');states=fields;neutral=states['0']
        pose_reports = {key: _topology(value, faces) for key, value in states.items()}
        if any(r['boundary_edges'] or r['nonmanifold_edges'] or r['same_direction_pairs'] or r['degenerate_triangles'] for r in pose_reports.values()):
            raise RuntimeError('Closed lid has a structural/degenerate pose failure: ' + json.dumps(pose_reports))
        name = 'INTERNAL_ONLY__' + eye['label'] + '_' + side + '_closed_lid__' + revision
        mesh = bpy.data.meshes.new(name); mesh.from_pydata(neutral.tolist(), [], faces); mesh.update()
        obj = bpy.data.objects.new(name, mesh); collection.objects.link(obj)
        # Existing SM texture is reused. Each strip inherits measured native skin
        # UV support at its fixed outer contour, never iris-blue sampling/repaint.
        for material in skin.data.materials: mesh.materials.append(material)
        layer = mesh.uv_layers.new(name=skin.data.uv_layers.active.name)
        for loop in mesh.loops:
            layer.data[loop.index].uv = uv_values[loop.vertex_index]
        for face in mesh.polygons: face.use_smooth = True
        obj.shape_key_add(name='Basis')
        for percent in (25, 50, 75, 100):
            key = obj.shape_key_add(name='blink_' + str(percent))
            key.data.foreach_set('co', states[str(percent)].astype(np.float32).ravel())
        obj['internal_only'] = True; obj['acceptance'] = 'UNACCEPTED_INTERNAL_EYE_STAGE'
        obj['measured_aperture_eye'] = eye['label']; obj['closed_lid_side'] = side
        outputs.append((obj, states, faces))
        reports.append({'object': name, 'pose_topology': pose_reports,
                        'before_subdivision_topology':pre_subdivision_reports,'loop_subdivision':subdivision_reports,
                        'maximum_native_cap_clearance_raise_m': max(depth_corrections, default=0.),
                        'uv_source_support': uv_evidence, 'source_texture_reused_no_repaint': True})
    return outputs, reports


def set_blink(objects, value):
    value = max(0., min(1., float(value))); x = value * 4
    lo = int(math.floor(x)); hi = min(4, lo + 1); fraction = x - lo
    for obj in objects:
        for percent in (25, 50, 75, 100): obj.data.shape_keys.key_blocks['blink_' + str(percent)].value = 0
        if lo: obj.data.shape_keys.key_blocks['blink_' + str(lo * 25)].value = 1 - fraction
        if hi and hi != lo: obj.data.shape_keys.key_blocks['blink_' + str(hi * 25)].value = fraction


def integrate(profile, target_scene='INTERNAL_ONLY_visibility_portals-001',
              skin_name='INTERNAL_ONLY__SM_000_protected_facial_skin', posterior_depth_m=.008,
              posterior_rings=16, lid_columns=48, lid_rows=6, thickness_m=.00003,
              clearance_m=.00008, neutral_fraction=.03, maximum_raise_m=.0005,
              uv_support_distance_m=.008, revision='eyes-001',loop_levels=2):
    import bpy
    import numpy as np
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',revision): raise RuntimeError('Invalid private revision name')
    root = _private_root(bpy); report_path = root / ('sm-eye-integration-'+revision+'.json')
    collection_name=COLLECTION+'__'+revision
    if report_path.exists() or bpy.data.collections.get(collection_name):
        raise RuntimeError('This eye revision already exists; choose a new revision to retain previous evidence')
    target = bpy.data.scenes.get(target_scene); skin = bpy.data.objects.get(skin_name)
    if target is None or skin is None: raise RuntimeError('Private target scene or protected source skin missing')
    active = bpy.context.window.scene if bpy.context.window else None
    collection = bpy.data.collections.new(collection_name); target.collection.children.link(collection)
    collection['internal_only'] = True; collection['acceptance'] = 'UNACCEPTED_INTERNAL_EYE_STAGE'
    report = {'status': 'UNACCEPTED_INTERNAL_EYE_STAGE', 'exports': 0, 'eyes': [],
              'outer_SM_skin_modified': False, 'source_objects_modified': False,
              'quad_requirement': False, 'full_oblique_anatomy_audit_still_required': True,
              'standalone_ray_scope':'Whole closed globe projection, not aperture-constrained or full-scene visibility; diagnostic only',
              'known_lid_construction_limit':'Raw ribbon return walls fail crease gate; shared-stencil Loop rounding must pass actual final pose triangles, rays and visuals',
              'parameters':{'revision':revision,'target_scene':target_scene,'skin_name':skin_name,
                 'posterior_depth_m':posterior_depth_m,'posterior_rings':posterior_rings,
                 'lid_columns':lid_columns,'lid_rows':lid_rows,'thickness_m':thickness_m,
                 'clearance_m':clearance_m,'neutral_fraction':neutral_fraction,'maximum_raise_m':maximum_raise_m,
                 'uv_support_distance_m':uv_support_distance_m,'loop_levels':loop_levels,'cap_names':CAP_NAMES,
                 'profile_sha256':hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':')).encode()).hexdigest()},
              'created_objects':[]}
    selected={'globes':[],'lids':[]}
    try:
        for eye in profile['character']['eyes']:
            source = bpy.data.objects.get(CAP_NAMES[eye['label']])
            if source is None: raise RuntimeError('Authoritatively bound SM iris cap is missing')
            cap, points, faces, cap_report = _closed_cap(source, eye, collection, posterior_depth_m, posterior_rings,revision)
            selected['globes'].append(cap);report['created_objects'].append(cap.name)
            lids, lid_reports = _lids(eye, points, faces, skin, collection, lid_columns, lid_rows,
                thickness_m, clearance_m, neutral_fraction, maximum_raise_m, uv_support_distance_m,revision,loop_levels)
            selected['lids'].extend(obj for obj,states,faces0 in lids)
            report['created_objects'].extend(obj.name for obj,states,faces0 in lids)
            tree = _bvh(points, faces); closed_trees = [_bvh(states['100'], lid_faces) for obj, states, lid_faces in lids]
            lo, hi = points.min(axis=0), points.max(axis=0); rays = exposed = 0
            for y in np.linspace(lo[1], hi[1], 33):
                for z in np.linspace(lo[2], hi[2], 33):
                    hit = _cast(tree, float(y), float(z), float(hi[0] + .1))
                    if hit is None: continue
                    rays += 1
                    covers = [_cast(t, float(y), float(z), float(hi[0] + .1)) for t in closed_trees]
                    if not any(h and h[0] > hit[0] for h in covers): exposed += 1
            if not rays: raise RuntimeError('No actual closed-globe ray observations')
            report['eyes'].append({'eye': eye['label'], 'closed_globe': cap_report, 'lids': lid_reports,
                'closed_front_rays': rays, 'closed_front_exposed_or_empty': exposed,
                'source_cap_remains_visible_until_root_composes_stage': source.name})
        if active is not None and bpy.context.window.scene != active: raise RuntimeError('Active operator scene changed')
        report['active_scene_preserved'] = True
        report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    except Exception as error:
        # Keep diagnostic staging objects and mark them unusable; no source edits.
        report['status'] = 'FAILED_CLOSED_UNACCEPTED_INTERNAL_STAGE'; report['error'] = str(error)
        collection['acceptance'] = 'FAILED_UNACCEPTED_DO_NOT_EXPORT'
        report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        raise
    print(json.dumps({'status': report['status'], 'eyes': [{'eye': r['eye'],
        'rays': r['closed_front_rays'], 'exposed': r['closed_front_exposed_or_empty'],
        'globe_boundary_edges': r['closed_globe']['topology']['boundary_edges']} for r in report['eyes']],
        'private_report': report_path.name, 'source_objects_modified': False, 'exports': 0}))
    return {'report':report,'objects':selected,'collection':collection}


