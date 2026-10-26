# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,pathlib,json,numpy as np,collections,math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
def initialize(cfg):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);src=bpy.data.objects[cfg['source']];m=src.data
    base=np.array([list(v.co) for v in m.shape_keys.key_blocks['Basis'].data]);f=np.array([list(p.vertices) for p in m.polygons])
    reference=bpy.data.objects[cfg['source_before_cut']];tree=BVHTree.FromPolygons([reference.matrix_world@v.co for v in reference.data.vertices],[list(p.vertices) for p in reference.data.polygons],all_triangles=True)
    edges=collections.defaultdict(list)
    for i,tri in enumerate(f):
        for a,b in zip(tri,np.roll(tri,-1)):edges[tuple(sorted((int(a),int(b))))].append(i)
    seam={i for e,uses in edges.items() if len(uses)==2 and len({m.polygons[j].material_index for j in uses})==2 for i in e};rim=[]
    for i in seam:
        x,y,z=base[i];hit,n,fi,d=tree.ray_cast(Vector((.1,y,z)),Vector((-1,0,0)))
        if hit is not None and abs(hit.x-x)<.00001:rim.append(i)
    cy,cz=cfg['center_yz'];mov=(base[:,0]>-.012)&(abs(base[:,1]-cy)<.018)&(abs(base[:,2]-cz)<.016)
    if cfg['pin_rim']:mov[rim]=False
    caps=np.where(base[:,0]>.005,cfg['skin_cap_m'],cfg['interior_cap_m'])
    ns={};exec((root/'scripts'/cfg.get('optimizer_script','joint_dihedral.py')).read_text(),ns)
    out,r=ns['optimize'](base,f,mov,caps,cfg['optimizer'])
    r.update({'classification':'INTERNAL_ONLY','profile':cfg,'rim_vertices':rim,'source':src.name})
    (root/(cfg['revision']+'-neutral-optimization.json')).write_text(json.dumps(r,indent=2))
    np.savez_compressed(root/(cfg['revision']+'-pose-state.npz'),original=base,neutral=out,triangles=f,movable=mov,caps=caps,rim=np.array(rim,int))
    (root/(cfg['revision']+'-profile.json')).write_text(json.dumps(cfg,indent=2));return r
def pose(revision,degrees):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);cfg=json.loads((root/(revision+'-profile.json')).read_text());data=np.load(root/(revision+'-pose-state.npz'));base=data['neutral'];f=data['triangles'];cy,cz=cfg['center_yz'];w=cfg['mouth_half_width'];h=cfg['mouth_half_height'];smooth=lambda t:np.clip(t,0,1)**2*(3-2*np.clip(t,0,1))
    u=(base[:,1]-cy)/w;side=smooth((abs(base[:,1]-cy)-w*.75)/(w*.5));band=np.maximum(h*np.sqrt(np.maximum(0,1-u*u)),.00002)+.003*side
    weight=smooth((cz+band-base[:,2])/(2*band))*(1-smooth((abs(base[:,1]-cy)-.02)/.02))*smooth((base[:,2]-.84)/.015)*smooth((base[:,0]+.015)/.02)
    pivot=np.array(cfg['jaw_pivot']);a=np.radians(degrees);rel=base-pivot;rot=rel.copy();rot[:,0]=np.cos(a)*rel[:,0]+np.sin(a)*rel[:,2];rot[:,2]=-np.sin(a)*rel[:,0]+np.cos(a)*rel[:,2];raw=base+(rot+pivot-base)*weight[:,None]
    ns={};exec((root/'scripts'/'joint_dihedral.py').read_text(),ns);out,r=ns['optimize'](raw,f,data['movable'],data['caps'],cfg['optimizer'],reference_vertices=base)
    r.update({'classification':'INTERNAL_ONLY','degrees':degrees,'profile':cfg,'reference':'Optimized neutral mesh','jaw_influence':'Anterior-weighted rotation; posterior skull stays fixed'})
    np.savez_compressed(root/(revision+'-pose-'+str(degrees)+'.npz'),raw=raw,positions=out);(root/(revision+'-pose-'+str(degrees)+'.json')).write_text(json.dumps(r,indent=2));return r
