# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,numpy as np,pathlib,json,collections,math
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt
def build(cfg):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);src=bpy.data.objects[cfg['source']];m=src.data
    base=np.array([list(v.co) for v in m.vertices]);target=np.array([list(v.co) for v in m.shape_keys.key_blocks['jawOpen'].data]);faces=[list(f.vertices) for f in m.polygons]
    data=json.loads((root/'mouth-002-open-wall-domains.json').read_text());vs=base.tolist();ts=target.tolist();newfaces=[];reports=[]
    cy,cz=cfg['center_yz'];w,h=cfg['half_width'],cfg['half_height']
    for group in data:
        loop=group['vertices'];theta=np.array(group['theta']);poly=np.column_stack((theta*w,base[loop,0]));N=len(poly)
        points=poly.tolist()
        def inside(q):
            ok=False
            for a,b in zip(poly,np.roll(poly,-1,axis=0)):
                if (a[1]>q[1])!=(b[1]>q[1]) and q[0]<(b[0]-a[0])*(q[1]-a[1])/(b[1]-a[1])+a[0]:ok=not ok
            return ok
        def edge_distance(q):
            a=poly;b=np.roll(poly,-1,axis=0);d=b-a;ss=np.clip(np.sum((q-a)*d,axis=1)/np.maximum(np.sum(d*d,axis=1),1e-30),0,1)
            return float(np.linalg.norm(q-(a+ss[:,None]*d),axis=1).min())
        for u in np.arange(poly[:,0].min()+cfg['grid_m'],poly[:,0].max(),cfg['grid_m']):
            for x in np.arange(poly[:,1].min()+cfg['grid_m'],poly[:,1].max(),cfg['grid_m']):
                q=np.array([u,x])
                if inside(q) and edge_distance(q)>cfg['grid_m']*.08:points.append(q.tolist())
        signed=np.sum(poly[:,0]*np.roll(poly[:,1],-1)-poly[:,1]*np.roll(poly[:,0],-1))
        order=list(range(N)) if signed>0 else list(reversed(range(N)))
        coords,ee,ff,ov,oe,of=delaunay_2d_cdt([Vector(v) for v in points],[],[order],1,1e-10,True)
        mapped=[];interpolation=[]
        for q,orig in zip(coords,ov):
            boundary=[i for i in orig if i<N]
            if len(boundary)>1:
                if max(np.linalg.norm(base[loop[i]]-base[loop[boundary[0]]]) for i in boundary)>1e-8:raise RuntimeError('CDT merged different original boundary vertices')
            if boundary:mapped.append(loop[boundary[0]]);continue
            u,x=map(float,q);crossings=[]
            for i,(a,b) in enumerate(zip(poly,np.roll(poly,-1,axis=0))):
                if abs(b[0]-a[0])<1e-14:continue
                t=(u-a[0])/(b[0]-a[0])
                if -1e-7<=t<=1+1e-7:
                    t=float(np.clip(t,0,1));ix=a[1]+t*(b[1]-a[1])
                    if not any(abs(ix-v[0])<1e-9 for v in crossings):crossings.append((ix,i,t))
            crossings.sort()
            interval=None
            for a,b in zip(crossings,crossings[1:]):
                if a[0]-1e-9<=x<=b[0]+1e-9 and b[0]-a[0]>1e-10:interval=(a,b);break
            if interval is None:raise RuntimeError('No actual boundary interpolation interval for '+str((u,x,crossings)))
            a,b=interval
            def endpoint(item,array):
                _,i,t=item;return array[loop[i]]*(1-t)+array[loop[(i+1)%N]]*t
            fraction=float(np.clip((x-a[0])/(b[0]-a[0]),0,1));co=endpoint(a,base)*(1-fraction)+endpoint(b,base)*fraction;posed=endpoint(a,target)*(1-fraction)+endpoint(b,target)*fraction
            mapped.append(len(vs));vs.append(co.tolist());ts.append(posed.tolist());interpolation.append({'vertex':mapped[-1],'theta_scaled':u,'x':x,'boundary_edges':[a[1],b[1]],'fraction':fraction})
        triangles=[[mapped[k] for k in f] for f in ff]
        edge=tuple(loop[:2]);orientation=None
        for f in triangles:
            for a,b in zip(f,f[1:]+f[:1]):
                if (a,b)==edge:orientation=True
                elif (b,a)==edge:orientation=False
        if orientation is None:raise RuntimeError('CDT changed the source boundary edge without splitting its owner')
        if orientation:triangles=[f[::-1] for f in triangles]
        newfaces.extend(triangles);reports.append({'source_boundary_vertices':loop,'triangles_added':len(triangles),'interpolation':interpolation})
    oldn=len(faces);faces+=newfaces
    mesh=bpy.data.meshes.new('INTERNAL_ONLY_portal_walls_'+cfg['revision']);mesh.from_pydata(vs,[],faces);mesh.update()
    for mat in m.materials:mesh.materials.append(mat)
    uv=mesh.uv_layers.new(name='UVMap')
    for i,l in enumerate(m.uv_layers.active.data):uv.data[i].uv=l.uv
    for i,f in enumerate(mesh.polygons):f.use_smooth=True;f.material_index=m.polygons[i].material_index if i<oldn else cfg['lining_material_index']
    attr=mesh.attributes.new('native_SM_vertex_id','INT','POINT');attr.data.foreach_set('value',np.arange(len(vs),dtype=np.int32))
    ob=bpy.data.objects.new('INTERNAL_ONLY_SM_portal_walls_'+cfg['revision'],mesh);scene=bpy.data.scenes.new('INTERNAL_ONLY_integrated_'+cfg['revision'])
    for o in bpy.data.scenes[cfg['source_scene']].objects:
        if o!=src:scene.collection.objects.link(o)
    scene.collection.objects.link(ob);ob.shape_key_add(name='Basis');key=ob.shape_key_add(name='jawOpen');key.value=0;key.data.foreach_set('co',np.array(ts,np.float32).ravel())
    audits=[]
    for jaw in cfg['jaw_samples']:
        v=np.array(vs)+(np.array(ts)-vs)*jaw
        a=bpy.app.driver_namespace['dsh_private_topology_core']['analyze'](v,faces,faces,np.arange(len(faces)),reference_local_vertices=vs,local_vertices=v)
        audits.append({'jaw':jaw,**{k:a[k] for k in ['boundary_edges','nonmanifold_edges','same_direction_edges','degenerate_triangles','adjacent_normal_degrees','reference_normal_reversals']}})
    report={'classification':'INTERNAL_ONLY','status':'UNACCEPTED','profile':cfg,'object':ob.name,'scene':scene.name,'old_faces_unchanged':oldn,'new_walls':reports,'audit':audits}
    (root/(cfg['revision']+'-portal-walls.json')).write_text(json.dumps(report,indent=2));return report
