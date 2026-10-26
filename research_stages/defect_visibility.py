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

import bpy,json,pathlib,collections,math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def classify(scene_name, output_name, cfg):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root'])
    skin=bpy.data.objects[cfg['skin_object']];m=skin.data
    ids=[a.value for a in m.attributes['native_SM_vertex_id'].data]
    sv=np.array([list(skin.matrix_world@v.co) for v in m.vertices]);sf=[list(p.vertices) for p in m.polygons]
    edges=collections.defaultdict(list);native_pos={}
    for i,k in enumerate(ids):native_pos[k]=sv[i]
    for fi,f in enumerate(sf):
        for a,b in zip(f,f[1:]+f[:1]):edges[tuple(sorted((ids[a],ids[b])))].append(fi)
    folds=json.loads((root/'SM-native-folds.json').read_text())
    if cfg.get('dynamic_fold_measurement'):
        triangles=sv[np.array(sf)];norm=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]);norm/=np.maximum(np.linalg.norm(norm,axis=1)[:,None],1e-30);folds=[]
        for edge,fs in edges.items():
            if len(fs)==2:
                angle=float(np.degrees(np.arccos(np.clip(norm[fs[0]]@norm[fs[1]],-1,1))))
                if angle>90:folds.append({'edge':edge,'faces':fs,'angle':angle})
    defects=[]
    for edge,faces in edges.items():
        if len(faces)==1:defects.append({'kind':'boundary','edge':edge,'faces':faces})
    for item in folds:defects.append({'kind':'fold','edge':item['edge'],'faces':item['faces'],'angle':item['angle']})
    for d in defects:
        a,b=[native_pos[k] for k in d['edge']];points=[];point_faces=[]
        for fi in d['faces']:
            c=sv[sf[fi]].mean(axis=0);points.append(c);point_faces.append(fi)
            points.extend([.95*(a*(1-t)+b*t)+.05*c for t in cfg['edge_parameters']]);point_faces.extend([fi]*len(cfg['edge_parameters']))
        d['points']=points;d['point_faces']=point_faces
    dirs=[]
    for i in range(cfg['directions']):
        z=1-2*(i+.5)/cfg['directions'];phi=i*math.pi*(3-math.sqrt(5));r=math.sqrt(1-z*z);dirs.append((r*math.cos(phi),r*math.sin(phi),z))
    dirs.extend([(x,y,z) for x in [-1,0,1] for y in [-1,0,1] for z in [-1,0,1] if x*x+y*y+z*z])
    dirs=np.array(dirs);dirs/=np.linalg.norm(dirs,axis=1)[:,None]
    objects=[o for o in bpy.data.scenes[scene_name].objects if o.type=='MESH'];saved={o.name:[k.value for k in o.data.shape_keys.key_blocks] for o in objects if o.data.shape_keys}
    maxpoints=max(len(d['points']) for d in defects)
    blockers=np.full((len(cfg['jaw_samples']),len(defects),maxpoints,len(dirs)),-2,dtype=np.int16)
    distances=np.full(blockers.shape,np.nan,dtype=np.float32)
    source_scene=bpy.context.window.scene
    try:
        bpy.context.window.scene=bpy.data.scenes[scene_name]
        for pi,jaw in enumerate(cfg['jaw_samples']):
            for o in objects:
                if o.data.shape_keys:
                    for k in o.data.shape_keys.key_blocks:
                        if k.name!='Basis':k.value=jaw if k.name=='jawOpen' else 0
            bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get()
            vv=[];ff=[];owners=[];culling=[]
            for oi,o in enumerate(objects):
                ev=o.evaluated_get(dg);em=ev.to_mesh();em.calc_loop_triangles();offset=len(vv)
                vv.extend([o.matrix_world@v.co for v in em.vertices])
                ff.extend([tuple(offset+i for i in t.vertices) for t in em.loop_triangles]);owners.extend([oi]*len(em.loop_triangles));culling.extend([bool(em.materials[em.polygons[t.polygon_index].material_index].use_backface_culling) for t in em.loop_triangles]);ev.to_mesh_clear()
            tree=BVHTree.FromPolygons(vv,ff,all_triangles=True)
            for di,d in enumerate(defects):
                for ti,target in enumerate(d['points']):
                    for vi,direction in enumerate(dirs):
                        fi=d['point_faces'][ti];pts=sv[sf[fi]];normal=np.cross(pts[1]-pts[0],pts[2]-pts[0]);mat=skin.data.materials[skin.data.polygons[fi].material_index]
                        if mat.use_backface_culling and normal@direction<=0:
                            blockers[pi,di,ti,vi]=-4;continue
                        origin=Vector(target+direction*cfg['ray_distance_m'])
                        hit,n,face,dist,skip_count=rendered_hit(tree,vv,ff,culling,origin,-direction,cfg['ray_distance_m']+cfg['tolerance_m'])
                        if face is None:
                            blockers[pi,di,ti,vi]=-3;distances[pi,di,ti,vi]=0
                        else:
                            clearance=cfg['ray_distance_m']-dist
                            distances[pi,di,ti,vi]=clearance
                            blockers[pi,di,ti,vi]=owners[face] if clearance>cfg['tolerance_m'] else (-1 if abs(clearance)<=cfg['tolerance_m'] else -3)
        rows=[]
        for di,d in enumerate(defects):
            valid=blockers[:,di,:len(d['points']),:];loc=np.argwhere(valid==-1);counts=collections.Counter(int(a) for a in valid.ravel() if a>=0)
            row={k:v for k,v in d.items() if k!='points'}
            row.update({'classification':'reachable' if len(loc) else ('indeterminate' if (valid==-3).any() else 'hidden_in_sampled_views'),'ray_observations':int((valid!=-4).sum()),'target_backface_culled_views':int((valid==-4).sum()),'indeterminate_observations':int((valid==-3).sum()),'unoccluded_observations':len(loc),'occluders':{objects[i].name:n for i,n in counts.items()}})
            if len(loc):
                pi,ti,vi=map(int,loc[0]);row['witness']={'jaw':cfg['jaw_samples'][pi],'point':d['points'][ti].tolist(),'view_direction':dirs[vi].tolist(),'clearance_m':float(distances[pi,di,ti,vi])}
            else:row['minimum_occlusion_clearance_m']=float(np.nanmin(distances[:,di,:len(d['points']),:]))
            rows.append(row)
        result={'classification':'INTERNAL_ONLY','status':'PRE_INTEGRATION_VISIBILITY_BASELINE','coverage_limit':'Current jaw poses only. Blink and final integrated poses must be rerun before hidden exemptions are final. Finite recorded directions and surface samples, not a proof for all continuous views.','profile':cfg,'object_index':[o.name for o in objects],'defects':rows}
        result['counts']={kind:{cl:sum(d['kind']==kind and d['classification']==cl for d in rows) for cl in ['reachable','hidden_in_sampled_views','indeterminate']} for kind in ['boundary','fold']}
        (root/(output_name+'.json')).write_text(json.dumps(result,indent=2))
        np.savez_compressed(root/(output_name+'-rays.npz'),blocker_indices=blockers,clearances_m=distances,directions=dirs)
        return result['counts']
    finally:
        for name,values in saved.items():
            for k,val in zip(bpy.data.objects[name].data.shape_keys.key_blocks,values):k.value=val
        bpy.context.window.scene=source_scene
