// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

const test=require('node:test'),assert=require('node:assert/strict'),U=require('../ui-actions');
function setup(){
 const h={selected:true,open:true,clicks:0,finals:0,armed:0,disposed:0,optionsOpen:false};
 class E{constructor(type,opts){Object.assign(this,{type},opts);}}
 const input={value:'head',dispatchEvent(){}};
 const combos=[{textContent:'FBX',click(){h.clicks++;h.optionsOpen=true;h.slot=0;}},{textContent:'2kCurrent',click(){h.clicks++;h.optionsOpen=true;h.slot=1;}}];
 const switches=[{parentElement:{textContent:'Export Skeleton'},getAttribute:n=>n==='aria-checked'?(h.skeleton===false?'false':'true'):null,click(){h.clicks++;h.skeleton=h.skeleton===false;}}];
 const final={textContent:'Export',disabled:false,click(){h.clicks++;h.finals++;h.resolve({completed:true,path:'out/head.glb',bytes:100,sha256:'hash'});}};
 const d={textContent:'Export File Name Format FBX',getAttribute:()=> 'Export',querySelector:s=>s==='input'?input:null,querySelectorAll:s=>s==='[role="combobox"]'?combos:s==='[role="switch"]'?switches:s==='button'?[final]:[],dispatchEvent:e=>{if(e.key==='Escape')h.open=false;}};
 const title={textContent:'#1 Lab',click(){h.selected=true;h.clicks++;}};
 const node={getAttribute:()=> 'node',classList:{contains:()=>h.selected},querySelector:s=>s==='h3'?title:s==='.forge3d-lab-node-state'?{}:null};
 const document={defaultView:{Event:E,KeyboardEvent:E},querySelector:s=>s==='[role="dialog"][aria-label="Export"]'&&h.open?d:null,querySelectorAll:s=>s==='.vue-flow__node[data-id]'?[node]:s==='[role="listbox"] [role="option"]'&&h.optionsOpen?(h.slot===0?['FBX','GLB','OBJ']:['2k','4k','8k']).map(v=>({textContent:v,click(){h.clicks++;combos[h.slot].textContent=v;h.optionsOpen=false;}})):[]};
 const location={origin:'https://studio.tripo3d.ai',pathname:'/projects/p'};
 const downloads={arm(){h.armed++;return {promise:new Promise((resolve,reject)=>{h.resolve=resolve;h.reject=reject;}),dispose(){h.disposed++;}};}};
 h.ui=U.create({document,location,downloads});h.input=input;h.combos=combos;h.location=location;h.final=final;return h;
}
test('labExport dry-run and old labExportDialog never press final Export',async()=>{const h=setup();const p=await h.ui.run('labExport',{nodeId:'node',format:'GLB',textureResolution:'8k'});assert.equal(p.exportSubmitted,false);assert.equal(h.clicks,0);const old=await h.ui.run('labExportDialog',{nodeId:'node',operation:'read',dryRun:false});assert.equal(old.exportSubmitted,false);assert.equal(h.finals,0);});
test('format, resolution, filename and skeleton are applied; final Export pressed exactly once and receipt awaited',async()=>{const h=setup();const r=await h.ui.run('labExport',{nodeId:'node',format:'GLB',textureResolution:'8k',filename:'new-head',exportSkeleton:false,dryRun:false});assert.equal(h.combos[0].textContent,'GLB');assert.equal(h.combos[1].textContent,'8k');assert.equal(h.input.value,'new-head');assert.equal(h.skeleton,false);assert.equal(h.finals,1);assert.equal(h.armed,1);assert.equal(h.disposed,1);assert.equal(r.download.completed,true);assert.equal(r.converted,true);});
test('omitted export options preserve native dialog defaults',async()=>{const h=setup();const r=await h.ui.run('labExport',{nodeId:'node',dryRun:false});assert.equal(r.options.format,'FBX');assert.equal(r.options.textureResolution,'2k');assert.equal(h.input.value,'head');assert.equal(h.finals,1);});
test('unsupported format/resolution and wrong dialog owner fail without clicking',async()=>{const h=setup();for(const a of [{format:'EXE'},{textureResolution:'64k'},{filename:'../bad'}])await assert.rejects(h.ui.run('labExport',{nodeId:'node',...a,dryRun:false}));h.selected=false;await assert.rejects(h.ui.run('labExport',{nodeId:'node',dryRun:false}),/Another node/);assert.equal(h.clicks,0);});
test('failed download reports submitted-once and always removes capture',async()=>{const h=setup();h.final.click=()=>{h.finals++;h.reject(Error('transfer failed'));};await assert.rejects(h.ui.run('labExport',{nodeId:'node',dryRun:false}),/Export was pressed once/);assert.equal(h.finals,1);assert.equal(h.disposed,1);});
test('STOP before dispatch sends no UI event',async()=>{const h=setup(),c=new AbortController();c.abort();await assert.rejects(h.ui.run('labExport',{nodeId:'node',dryRun:false},c.signal),/Stopped/);assert.equal(h.finals,0);assert.equal(h.armed,0);});
test('export may close its dialog while the verified download completes',async()=>{const h=setup();const original=h.final.click;h.final.click=()=>{original();h.open=false;};const r=await h.ui.run('labExport',{nodeId:'node',dryRun:false});assert.equal(r.download.completed,true);assert.equal(r.options.format,'FBX');});
