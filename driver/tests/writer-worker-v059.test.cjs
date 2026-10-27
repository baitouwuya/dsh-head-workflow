// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('shipped worker forwards health, artifacts and legacy evidence from the installed bridge envelope',async()=>{
 let listener;const calls=[];const id='a'.repeat(32);
 vm.runInNewContext(fs.readFileSync(require.resolve('../writer-worker.js'),'utf8'),{chrome:{runtime:{id,onMessage:{addListener:f=>listener=f}}},fetch:async(url,options)=>{calls.push({url,options});return {json:async()=>({ok:true})};}});
 for(const area of ['health','artifacts','runs','out']){
  const result=await new Promise(resolve=>listener({type:'dsh-write',payload:{area}},{id,url:'https://studio.tripo3d.ai/projects/test'},resolve));assert.equal(result.ok,true);
  assert.equal(calls.at(-1).url,'http://127.0.0.1:43127/'+(area==='health'?'health':'write'));
 }
 const refused=await new Promise(resolve=>listener({type:'dsh-write',payload:{area:'invalid'}},{id,url:'https://studio.tripo3d.ai/projects/test'},resolve));assert.equal(refused.error,'Writer envelope refused');assert.equal(calls.length,4);
});
