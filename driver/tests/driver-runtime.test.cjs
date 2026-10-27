// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),C=require('../driver-core');
const source=fs.readFileSync(require.resolve('../driver.js'),'utf8');
const registry=[{projectId:'01a15fa4-5cb7-7992-9bd7-803d6159d6f2',canvasId:'01a15fa4-5cb7-7998-b05c-b2d2eff1fa4d',name:'dsh-test'}];
const results=[];
function harness(){
  const ctx={MutationObserver:class{observe(){}},window:{__dshDriverCore:C,__dshTripoSanitize:{},__dshOwnedCanvases:registry},document:{readyState:'loading',addEventListener(){}},setTimeout,clearTimeout,Map,Set,URL,performance,Date,sessionStorage:{getItem(){return null;}},indexedDB:{open(){return {};}}};
  // Test-only exposure: execute the production closures; no hook ships in the extension.
  const marker=source.lastIndexOf('})();');
  vm.runInNewContext(source.slice(0,marker)+`window.test={execute,serverStop,setup(value,req){job=value;workRoot=true;request=req;balance=async()=>100;stateCapture=async()=>{};checkpoint=async()=>{};},trace:()=>trace};`+source.slice(marker),ctx);
  return ctx.window.test;
}
async function test(name,f){await f();results.push({name,status:'passed'});}
(async()=>{
 await test('Actual execute refuses zero-cap image before any request, even explicit opt-in',async()=>{const h=harness();let requests=0;h.setup(null,async()=>{requests++;});await assert.rejects(h.execute({version:1,...registry[0],maxCredits:0,steps:[{id:'image',kind:'prompt',costClass:'image',text:'cube',allowZeroEstimateSubmit:true}]}),/Zero credit cap/);assert.equal(requests,0);});
 await test('Actual execute refuses missing zero-estimate allowance before any request',async()=>{const h=harness();let requests=0;h.setup(null,async()=>{requests++;});await assert.rejects(h.execute({version:1,...registry[0],maxCredits:1,steps:[{id:'image',kind:'prompt',costClass:'image',text:'cube'}]}),/explicit allowance/);assert.equal(requests,0);});
 await test('Actual serverStop retains run before cancel removes it and sends both mutations',async()=>{const h=harness(),calls=[];const step={id:'x',status:'running',turnId:'turn',balanceBefore:100,startedMs:Date.now()};const job={plan:registry[0],steps:[step],balanceBefore:100};h.setup(job,async(op)=>{calls.push(op);if(op==='RunService/ListCanvasRuns')return {runs:[{runId:'run',turnId:'turn',canvasId:registry[0].canvasId}]};if(op==='RunService/GetRun')return{run:{status:'RUN_STATUS_STOPPED',steps:[{status:'RUN_STEP_STATUS_ABORTED'}]}};return{};});await h.serverStop('observed debit exceeds maxCredits');assert.deepEqual(calls,['RunService/ListCanvasRuns','TurnService/CancelTurn','RunService/StopRun','RunService/GetRun']);assert.equal(step.status,'stopped');assert.equal(step.creditDelta,0);assert(h.trace().some(e=>e.kind==='stop.terminal'));});
 await test('Actual serverStop still sends StopRun when CancelTurn fails',async()=>{const h=harness(),calls=[];h.setup({plan:registry[0],steps:[{status:'running',turnId:'turn',runId:'run',balanceBefore:100,startedMs:Date.now()}],balanceBefore:100},async(op)=>{calls.push(op);if(op==='TurnService/CancelTurn')throw Error('Network HTTP 500');if(op==='RunService/GetRun')return{run:{status:'RUN_STATUS_STOPPED'}};return{};});await h.serverStop('breach');assert(calls.includes('RunService/StopRun'));});
 await test('Concurrent stop calls share one cancellation sequence',async()=>{const h=harness(),calls=[];h.setup({plan:registry[0],steps:[{status:'running',turnId:'turn',runId:'run',balanceBefore:100,startedMs:Date.now()}],balanceBefore:100},async(op)=>{calls.push(op);return{run:{status:'RUN_STATUS_STOPPED'}};});await Promise.all([h.serverStop('a'),h.serverStop('b')]);assert.equal(calls.filter(x=>x==='TurnService/CancelTurn').length,1);assert.equal(calls.filter(x=>x==='RunService/StopRun').length,1);});
 console.log(JSON.stringify({suite:'production driver closures with mocked I/O',passed:results.length,tests:results,liveTraffic:false},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
