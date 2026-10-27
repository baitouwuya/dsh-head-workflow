// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(function(root){
  'use strict';
  // Pure geometry: no requests, asset changes, or generation.
  function plan(graph,options={}){
    if(!Array.isArray(graph?.nodes)||!Array.isArray(graph?.edges))throw Error('Auto-layout needs canvas nodes and edges.');
    const number=(key,fallback,min=0)=>{const v=options[key]??fallback;if(!Number.isFinite(v)||v<min)throw Error(key+' must be a finite number >= '+min+'.');return v;};
    const gapX=number('gapX',140,40),gapY=number('gapY',40,20),padding=64;
    const origin=options.origin??{x:0,y:0};if(!Number.isFinite(origin.x)||!Number.isFinite(origin.y))throw Error('origin needs finite x and y.');
    const nodes=new Map(),children=new Map([['',[]]]),warnings=[],cycles=[];
    for(const n of graph.nodes){if(!n.id||nodes.has(n.id))throw Error('Node IDs must be present and unique.');nodes.set(n.id,n);children.set(n.id,[]);}
    const cmp=(a,b)=>{const an=nodes.get(a),bn=nodes.get(b);return String(an?.displayNo||an?.name||a).localeCompare(String(bn?.displayNo||bn?.name||b),'en',{numeric:true})||a.localeCompare(b);};
    const parent=new Map();
    for(const n of nodes.values()){
      const p=n.pid||'';if(p&&!nodes.has(p))throw Error('Node '+n.id+' has a missing parent '+p+'.');
      parent.set(n.id,p);children.get(p).push(n.id);
    }
    for(const id of nodes.keys()){const seen=new Set();for(let p=id;p;p=parent.get(p)){if(seen.has(p))throw Error('Canvas contains a parent cycle at '+p+'.');seen.add(p);}}
    for(const list of children.values())list.sort(cmp);
    const edges=[];
    for(const e of graph.edges){const a=e.source?.nodeId,b=e.target?.nodeId;if(!nodes.has(a)||!nodes.has(b)){warnings.push('Ignored dangling edge '+e.id);continue;}edges.push([a,b]);}
    const dimensions=new Map(),positions=new Map(),sizes=new Map();
    for(const n of nodes.values()){
      const d=options.dimensions?.[n.id],s=n.ui?.size;
      const positive=(v,f)=>Number.isFinite(v)&&v>0?v:f;
      dimensions.set(n.id,{w:positive(d?.width,positive(s?.width,303)),h:positive(d?.height,positive(s?.height,303))});
    }
    function layout(ids,links){
      if(!ids.length)return {positions:new Map(),w:0,h:0};
      const adj=new Map(ids.map(id=>[id,new Set()])),rev=new Map(ids.map(id=>[id,new Set()]));
      for(const [a,b]of links){adj.get(a).add(b);rev.get(b).add(a);}
      // Iterative strongly connected components also handle cycles without hanging.
      const seen=new Set(),order=[];
      for(const id of ids){if(seen.has(id))continue;seen.add(id);const stack=[[id,[...adj.get(id)].sort(cmp),0]];
        while(stack.length){const f=stack.at(-1);if(f[2]<f[1].length){const next=f[1][f[2]++];if(!seen.has(next)){seen.add(next);stack.push([next,[...adj.get(next)].sort(cmp),0]);}}else{order.push(f[0]);stack.pop();}}
      }
      const components=[],owner=new Map();
      for(const id of order.reverse()){if(owner.has(id))continue;const c=[],stack=[id],index=components.length;owner.set(id,index);
        while(stack.length){const v=stack.pop();c.push(v);for(const u of rev.get(v))if(!owner.has(u)){owner.set(u,index);stack.push(u);}}
        c.sort(cmp);components.push(c);if(c.length>1||adj.get(c[0]).has(c[0]))cycles.push(c);
      }
      const out=components.map(()=>new Set()),incoming=components.map(()=>new Set());
      for(const [a,b]of links){const x=owner.get(a),y=owner.get(b);if(x!==y){out[x].add(y);incoming[y].add(x);}}
      const rank=components.map(()=>0),pending=incoming.map(s=>s.size),queue=[];
      for(let i=0;i<components.length;i++)if(!pending[i])queue.push(i);
      for(let i=0;i<queue.length;i++){const c=queue[i];for(const n of out[c]){rank[n]=Math.max(rank[n],rank[c]+1);if(!--pending[n])queue.push(n);}}
      // Keep unrelated lineages in separate vertical bands.
      const bands=[],visited=new Set();
      for(const id of ids){if(visited.has(id))continue;const band=[],stack=[id];visited.add(id);
        while(stack.length){const v=stack.pop();band.push(v);for(const u of [...adj.get(v),...rev.get(v)])if(!visited.has(u)){visited.add(u);stack.push(u);}}
        bands.push(band.sort(cmp));
      }
      bands.sort((a,b)=>cmp(a[0],b[0]));
      const result=new Map();let offsetY=0,maxWidth=0;
      for(const band of bands){
        const levels=[];for(const id of band)(levels[rank[owner.get(id)]]??=[]).push(id);
        const widths=levels.map(level=>Math.max(...level.map(id=>dimensions.get(id).w)));
        const heights=levels.map(level=>level.reduce((s,id)=>s+dimensions.get(id).h+40,0)+Math.max(0,level.length-1)*gapY);
        const fullHeight=Math.max(...heights);let x=0,minY=Infinity,maxY=-Infinity;
        for(let col=0;col<levels.length;col++){
          const desired=id=>{const ps=[...rev.get(id)].filter(p=>result.has(p));return ps.length?ps.reduce((sum,p)=>sum+result.get(p).y+(dimensions.get(p).h+40)/2,0)/ps.length-offsetY:fullHeight/2;};
          const level=levels[col].sort((a,b)=>desired(a)-desired(b)||cmp(a,b));
          const centers=level.map(desired);let y=centers.reduce((s,v)=>s+v,0)/level.length-heights[col]/2;
          for(const id of level){const d=dimensions.get(id);result.set(id,{x,y:y+offsetY});minY=Math.min(minY,y);maxY=Math.max(maxY,y+d.h+40);y+=d.h+40+gapY;}
          x+=widths[col]+gapX;
        }
        for(const id of band)result.get(id).y-=minY;
        maxWidth=Math.max(maxWidth,x-gapX);offsetY+=maxY-minY+120;
      }
      return {positions:result,w:maxWidth,h:Math.max(0,offsetY-120)};
    }
    function container(pid){
      const ids=children.get(pid);
      for(const id of ids){if(children.get(id).length){const inside=container(id);dimensions.set(id,{w:inside.w+2*padding,h:inside.h+2*padding});sizes.set(id,{width:inside.w+2*padding,height:inside.h+2*padding});}}
      const lift=id=>{let current=id;while(current&&parent.get(current)!==pid)current=parent.get(current);return current;};
      const projected=[];for(const [a,b]of edges){const x=lift(a),y=lift(b);if(x&&y&&(x!==y||(a===b&&x===a)))projected.push([x,y]);}
      const arranged=layout(ids,projected);let w=0,h=0;
      for(const [id,p]of arranged.positions){const shift=pid?{x:padding,y:padding}:origin;positions.set(id,{x:Math.round(p.x+shift.x),y:Math.round(p.y+shift.y)});const d=dimensions.get(id);w=Math.max(w,p.x+d.w);h=Math.max(h,p.y+d.h);}
      return {w:Math.ceil(w),h:Math.ceil(h)};
    }
    container('');
    const absolute=id=>{let p={...positions.get(id)};for(let up=parent.get(id);up;up=parent.get(up)){p.x+=positions.get(up).x;p.y+=positions.get(up).y;}return p;};
    const changes=[...nodes.keys()].sort(cmp).map(id=>({nodeId:id,position:positions.get(id),...(sizes.has(id)?{size:sizes.get(id)}:{})}));
    const inverse={changes:changes.map(c=>({nodeId:c.nodeId,position:nodes.get(c.nodeId).ui?.position??{x:0,y:0},...(sizes.has(c.nodeId)?{size:nodes.get(c.nodeId).ui?.size??null}:{})}))};
    const forward=edges.filter(([a,b])=>absolute(a).x+dimensions.get(a).w<=absolute(b).x).length;
    if(cycles.length)warnings.push('Cycles or section ordering conflicts are stacked in one column; those links cannot all point right.');
    if(forward<edges.length)warnings.push((edges.length-forward)+' connections are not left to right; retained hierarchy or cycles constrain their order.');
    return {changes,inverse,metrics:{nodes:nodes.size,edges:graph.edges.length,forwardEdges:forward,validEdges:edges.length,cycles:cycles.length},cycles,warnings};
  }
  const api={plan};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.__dshAutoLayout=api;
})(typeof window==='undefined'?globalThis:window);
