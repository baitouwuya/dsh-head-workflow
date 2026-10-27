# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Transfer measured skin COLOR values without interpolating unrelated UV charts.

The caller supplies semantic skin-triangle bindings. Original source UVs and
image bytes are read only. Generated geometry uses linear glTF COLOR_0 with a
texture-free white base material; it must not retain the source atlas material.
"""
import copy
import heapq
import numpy as np

def _indices(value,name,*,ndim=1,upper=None):
    a=np.asarray(value)
    if a.ndim!=ndim or not a.size or not np.issubdtype(a.dtype,np.integer) or (a<0).any() or (upper is not None and (a>=upper).any()):
        raise ValueError(name+' must contain nonempty valid integer indices')
    return a.astype(np.int64,copy=False)

def _faces(value,vertex_count):
    f=_indices(value,'faces',ndim=2,upper=vertex_count)
    if f.shape[1]!=3:raise ValueError('faces must be Nx3 triangle indices')
    return f

def _rgba(value,name):
    a=np.asarray(value,dtype=float)
    if a.ndim!=2 or a.shape[1]!=4 or not len(a) or not np.isfinite(a).all() or (a<0).any() or (a>1).any():
        raise ValueError(name+' must contain normalized finite linear RGBA values')
    return a


def audit_source_uv_charts(positions,faces,uv,position_tolerance,
                           uv_tolerance=1e-8,triangle_material_ids=None):
    """Measure actual incoming UV charts without relying on exporter vertex IDs.

    Coincident positions are welded only in this read-only diagnostic. Charts
    connect across an edge only when both endpoint UVs and material IDs agree.
    Supply the measured working-frame tolerance and the actual source material
    assignment; a single-material input may omit ``triangle_material_ids``.
    """
    p=np.asarray(positions,dtype=float);uv=np.asarray(uv,dtype=float);f=_faces(faces,len(p))
    if p.ndim!=2 or p.shape[1]!=3 or not len(p) or uv.shape!=(len(p),2) or f.ndim!=2 or f.shape[1]!=3 or not np.isfinite(p).all() or not np.isfinite(uv).all() or (f<0).any() or (f>=len(p)).any():
        raise ValueError('UV audit requires finite per-vertex positions/UVs and valid triangles')
    if not np.isfinite(position_tolerance) or position_tolerance<=0 or not np.isfinite(uv_tolerance) or uv_tolerance<=0:
        raise ValueError('UV audit tolerances must be finite and positive')
    material=np.zeros(len(f),dtype=int) if triangle_material_ids is None else np.asarray(triangle_material_ids)
    if material.shape!=(len(f),):raise ValueError('material IDs must be per triangle')
    quantized=np.round((p-p.mean(0))/position_tolerance)
    if not np.isfinite(quantized).all() or (abs(quantized)>=float(np.iinfo(np.int64).max)).any():raise ValueError('position tolerance overflows canonical quantization')
    _,canonical=np.unique(quantized.astype(np.int64),axis=0,return_inverse=True)
    parent=np.arange(len(f));edges={};seam_pairs=0;material_pairs=0
    def root(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for face_id,face in enumerate(f):
        for a,b in zip(face,np.roll(face,-1)):
            if canonical[a]==canonical[b]:continue
            key=tuple(sorted((int(canonical[a]),int(canonical[b]))))
            edge_uv=np.array([uv[a],uv[b]]) if canonical[a]<canonical[b] else np.array([uv[b],uv[a]])
            for other,other_uv in edges.get(key,[]):
                if material[face_id]!=material[other]:material_pairs+=1
                elif np.max(np.abs(edge_uv-other_uv))<=uv_tolerance:parent[root(face_id)]=root(other)
                else:seam_pairs+=1
            edges.setdefault(key,[]).append((face_id,edge_uv))
    _,counts=np.unique([root(i) for i in range(len(f))],return_counts=True)
    t=uv[f];area=np.abs((t[:,1,0]-t[:,0,0])*(t[:,2,1]-t[:,0,1])-(t[:,1,1]-t[:,0,1])*(t[:,2,0]-t[:,0,0]))
    return {'source_vertex_count':len(p),'source_triangle_count':len(f),'geometric_position_clusters':int(canonical.max()+1) if len(canonical) else 0,
            'uv_chart_count':len(counts),'chart_triangle_counts_descending':sorted(counts.astype(int).tolist(),reverse=True),
            'uv_discontinuous_shared_geometric_edge_pairs':seam_pairs,'different_material_edge_pairs':material_pairs,
            'geometric_boundary_edges':sum(len(v)==1 for v in edges.values()),
            'degenerate_uv_triangles':int((area<=uv_tolerance**2).sum()),
            'material_count':len(np.unique(material)),'position_tolerance':float(position_tolerance),'uv_tolerance':float(uv_tolerance),
            'original_topology_uv_and_image_changed':False,'exporter_vertex_ids_or_material_names_used':False}


def srgb_to_linear(rgb):
    a=np.asarray(rgb,dtype=np.float64)
    return np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)


def linear_to_srgb(rgb):
    a=np.asarray(rgb,dtype=np.float64)
    return np.where(a<=.0031308,12.92*a,1.055*np.maximum(a,0)**(1/2.4)-.055)


def sample_texture_rgb(image, uv, uv_origin='top-left'):
    """Linear-color bilinear sampling of top-row-first RGB, REPEAT wrapping.

    Declare incoming UV convention explicitly: glTF uses top-left, while Blender
    mesh UV coordinates generally use bottom-left. Image bytes are never flipped.
    ``image`` is decoded encoded-sRGB RGB data (for example PIL from original
    bytes), not Blender's already-linear ``image.pixels`` buffer.
    """
    image=np.asarray(image)
    if image.ndim!=3 or image.shape[2]<3 or min(image.shape[:2])<1:
        raise ValueError('image must be HxWxRGB(A)')
    divisor=np.iinfo(image.dtype).max if image.dtype.kind in 'ui' else 1
    rgb=image[...,:3]
    if not np.isfinite(rgb).all() or rgb.min()<0 or rgb.max()>divisor:
        raise ValueError('image colors must be finite normalized sRGB')
    uv=np.asarray(uv,dtype=np.float64)
    if uv.ndim!=2 or uv.shape[1]!=2 or not np.isfinite(uv).all():
        raise ValueError('UVs must be finite Nx2')
    if uv_origin not in ('top-left','bottom-left'):
        raise ValueError('UV origin must be top-left or bottom-left')
    if uv_origin=='bottom-left':
        uv=uv.copy();uv[:,1]=1-uv[:,1]
    h,w=rgb.shape[:2]
    p=(uv%1)*np.array([w,h])-.5
    base=np.floor(p).astype(np.int64);t=p-base
    x0=base[:,0]%w;y0=base[:,1]%h;x1=(x0+1)%w;y1=(y0+1)%h
    c00=srgb_to_linear(rgb[y0,x0]/divisor);c10=srgb_to_linear(rgb[y0,x1]/divisor);c01=srgb_to_linear(rgb[y1,x0]/divisor);c11=srgb_to_linear(rgb[y1,x1]/divisor)
    tx=t[:,0,None];ty=t[:,1,None]
    return (c00*(1-tx)+c10*tx)*(1-ty)+(c01*(1-tx)+c11*tx)*ty


def transfer_skin_colors(source_faces, source_uv, image, triangle_ids,
                         barycentric_weights, allowed_skin_triangle_ids,
                         source_material=None,uv_origin='top-left'):
    """Return linear RGBA and audited one-source-triangle-per-vertex UV bindings.

    Each output color is sampled inside one explicitly allowed source triangle.
    UVs are interpolated only within that source triangle, never between samples
    belonging to different source charts. Generated triangles interpolate the
    returned COLOR values. Role assignment/attachment remain caller obligations.
    """
    uv=np.asarray(source_uv,dtype=np.float64);faces=_faces(source_faces,len(uv))
    triangle_ids=_indices(triangle_ids,'triangle_ids',upper=len(faces));weights=np.asarray(barycentric_weights,dtype=np.float64)
    allowed_skin_triangle_ids=_indices(allowed_skin_triangle_ids,'allowed_skin_triangle_ids',upper=len(faces))
    if faces.ndim!=2 or faces.shape[1]!=3 or uv.ndim!=2 or uv.shape[1]!=2:
        raise ValueError('source requires triangle faces and per-vertex UVs')
    if triangle_ids.ndim!=1 or weights.shape!=(len(triangle_ids),3):
        raise ValueError('bindings require one triangle and three weights per generated vertex')
    if not np.isfinite(weights).all() or (weights < -1e-9).any() or not np.allclose(weights.sum(1),1,rtol=0,atol=1e-8):
        raise ValueError('source barycentric weights must be finite, nonnegative and sum to one')
    if (triangle_ids<0).any() or (triangle_ids>=len(faces)).any() or not np.isin(triangle_ids,allowed_skin_triangle_ids).all():
        raise ValueError('a binding targets a missing or unapproved skin triangle')
    if (faces<0).any() or (faces>=len(uv)).any() or not np.isfinite(uv).all():
        raise ValueError('source UV indices or coordinates are invalid')
    sampled_uv=np.einsum('ni,nij->nj',weights,uv[faces[triangle_ids]])
    rgb=sample_texture_rgb(image,sampled_uv,uv_origin)
    colors=np.column_stack([rgb,np.ones(len(rgb))]).astype(np.float32)
    source_material=source_material or {}
    source_pbr=source_material.get('pbrMetallicRoughness',{})
    material={'name':'measured-skin-vertex-color',
              'doubleSided':source_material.get('doubleSided',True),
              'pbrMetallicRoughness':{
                  'baseColorFactor':copy.deepcopy(source_pbr.get('baseColorFactor',[1,1,1,1])),
                  'metallicFactor':source_pbr.get('metallicFactor',0),
                  'roughnessFactor':source_pbr.get('roughnessFactor',.9)}}
    return {'colors_linear_rgba':colors,'source_triangle_ids':triangle_ids.copy(),
            'source_barycentric_weights':weights.copy(),'sampled_source_uv':sampled_uv,
            'material':material,
            'attribute':'COLOR_0','encoding':'linear RGBA float32',
            'source_uv_origin':uv_origin,
            'source_encoded_image_bytes_audited':False,
            'source_image_unchanged':True,'source_uv_unchanged':True,
            'generated_material_uses_source_atlas':False}


def transfer_lid_anchor_colors(source_faces,source_uv,image,
                               anchor_triangle_ids,anchor_barycentric_weights,
                               vertex_anchor_indices,allowed_skin_triangle_ids,
                               source_material=None,uv_origin='top-left'):
    """Propagate explicitly bound anchor COLOR values through a generated lid.

    ``vertex_anchor_indices`` maps every generated vertex to a source-skin anchor.
    The mapping is explicit and topology-independent; no assumed row count,
    nearest vertex search, UV-chart averaging or automatic semantic assignment.
    A more detailed transfer may supply per-vertex source bindings directly to
    ``transfer_skin_colors`` instead of propagating anchor colors.
    """
    triangles=_indices(anchor_triangle_ids,'anchor_triangle_ids')
    index=_indices(vertex_anchor_indices,'generated-to-anchor mapping',upper=len(triangles))
    weights=np.asarray(anchor_barycentric_weights,dtype=float)
    if index.ndim!=1 or triangles.ndim!=1 or weights.shape!=(len(triangles),3) or (index<0).any() or (index>=len(triangles)).any():
        raise ValueError('generated-to-anchor mapping is invalid')
    return transfer_skin_colors(source_faces,source_uv,image,triangles[index],weights[index],allowed_skin_triangle_ids,source_material,uv_origin)


def interpolate_skin_color_strip(reference_parameter,reference_linear_rgba,vertex_parameter):
    """Interpolate already sampled COLOR values along an explicit skin strip.

    The caller must derive and validate this reference outside eye/lash paint.
    This operation never averages UVs across charts. Out-of-range parameters
    clamp to the measured endpoints and are reported explicitly.
    """
    x=np.asarray(reference_parameter,dtype=float);c=_rgba(reference_linear_rgba,'reference colors');q=np.asarray(vertex_parameter,dtype=float)
    if x.ndim!=1 or len(x)<2 or c.shape!=(len(x),4) or q.ndim!=1 or not len(q) or not np.isfinite(x).all() or not np.isfinite(c).all() or not np.isfinite(q).all() or not np.all(np.diff(x)>0):
        raise ValueError('skin strip requires finite strictly ordered parameters and RGBA samples')
    return {'colors_linear_rgba':np.column_stack([np.interp(q,x,c[:,i]) for i in range(4)]).astype(np.float32),
            'clamped_query_count':int(((q<x[0])|(q>x[-1])).sum()),
            'reference_parameter_range':[float(x[0]),float(x[-1])]}


def blend_skin_boundary_colors(vertices,faces,boundary_indices,interior_indices,
                               bound_linear_rgba,clean_skin_linear_rgba,
                               boundary_exponent=2):
    """Keep source boundary color exact; fade toward a clean measured skin field.

    Graph distances use the actual generated topology, not exporter IDs or row
    assumptions. The explicit source-skin field prevents baked eyeliner from
    being propagated across an entire eyelid. It is an appearance approximation,
    not restoration of unobserved skin texture or a semantic classifier.
    """
    p=np.asarray(vertices,dtype=float);f=_faces(faces,len(p));a=_rgba(bound_linear_rgba,'bound colors');b=_rgba(clean_skin_linear_rgba,'clean skin colors');boundary=np.unique(_indices(boundary_indices,'boundary_indices',upper=len(p)));inner=np.unique(_indices(interior_indices,'interior_indices',upper=len(p)))
    if p.ndim!=2 or p.shape[1]!=3 or f.ndim!=2 or f.shape[1]!=3 or a.shape!=(len(p),4) or b.shape!=a.shape or not np.isfinite(p).all() or not np.isfinite(a).all() or not np.isfinite(b).all() or not np.isfinite(boundary_exponent) or boundary_exponent<=0:
        raise ValueError('invalid generated appearance geometry or colors')
    if not len(boundary) or not len(inner) or np.intersect1d(boundary,inner).size or min(f.min(),boundary.min(),inner.min())<0 or max(f.max(),boundary.max(),inner.max())>=len(p):
        raise ValueError('boundary and interior constraints must be valid and disjoint')
    edges=np.unique(np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1),axis=0);adj=[[] for _ in p]
    for i,j in edges:
        distance=float(np.linalg.norm(p[i]-p[j]));adj[i].append((int(j),distance));adj[j].append((int(i),distance))
    def distances(seeds):
        d=np.full(len(p),np.inf);queue=[]
        for i in seeds:d[i]=0;heapq.heappush(queue,(0,int(i)))
        while queue:
            dist,i=heapq.heappop(queue)
            if dist!=d[i]:continue
            for other,edge in adj[i]:
                candidate=dist+edge
                if candidate<d[other]:d[other]=candidate;heapq.heappush(queue,(candidate,other))
        if not np.isfinite(d).all():raise ValueError('generated appearance graph has an unconstrained disconnected component')
        return d
    db=distances(boundary);di=distances(inner);den=db+di
    if (den<=0).any():raise ValueError('collapsed appearance distance constraints')
    fraction=db/den;influence=(1-fraction)**boundary_exponent;result=a*influence[:,None]+b*(1-influence[:,None]);result[boundary]=a[boundary];result[inner]=b[inner]
    return {'colors_linear_rgba':result.astype(np.float32),'interior_fraction':fraction,'boundary_color_influence':influence,
            'boundary_exponent':float(boundary_exponent),'boundary_color_max_error_before_float32':float(abs(result[boundary]-a[boundary]).max()),
            'interior_reference_max_error_before_float32':float(abs(result[inner]-b[inner]).max())}


def audit_uv_chart_excursions(image, generated_uv, faces, excursion_tolerance=.05,uv_origin='top-left'):
    """Detect a texture value leaving the range of its triangle's corner colors.

    Sample locations are fixed barycentric coordinates. A chart jump may produce
    values unrelated to all three source samples even if endpoint skin is valid.
    This diagnostic is not a general proof that a source texture is seam-free.
    """
    uv=np.asarray(generated_uv,dtype=float);faces=_faces(faces,len(uv))
    if uv.ndim!=2 or uv.shape[1]!=2 or not len(uv) or not np.isfinite(uv).all():raise ValueError('UV audit requires nonempty finite Nx2 coordinates')
    if not np.isfinite(excursion_tolerance) or excursion_tolerance<0:raise ValueError('excursion tolerance must be finite and nonnegative')
    bary=np.array([[1/3,1/3,1/3],[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]])
    corners=sample_texture_rgb(image,uv,uv_origin)
    query=np.einsum('si,fij->fsj',bary,uv[faces])
    actual=sample_texture_rgb(image,query.reshape(-1,2),uv_origin).reshape(len(faces),len(bary),3)
    lo=corners[faces].min(1)[:,None,:];hi=corners[faces].max(1)[:,None,:]
    excursion=np.maximum(np.maximum(lo-actual,actual-hi),0).max(2)
    expected=np.einsum('si,fij->fsj',bary,corners[faces])
    actual_luminance=actual@np.array([.2126,.7152,.0722]);corner_luminance=corners[faces]@np.array([.2126,.7152,.0722])
    return {'sample_count':int(excursion.size),
            'outside_corner_color_range_samples':int((excursion>excursion_tolerance).sum()),
            'maximum_linear_color_excursion':float(excursion.max()),
            'mean_absolute_linear_error_from_color_interpolation':float(np.abs(actual-expected).mean()),
            'dark_samples_with_all_bright_corners':int(((actual_luminance<.2)&(corner_luminance.min(1)[:,None]>.5)).sum()),
            'texture_coordinate_edge_jump_max':float(np.linalg.norm(uv[faces]-np.roll(uv[faces],1,axis=1),axis=2).max())}
