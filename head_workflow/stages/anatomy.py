# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Reconstruction stage; invoked by the head workflow runner."""

def run(h):
    import bpy,json,numpy as np,collections,math
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    
    h.visibility_tests=[]
    def trees(objects):
     dg=bpy.context.evaluated_depsgraph_get();out=[]
     for obj in objects:
      ev=obj.evaluated_get(dg);mesh=ev.to_mesh();vs=[obj.matrix_world@v.co for v in mesh.vertices];fs=[list(f.vertices) for f in mesh.polygons];out.append((obj.name,BVHTree.FromPolygons(vs,fs)));ev.to_mesh_clear()
     return out
    for weight in [0,.5,1]:
     h.controls({'blinkLeft':weight,'blinkRight':weight});ts=trees([h.body,h.hair]+h.eyeballs+h.socket_rims)
     for e in h.eyes:
      poly=e['polygon'];lo=poly.min(0);hi=poly.max(0);total=exposed=0
      for y in np.linspace(lo[0],hi[0],31)[1:-1]:
       lim=h.vertical_limits(e,y)
       if not lim:continue
       for z in np.linspace(lim[0],lim[1],17)[1:-1]:
        hits=[]
        for name,tree in ts:
         p,n,fi,d=tree.ray_cast(Vector((.15,y,z)),Vector((-1,0,0)))
         if p is not None:hits.append((p.x,name))
        if hits:
         total+=1;exposed+=max(hits)[1]==e['object_name']
      h.visibility_tests.append({'eye':e['label'],'blink_weight':weight,'rays':total,'visible_globe_rays':exposed})
    h.controls({'jawOpen':1});ts=trees([h.body,h.hair]+h.mouth_parts);leaks=[];total=0
    cy=sum(h.lip['y_range'])/2;cz=float(np.polyval(h.lip['fit_z_of_y_coefficients'],cy))
    for y in np.linspace(cy-.0035,cy+.0035,31):
     for z in np.linspace(cz-.006,cz+.0005,25):
      hits=[]
      for name,tree in ts:
       p,n,fi,d=tree.ray_cast(Vector((.15,y,z)),Vector((-1,0,0)))
       if p is not None:hits.append((p.x,name))
      total+=1
      if not hits or max(hits)[0]<0:leaks.append([float(y),float(z)])
    closed=[]
    for obj in h.eyeballs:
     count=collections.Counter(tuple(sorted((int(a),int(b)))) for f in obj.data.polygons for a,b in zip(f.vertices,list(f.vertices)[1:]+[f.vertices[0]]));closed.append({'object':obj.name,'vertices':len(obj.data.vertices),'boundary_edges':sum(n==1 for n in count.values()),'nonmanifold_edges':sum(n!=2 for n in count.values())})
    h.controls({});audit={'eye_visibility':h.visibility_tests,'closed_eyeballs':closed,'mouth_probe':{'rays':total,'back_head_or_empty_rays':len(leaks),'failed_yz':leaks},'note':'Frontal probe within original apertures; not a proof of all-view collision freedom.'}
    (h.root/'anatomy-occlusion-audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps(audit))
