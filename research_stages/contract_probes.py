# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
def rendered_hit(tree,vertices,triangles,culling,origin,direction,max_distance=1e6):
    """First actually rendered opaque surface; preserve current material culling."""
    from mathutils import Vector
    import numpy as np
    start=Vector(origin);d=Vector(direction);d.normalize();travel=0.0;skipped=0
    for _ in range(96):
        point,normal,face,distance=tree.ray_cast(start,d,max_distance-travel)
        if face is None:return None,None,None,None,skipped
        distance_total=travel+distance
        if not culling[face] or normal.dot(d)<0:return point,normal,face,distance_total,skipped
        skipped+=1;step=1e-7;travel=distance_total+step
        if travel>=max_distance:return None,None,None,None,skipped
        start=point+d*step
    raise RuntimeError('Rendered-ray traversal exhausted its declared96-layer limit')

import bpy,numpy as np,json,pathlib,math,collections,hashlib
from mathutils import Vector
from mathutils.bvhtree import BVHTree
def hull(points):
    pts=sorted(set(tuple(map(float,p)) for p in points));cross=lambda o,a,b:(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);lo=[];hi=[]
    for p in pts:
        while len(lo)>=2 and cross(lo[-2],lo[-1],p)<=0:lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi)>=2 and cross(hi[-2],hi[-1],p)<=0:hi.pop()
        hi.append(p)
    return np.array(lo[:-1]+hi[:-1])
def domain(poly,nx,nz):
    for x in np.linspace(poly[:,0].min(),poly[:,0].max(),nx)[1:-1]:
        zs=[]
        for a,b in zip(poly,np.roll(poly,-1,axis=0)):
            if min(a[0],b[0])<=x<=max(a[0],b[0]) and abs(a[0]-b[0])>1e-12:zs.append(a[1]+(x-a[0])/(b[0]-a[0])*(b[1]-a[1]))
        if len(zs)>1:
            for z in np.linspace(min(zs),max(zs),nz)[1:-1]:yield x,z
def apply(objects,jaw,left,right):
    for o in objects:
        if not o.data.shape_keys:continue
        keys=o.data.shape_keys.key_blocks
        for k in keys:
            if k.name!='Basis':k.value=0
        if 'jawOpen' in keys:keys['jawOpen'].value=jaw/15
        if 'rounded_lid' in o.name:
            b=right if 'right_' in o.name else left;x=b*4;lo=int(math.floor(x));hi=min(4,lo+1);frac=x-lo
            if lo:keys['blink_'+str(lo*25)].value=1-frac
            if hi and hi!=lo:keys['blink_'+str(hi*25)].value=frac
