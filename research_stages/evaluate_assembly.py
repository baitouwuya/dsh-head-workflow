# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
import bpy,json,pathlib
from mathutils import Vector
from mathutils.bvhtree import BVHTree
def evaluate(report_filename,revision,base_source=None):
    root=pathlib.Path(bpy.app.driver_namespace['dsh_internal_research_root']);report=json.loads((root/report_filename).read_text());o=bpy.data.objects[report['object']]
    source_name=base_source or report.get('source_profile',report['profile'])['source'];src=bpy.data.objects[source_name];tree=BVHTree.FromPolygons([src.matrix_world@v.co for v in src.data.vertices],[list(f.vertices) for f in src.data.polygons],all_triangles=True);rim=[]
    for i in report['entrance_vertices']:
        x,y,z=o.data.vertices[i].co;hit,n,fi,d=tree.ray_cast(Vector((.1,y,z)),Vector((-1,0,0)))
        if hit is not None and abs(hit.x-x)<.00001:rim.append(i)
    if not rim:raise RuntimeError('No source-bound entrance')
    entry=revision+'-front-entrance.json';(root/entry).write_text(json.dumps({'classification':'INTERNAL_ONLY','object':o.name,'rim_vertices':rim,'source_before_cut':source_name,'maximum_source_match_m':.00001},indent=2))
    cfg=json.loads((root/'integrated004-contract-profile.json').read_text());cfg.update({'revision':revision,'scene':report['scene'],'mouth_object':report['object'],'mouth_report':report_filename,'entrance_report':entry})
    (root/(revision+'-contract-profile.json')).write_text(json.dumps(cfg,indent=2));ns={};exec((root/'scripts'/'contract_probes.py').read_text(),ns);profile=json.loads(pathlib.Path(r'<TRIPO_STUDIO_ROOT>\runs\head-refinement-1792921289985\routes\clean-head\canvas-sm-adapter-0.1.8\profile.json').read_text());return ns['run'](cfg,profile)
