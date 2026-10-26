# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,numpy as np,pathlib,json,collections,math
from mathutils import Vector
def build(cfg):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);src=bpy.data.objects[cfg['source']];m=src.data
    cy,cz=cfg['center_yz'];w=cfg['half_width'];h=cfg['neutral_half_height']
    theta=np.linspace(0,2*np.pi,cfg['cut_sides'],endpoint=False);poly=np.column_stack((cy+w*np.cos(theta),cz+h*np.sin(theta)))
    world=np.array([list(src.matrix_world@v.co) for v in m.vertices]);normal_matrix=src.matrix_world.to_3x3().inverted().transposed()
    pieces=[];removed=[];cut_points=[]
    def simplify(p):
        out=[]
        for v in p:
            if not out or np.linalg.norm(v[:3]-out[-1][:3])>1e-10:out.append(v)
        if len(out)>1 and np.linalg.norm(out[0][:3]-out[-1][:3])<1e-10:out.pop()
        return out
    def half(p,a,b,inside):
        result=[]
        for u,v in zip(p,p[1:]+p[:1]):
            du=np.cross(b-a,u[1:3]-a);dv=np.cross(b-a,v[1:3]-a)
            iu=du>=-1e-16 if inside else du<=1e-16;iv=dv>=-1e-16 if inside else dv<=1e-16
            if iu:result.append(u)
            if iu!=iv:
                t=du/(du-dv);result.append(u+t*(v-u))
        return simplify(result)
    for fi,face in enumerate(m.polygons):
        rows=[]
        for vi,li in zip(face.vertices,face.loop_indices):
            norm=normal_matrix@m.corner_normals[li].vector;norm.normalize()
            rows.append(np.r_[world[vi],list(m.uv_layers.active.data[li].uv),list(norm)])
        q=world[list(face.vertices)]
        if q[:,0].min()<cfg['front_min_x'] or q[:,1].min()>cy+w or q[:,1].max()<cy-w or q[:,2].min()>cz+h or q[:,2].max()<cz-h:
            pieces.append((fi,rows));continue
        remaining=rows;local=[]
        for a,b in zip(poly,np.roll(poly,-1,axis=0)):
            if not remaining:break
            outside=half(remaining,a,b,False)
            if len(outside)>=3:local.append(outside)
            remaining=half(remaining,a,b,True)
        if len(remaining)>=3:removed.append(fi)
        if local:
            for piece in local:pieces.append((fi,piece));cut_points.extend(x[:3] for x in piece)
        elif not remaining:pieces.append((fi,rows))
    cp=np.unique(np.round(np.array(cut_points),10),axis=0)
    # Conform every affected source edge to all actual clipping vertices.
    stitched=[]
    for fi,piece in pieces:
        result=[]
        for a,b in zip(piece,piece[1:]+piece[:1]):
            result.append(a);edge=b[:3]-a[:3];ll=edge@edge
            if ll<1e-20:continue
            t=((cp-a[:3])@edge)/ll;d=np.linalg.norm(cp-(a[:3]+t[:,None]*edge),axis=1);sel=np.flatnonzero((t>1e-8)&(t<1-1e-8)&(d<3e-9))
            for idx in sel[np.argsort(t[sel])]:result.append(a+t[idx]*(b-a))
        stitched.append((fi,simplify(result)))
    verts=[];lookup=collections.defaultdict(list);faces=[];uv=[];normals=[];ancestry=[]
    def vertex(co):
        key=tuple(np.floor(co*1e8).astype(np.int64))
        for dx in [-1,0,1]:
            for dy in [-1,0,1]:
                for dz in [-1,0,1]:
                    for idx in lookup.get((key[0]+dx,key[1]+dy,key[2]+dz),[]):
                        if np.linalg.norm(np.array(verts[idx])-co)<1e-8:return idx
        idx=len(verts);lookup[key].append(idx);verts.append(co.tolist());return idx
    for fi,piece in stitched:
        if len(piece)<3:continue
        tris=[piece] if len(piece)==3 else [[piece[i],piece[(i+1)%len(piece)],np.mean(piece,axis=0)] for i in range(len(piece))]
        for tri in tris:
            q=np.array([x[:3] for x in tri])
            if np.linalg.norm(np.cross(q[1]-q[0],q[2]-q[0]))<1e-15:continue
            faces.append([vertex(x[:3]) for x in tri]);uv.append([x[3:5].tolist() for x in tri]);normals.append([x[5:8].tolist() for x in tri]);ancestry.append(fi)
    uses=collections.defaultdict(list)
    for fi,f in enumerate(faces):
        for a,b in zip(f,f[1:]+f[:1]):uses[tuple(sorted((a,b)))].append((fi,a,b))
    mouth_edges=[u[0] for e,u in uses.items() if len(u)==1 and all(verts[i][0]>cfg['front_min_x'] and abs(verts[i][1]-cy)<w*1.01 and abs(verts[i][2]-cz)<h*1.02 for i in e)]
    nxt={a:b for _,a,b in mouth_edges}
    if not nxt or len(nxt)!=len(mouth_edges):
        (root/(cfg['revision']+'-cut-failed.json')).write_text(json.dumps({'mouth_boundary_edges':mouth_edges,'vertices':verts,'removed':removed,'all_boundary_count':sum(len(u)==1 for u in uses.values())}))
        raise RuntimeError('Mouth cut is not a simple directed rim: '+str(len(mouth_edges)))
    start=next(iter(nxt));loop=[start];k=nxt[start]
    while k!=start:
        if k in loop or k not in nxt:raise RuntimeError('Mouth boundary chain is not closed')
        loop.append(k);k=nxt[k]
    if len(loop)!=len(mouth_edges):
        seen=set(loop);loops=[loop]
        for start2 in nxt:
            if start2 in seen:continue
            ll=[start2];k=nxt[start2]
            while k!=start2:
                if k in ll or k not in nxt:raise RuntimeError('Broken secondary mouth loop')
                ll.append(k);k=nxt[k]
            seen.update(ll);loops.append(ll)
        metrics=[]
        for ll in loops:
            vv=np.array([verts[i] for i in ll]);area=abs(np.sum(vv[:,1]*np.roll(vv[:,2],-1)-vv[:,2]*np.roll(vv[:,1],-1)))/2
            metrics.append({'vertices':len(ll),'area_yz':float(area),'mean_x':float(vv[:,0].mean()),'min_x':float(vv[:,0].min()),'max_x':float(vv[:,0].max())})
        (root/(cfg['revision']+'-cut-loops.json')).write_text(json.dumps(metrics,indent=2))
        candidates=[i for i,entry in enumerate(metrics) if entry['area_yz']>np.pi*w*h*.95]
        if not candidates:raise RuntimeError('No complete measured aperture loop: '+str(metrics))
        best=max(candidates,key=lambda i:metrics[i]['mean_x']);loop=loops[best]
    rim=np.array([verts[i] for i in loop]);theta=np.arctan2((rim[:,2]-cz)/h,(rim[:,1]-cy)/w)
    cavity=[];cavity_start=len(faces)
    for row in range(1,cfg['cavity_rows']+1):
        t=row/cfg['cavity_rows'];positions=rim.copy();positions[:,0]-=cfg['depth_m']*t
        positions[:,1]=cy+(rim[:,1]-cy)*(1+.15*np.sin(np.pi*t))
        positions[:,2]=rim[:,2]+cfg['inner_half_height']*np.sin(theta)*np.sin(np.pi*t/2)
        ring=[vertex(co) for co in positions];previous=loop if row==1 else cavity[-1]
        for i in range(len(loop)):
            j=(i+1)%len(loop);faces.extend([[previous[j],previous[i],ring[i]],[previous[j],ring[i],ring[j]]]);ancestry.extend([-1,-1]);uv.extend([[[0,0]]*3]*2);normals.extend([[[0,0,0]]*3]*2)
        cavity.append(ring)
    center=np.array([verts[i] for i in cavity[-1]]).mean(axis=0);center[0]-=.001;pole=vertex(center)
    for i in range(len(loop)):
        faces.append([cavity[-1][(i+1)%len(loop)],cavity[-1][i],pole]);ancestry.append(-1);uv.append([[0,0]]*3);normals.append([[0,0,0]]*3)
    mesh=bpy.data.meshes.new('INTERNAL_ONLY_mouth_'+cfg['revision']);mesh.from_pydata(verts,[],faces);mesh.update()
    for material in m.materials:mesh.materials.append(material)
    inner=bpy.data.materials.new('INTERNAL_ONLY_own_oral_dark_'+cfg['revision']);inner.diffuse_color=(.035,.008,.012,1);inner.use_nodes=True;next(n for n in inner.node_tree.nodes if n.type=='BSDF_PRINCIPLED').inputs['Base Color'].default_value=(.035,.008,.012,1);mesh.materials.append(inner)
    for i,f in enumerate(mesh.polygons):f.use_smooth=True;f.material_index=len(mesh.materials)-1 if i>=cavity_start else 0
    layer=mesh.uv_layers.new(name='UVMap');layer.data.foreach_set('uv',np.array(uv,np.float32).ravel())
    attr=mesh.attributes.new('native_SM_vertex_id','INT','POINT');attr.data.foreach_set('value',np.arange(len(verts),dtype=np.int32));attr=mesh.attributes.new('source_SM_face_id','INT','FACE');attr.data.foreach_set('value',np.array(ancestry,np.int32))
    ob=bpy.data.objects.new('INTERNAL_ONLY_SM_mouth_'+cfg['revision'],mesh);scene=bpy.data.scenes.new('INTERNAL_ONLY_mouth_'+cfg['revision'])
    for item in bpy.data.scenes[cfg['source_scene']].objects:
        if item!=src and 'closed_oral_lining_candidate' not in item.name:scene.collection.objects.link(item)
    scene.collection.objects.link(ob)
    base=np.array(verts);target=base.copy()
    # Smooth monotone lower-face drop; no deformation crosses the actual opening.
    u=(base[:,1]-cy)/w
    smooth=lambda x:np.clip(x,0,1)**2*(3-2*np.clip(x,0,1))
    side=smooth((np.abs(base[:,1]-cy)-w*.75)/(w*.5))
    band=np.maximum(h*np.sqrt(np.maximum(0,1-u*u)),.00002)+.003*side
    weight=smooth((cz+band-base[:,2])/(2*band))*(1-smooth((np.abs(base[:,1]-cy)-.02)/.02))*smooth((base[:,2]-.84)/.015)
    pivot=np.array(cfg['jaw_pivot']);ang=np.radians(cfg['jaw_degrees']);rel=base-pivot
    rotated=rel.copy();rotated[:,0]=np.cos(ang)*rel[:,0]+np.sin(ang)*rel[:,2];rotated[:,2]=-np.sin(ang)*rel[:,0]+np.cos(ang)*rel[:,2]
    target=base+(rotated+pivot-base)*weight[:,None]
    for row,ring in enumerate(cavity,1):
        t=row/cfg['cavity_rows'];rimtarget=target[loop];positions=rimtarget.copy();positions[:,0]-=cfg['depth_m']*t
        positions[:,1]=cy+(rimtarget[:,1]-cy)*(1+.15*np.sin(np.pi*t))
        positions[:,2]=rimtarget[:,2]+cfg['inner_half_height']*np.sin(theta)*np.sin(np.pi*t/2)
        target[ring]=positions
    target[pole]=target[cavity[-1]].mean(axis=0);target[pole,0]-=.001
    ob.shape_key_add(name='Basis');key=ob.shape_key_add(name='jawOpen');key.value=0;key.data.foreach_set('co',target.astype(np.float32).ravel())
    audit=[]
    for jaw in [0,.25,.5,.75,1]:
        v=base+(target-base)*jaw;a=bpy.app.driver_namespace['dsh_private_topology_core']['analyze'](v,faces,faces,np.arange(len(faces)),reference_local_vertices=base,local_vertices=v)
        audit.append({'jaw':jaw,**{k:a[k] for k in ['boundary_edges','nonmanifold_edges','same_direction_edges','degenerate_triangles','adjacent_normal_degrees','reference_normal_reversals']}})
    report={'classification':'INTERNAL_ONLY','status':'UNACCEPTED','profile':cfg,'scene':scene.name,'object':ob.name,'cut_source_faces':removed,'rim_vertices':loop,'cavity_faces_from':cavity_start,'cavity_rings':cavity,'cavity_pole':pole,'audit':audit}
    (root/(cfg['revision']+'-mouth.json')).write_text(json.dumps(report,indent=2));return report
