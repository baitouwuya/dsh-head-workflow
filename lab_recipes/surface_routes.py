# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Continuous routes within source triangles, with explicit portal provenance."""
import numpy as np,heapq
from collections import defaultdict

def segment_closest_parameter(a,b,c,d):
    # Closest point on CD to segment AB; convex scalar minimization handles parallelism.
    u=b-a;v=d-c;uu=float(u@u)
    def dist(t):
        p=c+t*v;s=np.clip(((p-a)@u)/uu,0,1) if uu>0 else 0;return float(np.sum((p-a-s*u)**2))
    lo,hi=0.,1.
    for _ in range(32):
        t1=(2*lo+hi)/3;t2=(lo+2*hi)/3
        if dist(t1)<dist(t2):hi=t2
        else:lo=t1
    choices=[0.,1.,(lo+hi)/2];return min(choices,key=dist)

class SkinTriangleGraph:
    def __init__(self,vertices,faces,canonical_ids):
        self.v=np.asarray(vertices,float);self.f=np.asarray(faces,int);self.ids=np.asarray(canonical_ids,int);self.centers=self.v[self.f].mean(1);edges=defaultdict(list);verts=defaultdict(list);self.adj=defaultdict(list)
        for i,face in enumerate(self.f):
            for vertex in face:verts[int(self.ids[vertex])].append((i,int(vertex)))
            for a,b in zip(face,np.roll(face,-1)):edges[tuple(sorted((int(self.ids[a]),int(self.ids[b]))))].append((i,int(a),int(b)))
        for owners in edges.values():
            for i,a,b in owners:
                for j,_,_ in owners:
                    if i!=j:self.adj[i].append((j,a,b,float(np.linalg.norm(self.centers[i]-self.centers[j]))))
        for owners in verts.values():
            for i,a in owners:
                known={j for j,*_ in self.adj[i]}
                for j,_ in owners:
                    if i!=j and j not in known:self.adj[i].append((j,a,a,float(np.linalg.norm(self.centers[i]-self.centers[j]))))
    def route(self,a,b,start,end,padding=.03):
        if start==end:return {'positions':np.array([a,b]),'faces':[start],'portals':[]}
        direction=b-a;dd=float(direction@direction);t=np.clip(((self.centers-a)@direction)/dd,0,1) if dd>0 else np.zeros(len(self.centers));distance=np.linalg.norm(self.centers-a-t[:,None]*direction,axis=1);allowed=distance<=padding;allowed[[start,end]]=True
        cost={int(start):0.};prev={int(start):None};portal={};heap=[(0.,int(start))]
        while heap:
            dist,i=heapq.heappop(heap)
            if dist!=cost[i]:continue
            if i==end:break
            for j,u,v,length in self.adj[i]:
                if not allowed[j]:continue
                nd=dist+length*(1+distance[j]/max(np.linalg.norm(direction),.001))
                if nd<cost.get(j,np.inf):cost[j]=nd;prev[j]=i;portal[j]=(u,v);heapq.heappush(heap,(nd,j))
        if end not in prev:raise ValueError('No local connected source-skin triangle corridor')
        fs=[];i=end
        while i is not None:fs.append(i);i=prev[i]
        fs.reverse();ps=[a];ports=[]
        for j in fs[1:]:
            u,v=portal[j];frac=segment_closest_parameter(a,b,self.v[u],self.v[v]);ps.append(self.v[u]*(1-frac)+self.v[v]*frac);ports.append({'source_vertices':[u,v],'fraction':frac,'incoming_face':prev[j],'outgoing_face':j})
        ps.append(b);return {'positions':np.asarray(ps),'faces':fs,'portals':ports}
