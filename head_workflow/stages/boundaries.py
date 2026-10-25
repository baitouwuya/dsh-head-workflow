# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Reconstruction stage; invoked by the head workflow runner."""

def run(h):
    import bpy,numpy as np,collections,json
    
    h.boundaries={}
    for obj in [h.body,h.hair]:
     m=obj.data;p=np.array([v.co[:] for v in m.vertices]);canonical={};idx=[]
     for i,co in enumerate(p):idx.append(canonical.setdefault(tuple(np.round(co,7)),i))
     counts=collections.Counter()
     for f in m.polygons:
      vv=[idx[i] for i in f.vertices]
      for a,b in zip(vv,vv[1:]+vv[:1]):
       if a!=b:counts[tuple(sorted((a,b)))]+=1
     h.boundaries[obj.name]={}
     for reg in h.all_regions:
      poly=reg['polygon'];lo=poly.min(0)-1e-5;hi=poly.max(0)+1e-5;adj=collections.defaultdict(list)
      def dist(co):
       pt=co[1:3];return min(float(np.linalg.norm(pt-(a+np.clip(np.dot(pt-a,b-a)/np.dot(b-a,b-a),0,1)*(b-a)))) for a,b in zip(poly,np.roll(poly,-1,axis=0)))
      for (a,b),count in counts.items():
       if count!=1:continue
       if p[a,0]<.003 or p[b,0]<.003:continue
       if not(np.all(p[[a,b],1:3]>=lo) and np.all(p[[a,b],1:3]<=hi)):continue
       if dist(p[a])<2e-6 and dist(p[b])<2e-6:adj[a].append(b);adj[b].append(a)
      seen=set();parts=[]
      for start in adj:
       if start in seen:continue
       todo=[start];part=[];seen.add(start)
       while todo:
        i=todo.pop();part.append(i)
        for j in adj[i]:
         if j not in seen:seen.add(j);todo.append(j)
       parts.append({'ids':part,'cycle':all(len(adj[i])==2 for i in part),'mean_x':float(p[part,0].mean()),'x_range':[float(p[part,0].min()),float(p[part,0].max())],'adj':{str(i):adj[i] for i in part}})
      h.boundaries[obj.name][reg['label']]=parts
    print(json.dumps({k:{reg:[{a:b for a,b in p.items() if a not in ['ids','adj']}|{'vertices':len(p['ids'])} for p in pp] for reg,pp in v.items()} for k,v in h.boundaries.items()}))
    (h.root/'aperture-boundaries.json').write_text(json.dumps(h.boundaries,indent=2))
