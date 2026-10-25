# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Reconstruction stage; invoked by the head workflow runner."""

def run(h):
    import numpy as np,json,collections
    
    m=h.src_hair.data;p=np.array([v.co[:] for v in m.vertices]);canonical={};idx=[]
    for i,co in enumerate(p):idx.append(canonical.setdefault(tuple(np.round(co,7)),i))
    adj=collections.defaultdict(set)
    for e in m.edges:
     a,b=[idx[x] for x in e.vertices];adj[a].add(b);adj[b].add(a)
    seen=set();comps=[];vcomp={}
    for start in adj:
     if start in seen:continue
     todo=[start];seen.add(start);ids=[]
     while todo:
      i=todo.pop();ids.append(i)
      for j in adj[i]:
       if j not in seen:seen.add(j);todo.append(j)
     cid=len(comps);comps.append(ids)
     for i in ids:vcomp[i]=cid
    h.hair_components=comps;h.hair_component_indices=np.array([vcomp.get(i,-1) for i in idx])
    h.source_hair_editable=np.isin(h.hair_component_indices,h.config["editable_eye_components"])
