# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,json,pathlib
from mathutils import Vector
from mathutils.bvhtree import BVHTree
def evaluate(revision):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);report=json.loads((root/(revision+'-boolean-mouth.json')).read_text());o=bpy.data.objects[report['object']]
    src=bpy.data.objects[report['profile']['source']];v=[src.matrix_world@x.co for x in src.data.vertices];tree=BVHTree.FromPolygons(v,[list(f.vertices) for f in src.data.polygons],all_triangles=True);rim=[]
    for i in report['entrance_vertices']:
        x,y,z=o.matrix_world@o.data.vertices[i].co;hit,n,fi,d=tree.ray_cast(Vector((.1,y,z)),Vector((-1,0,0)))
        if hit is not None and abs(hit.x-x)<.00001:rim.append(i)
    if not rim:raise RuntimeError('No source-bound outer entrance')
    prefix=revision.replace('-','')
    (root/(prefix+'-front-entrance.json')).write_text(json.dumps({'classification':'INTERNAL_ONLY','object':o.name,'rim_vertices':rim,'rule':'Actual source/lining intersection at source first-hit outer facial surface within10microns'},indent=2))
    cfg=json.loads((root/'integrated004-contract-profile.json').read_text());cfg.update({'revision':prefix,'scene':report['scene'],'mouth_object':report['object'],'mouth_report':revision+'-boolean-mouth.json','entrance_report':prefix+'-front-entrance.json'})
    (root/(prefix+'-contract-profile.json')).write_text(json.dumps(cfg,indent=2));ns={};exec((root/'scripts'/'contract_probes.py').read_text(),ns)
    profile=json.loads(pathlib.Path(r'<TRIPO_STUDIO_ROOT>\runs\head-refinement-1792921289985\routes\clean-head\canvas-sm-adapter-0.1.8\profile.json').read_text())
    return ns['run'](cfg,profile)
