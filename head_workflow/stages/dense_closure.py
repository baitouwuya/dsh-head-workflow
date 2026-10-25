# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Reconstruction stage; invoked by the head workflow runner."""

def run(h):
    import bpy,json,numpy as np
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    
    h.controls({'blink':1});dg=bpy.context.evaluated_depsgraph_get();ts=[]
    for obj in [h.body,h.hair]+h.eyeballs+h.socket_rims:
     ev=obj.evaluated_get(dg);m=ev.to_mesh();ts.append((obj.name,BVHTree.FromPolygons([obj.matrix_world@v.co for v in m.vertices],[list(f.vertices) for f in m.polygons])));ev.to_mesh_clear()
    rows=[]
    for e in h.eyes:
     lo=e['polygon'].min(0);hi=e['polygon'].max(0);failed=[];count=0
     for y in np.linspace(lo[0],hi[0],121)[1:-1]:
      low,up=h.vertical_limits(e,y)
      for z in np.linspace(low,up,61)[1:-1]:
       hits=[]
       for name,tree in ts:
        p,n,fi,d=tree.ray_cast(Vector((.15,y,z)),Vector((-1,0,0)))
        if p is not None:hits.append((p.x,name))
       count+=1
       if not hits or max(hits)[1]==e['object_name']:failed.append([float(y),float(z)])
     rows.append({'eye':e['label'],'rays':count,'visible_globe_rays':len(failed),'failed_yz':failed})
    h.dense_closure=rows;(h.root/'dense-closure-audit.json').write_text(json.dumps(rows,indent=2));h.controls({})
