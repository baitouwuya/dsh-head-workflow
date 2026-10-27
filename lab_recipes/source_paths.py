# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors
"""Source-edge skin routes between barycentrically attached anchors."""
import heapq
import numpy as np

class SkinEdgeGraph:
    def __init__(self,vertices,faces,canonical_ids):
        self.vertices=np.asarray(vertices,float);self.faces=np.asarray(faces,int);ids=np.asarray(canonical_ids,int);self.ids=ids
        self.position={int(i):p for i,p in zip(ids,self.vertices)};self.representative={int(i):k for k,i in enumerate(ids)};self.adj={int(i):{} for i in np.unique(ids[self.faces])}
        for face in ids[self.faces]:
            for a,b in zip(face,np.roll(face,-1)):
                a,b=int(a),int(b)
                if a==b:continue
                length=float(np.linalg.norm(self.position[a]-self.position[b]));self.adj[a][b]=min(length,self.adj[a].get(b,np.inf));self.adj[b][a]=min(length,self.adj[b].get(a,np.inf))
    def route(self,a,b,triangle_a,triangle_b,minimum_x=-np.inf):
        start=self.ids[np.asarray(triangle_a,int)];goal=self.ids[np.asarray(triangle_b,int)];cost={int(i):float(np.linalg.norm(a-self.position[int(i)])) for i in start};prev={int(i):None for i in start};heap=[(d,i) for i,d in cost.items()];heapq.heapify(heap);tails={int(i):float(np.linalg.norm(b-self.position[int(i)])) for i in goal};best=np.inf;end=None
        while heap:
            d,i=heapq.heappop(heap)
            if d!=cost[i]:continue
            if d>=best:break
            if i in tails and d+tails[i]<best:best=d+tails[i];end=i
            for k,w in self.adj[i].items():
                if self.position[k][0]<minimum_x:continue
                nd=d+w
                if nd<cost.get(k,np.inf):cost[k]=nd;prev[k]=i;heapq.heappush(heap,(nd,k))
        if end is None:raise ValueError('No source-surface route within the allowed frontal region')
        path=[]
        while end is not None:path.append(end);end=prev[end]
        path.reverse();return {'positions':np.vstack([a,[self.position[i] for i in path],b]),'source_vertex_indices':[self.representative[i] for i in path],'path_length':best}