def evaluate(objects,dg,mouth):
    vv=[];ff=[];names=[];fis=[];culling=[];rim=None
    for o in objects:
        ev=o.evaluated_get(dg);m=ev.to_mesh();m.calc_loop_triangles();off=len(vv);v=[o.matrix_world@x.co for x in m.vertices];vv.extend(v)
        for t in m.loop_triangles:
            ff.append(tuple(off+i for i in t.vertices));names.append(o.name);fis.append(t.polygon_index);mat=m.materials[m.polygons[t.polygon_index].material_index];culling.append(bool(mat.use_backface_culling))
        if o.name==mouth:rim=np.array(v)
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(vv,ff,all_triangles=True),names,fis,rim,vv,ff,culling
def run(cfg,profile):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);scene=bpy.data.scenes[cfg['scene']];objects=[o for o in scene.objects if o.type=='MESH'];sampling=profile['sampling']
    saved_scene=bpy.context.window.scene;saved={o.name:[k.value for k in o.data.shape_keys.key_blocks] for o in objects if o.data.shape_keys}
    mouth_data=json.loads((root/cfg['mouth_report']).read_text());front=json.loads((root/cfg['entrance_report']).read_text());lining_set=set(mouth_data.get('lining_faces',[]));report={'classification':'INTERNAL_ONLY','status':'MEASURED_UNACCEPTED','profile':cfg,'source_sampling':sampling,'eyes':[],'mouth':[]}
    try:
        bpy.context.window.scene=scene
        for blink in sampling['blink_weights']:
            apply(objects,0,blink,blink);bpy.context.view_layer.update();tree,names,fis,bp,vv,ff,culling=evaluate(objects,bpy.context.evaluated_depsgraph_get(),cfg['mouth_object'])
            for eye in profile['character']['eyes']:
                total=empty=exposed=0;owners=collections.Counter();fails=[];skin_hits=0
                for y,z in domain(hull(np.array(eye['rim_xyz'])[:,1:]),*sampling['eye_grid']):
                    hit,n,fi,d,skipped_backfaces=rendered_hit(tree,vv,ff,culling,(.15,y,z),(-1,0,0));total+=1;owner=names[fi] if fi is not None else 'EMPTY';owners[owner]+=1
                    if fi is None:empty+=1
                    ocular='closed_native_SM_globe' in owner or 'closed_scleral_globe' in owner or owner in cfg['glints'][eye['label']]
                    if blink==1 and ocular:
                        exposed+=1
                        if len(fails)<cfg['witness_limit']:fails.append({'sample':[y,z],'hit_object':owner,'hit':list(hit)})
                    if owner==cfg['mouth_object']:skin_hits+=1
                report['eyes'].append({'side':eye['label'],'blink':blink,'rays':total,'empty':empty,'exposed_when_closed':exposed,'source_skin_first_hits':skin_hits,'first_hit_objects':dict(owners),'failures':fails,'metric_applicability':'Closed eye exposure is tested at full blink; intermediate poses retain required empty-hit observation and separate geometry audits'})
        for deg in sampling['jaw_degrees']:
            apply(objects,deg,0,0);bpy.context.view_layer.update();tree,names,fis,bp,vv,ff,culling=evaluate(objects,bpy.context.evaluated_depsgraph_get(),cfg['mouth_object']);rim=bp[front['rim_vertices']]
            for angle in sampling['mouth_views']:
                rad=math.radians(angle);forward=np.array([math.cos(rad),math.sin(rad),0]);right=np.array([-math.sin(rad),math.cos(rad),0]);up=np.array([0,0,1]);poly=hull(np.array([rim@right,rim@up]).T);center=poly.mean(axis=0);shrink=poly*sampling['mouth_inner_fraction']+center*(1-sampling['mouth_inner_fraction'])
                count=empty=bad=0;semantics=collections.Counter();failures=[]
                for u,z in domain(poly,*sampling['mouth_grid']):
                    origin=right*u+up*z+forward*.15;hit,n,fi,d,skipped_backfaces=rendered_hit(tree,vv,ff,culling,origin,-forward);count+=1;owner=names[fi] if fi is not None else 'EMPTY';part='EMPTY';dist=None
                    if hit is not None:
                        dist=float(np.linalg.norm(rim-np.array(hit),axis=1).min())
                        if owner==cfg['mouth_object'] and (fis[fi]>=mouth_data.get('cavity_faces_from',1000000000) or fis[fi] in lining_set):part='oral_lining'
                        elif owner in cfg['oral_objects']:part='tongue' if 'tongue' in owner else 'teeth'
                        elif owner==cfg['mouth_object'] and dist<=sampling['lip_occluder_distance']:part='retained_native_lip'
                        else:part='source_skin_or_other'
                        semantics[part]+=1
                    posterior=hit is None or hit.x<sampling['mouth_posterior_plane']
                    inner=all(np.cross(b-a,np.array([u,z])-a)>=-1e-12 for a,b in zip(shrink,np.roll(shrink,-1,axis=0)))
                    blocked=deg>0 and inner and part=='source_skin_or_other'
                    empty+=int(posterior);bad+=int(blocked)
                    if (posterior or blocked) and len(failures)<cfg['witness_limit']:failures.append({'sample':[u,z],'hit_object':owner,'hit':list(hit) if hit else None,'face':fis[fi] if fi is not None else None,'part':part,'rim_distance_m':dist,'posterior_or_empty':posterior,'unwanted_occluder':bool(blocked)})
                report['mouth'].append({'jaw_degrees':deg,'view_degrees':angle,'rays':count,'empty_or_posterior':empty,'unwanted_occluders':bad,'first_hit_semantics':dict(semantics),'failures':failures,'projected_front_entrance_hull':poly.tolist()})
        report['metrics']={'eye_exposed_or_empty':{'status':'observed','value':sum(r['empty']+r['exposed_when_closed'] for r in report['eyes']),'observations':sum(r['rays'] for r in report['eyes'])},'mouth_empty_or_posterior':{'status':'observed','value':sum(r['empty_or_posterior'] for r in report['mouth']),'observations':sum(r['rays'] for r in report['mouth'])},'mouth_unwanted_occluders':{'status':'observed','value':sum(r['unwanted_occluders'] for r in report['mouth']),'observations':sum(r['rays'] for r in report['mouth'])}}
        (root/(cfg['revision']+'-contract-probes.json')).write_text(json.dumps(report,indent=2));return report['metrics']
    finally:
        for name,vals in saved.items():
            for k,v in zip(bpy.data.objects[name].data.shape_keys.key_blocks,vals):k.value=v
        bpy.context.window.scene=saved_scene
