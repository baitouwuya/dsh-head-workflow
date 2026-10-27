// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

const assert=require('assert/strict'),fs=require('fs'),{plan}=require('../auto-layout.js');
const n=(id,pid='',w=303,h=303)=>({id,pid,type:pid==='section'?'NODE_TYPE_GENERATE_IMAGE':'NODE_TYPE_UPLOAD_CARD',displayNo:'#'+id,ui:{position:{x:999,y:999},size:{width:w,height:h}},params:{keep:id},nodeAssets:[{assetId:id}]});
const e=(a,b)=>({id:a+'-'+b,source:{nodeId:a},target:{nodeId:b}});
const tests=[];function check(name,fn){fn();tests.push(name);}
const plain=p=>JSON.parse(JSON.stringify(p));
function apply(g,p){const out=plain(g);for(const c of p.changes){const x=out.nodes.find(n=>n.id===c.nodeId);x.ui={...x.ui,position:c.position,...(c.size!==undefined?{size:c.size}:{})};}return out;}
function noSiblingOverlap(g,p){const next=apply(g,p);for(let i=0;i<next.nodes.length;i++)for(let j=i+1;j<next.nodes.length;j++){const a=next.nodes[i],b=next.nodes[j];if(a.pid!==b.pid)continue;const ap=a.ui.position,bp=b.ui.position,as=a.ui.size||{width:303,height:303},bs=b.ui.size||{width:303,height:303};assert(!(ap.x<bp.x+bs.width&&bp.x<ap.x+as.width&&ap.y<bp.y+bs.height&&bp.y<ap.y+as.height));}}
const g={nodes:['1','2','3','4','5','6'].map(x=>n(x)),edges:[e('1','2'),e('2','3'),e('2','4'),e('2','5'),e('1','4'),e('1','5'),e('5','6')]};
check('Branch workflow is forward, aligned by lineage and does not mutate input',()=>{const old=plain(g),p=plan(g);assert.equal(p.metrics.forwardEdges,7);noSiblingOverlap(g,p);assert.equal(p.changes.find(c=>c.nodeId==='5').position.y,p.changes.find(c=>c.nodeId==='6').position.y);assert.deepEqual(g,old);});
check('Idempotent positions and exact inverse',()=>{const p=plan(g),next=apply(g,p);assert.deepEqual(plan(next).changes,p.changes);assert.deepEqual(apply(next,p.inverse),g);});
check('Input array order does not change layout',()=>{assert.deepEqual(plan({nodes:[...g.nodes].reverse(),edges:[...g.edges].reverse()}).changes,plan(g).changes);});
check('Empty canvas and singleton',()=>{assert.equal(plan({nodes:[],edges:[]}).changes.length,0);assert.deepEqual(plan({nodes:[n('1')],edges:[]}).changes[0].position,{x:0,y:0});});
check('Cycle and self loop terminate and report constraints',()=>{const cyc={nodes:[n('1'),n('2'),n('3')],edges:[e('1','2'),e('2','1'),e('3','3')]},p=plan(cyc);assert.equal(p.metrics.cycles,2);assert(p.warnings.length);noSiblingOverlap(cyc,p);});
check('Disconnected lineages, joins, duplicate links and variable sizes',()=>{const graph={nodes:[n('1','',600,400),n('2'),n('3'),n('4'),n('5')],edges:[e('1','3'),e('2','3'),e('2','3'),e('4','5')]},p=plan(graph);assert.equal(p.metrics.forwardEdges,4);noSiblingOverlap(graph,p);});
check('Sections keep parent membership, fit children with 64px padding and restore size',()=>{const graph={nodes:[{...n('section'),type:'NODE_TYPE_SECTION'},n('1','section'),n('2','section'),n('3')],edges:[e('1','2'),e('2','3')]};const p=plan(graph),next=apply(graph,p);assert.equal(next.nodes[1].pid,'section');assert.equal(next.nodes[1].ui.position.x,64);assert.equal(next.nodes[1].ui.position.y,64);assert.deepEqual(apply(next,p.inverse),graph);noSiblingOverlap(graph,p);assert.equal(p.metrics.forwardEdges,2);});
check('Nested sections and invalid parent cycles',()=>{const graph={nodes:[n('a'),n('b','a'),n('c','b'),n('d')],edges:[e('c','d')]};assert.equal(plan(graph).metrics.forwardEdges,1);assert.throws(()=>plan({nodes:[n('a','b'),n('b','a')],edges:[]}),/parent cycle/);});
check('Malformed geometry and missing IDs produce readable errors',()=>{assert.throws(()=>plan(g,{gapX:NaN}),/gapX/);assert.throws(()=>plan(g,{origin:{x:Infinity,y:0}}),/origin/);assert.throws(()=>plan({nodes:[n('1'),n('1')],edges:[]}),/unique/);const p=plan({nodes:[n('1')],edges:[e('1','missing')]});assert(p.warnings.length);});
const source='<SHARE_ROOT>/runs/three-stage-1792775569327/source-graph.json';
if(fs.existsSync(source))check('Observed 63-node / 90-edge graph: non-geometry fields preserved and siblings separated',()=>{const graph=JSON.parse(fs.readFileSync(source));const p=plan(graph),next=apply(graph,p);assert.equal(p.changes.length,63);noSiblingOverlap(graph,p);for(let i=0;i<graph.nodes.length;i++){const {ui:a,...old}=graph.nodes[i],{ui:b,...updated}=next.nodes[i];assert.deepEqual(old,updated);}assert.deepEqual(next.edges,graph.edges);assert.deepEqual(plan(next).changes,p.changes);});
console.log(JSON.stringify({passed:tests.length,tests},null,2));
