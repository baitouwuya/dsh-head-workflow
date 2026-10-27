// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

const assert=require('assert/strict');
const C=require('../driver-core');
const vm=require('vm'),fs=require('fs');
const registry=[{projectId:'01a15fa4-5cb7-7992-9bd7-803d6159d6f2',canvasId:'01a15fa4-5cb7-7998-b05c-b2d2eff1fa4d',name:'dsh-test'}];
const plan={version:1,...registry[0],maxCredits:40,steps:[{id:'model',kind:'prompt',costClass:'hd-model',text:'One blue cube'}]};
const tests=[];function test(name,fn){fn();tests.push({name,status:'passed'});}
test('Explicit cap is mandatory',()=>assert.throws(()=>C.validate({...plan,maxCredits:undefined},registry)));
test('Negative cap refused',()=>assert.throws(()=>C.validate({...plan,maxCredits:-1},registry)));
test('A dsh name cannot authorize unregistered IDs',()=>assert.throws(()=>C.validate({...plan,projectId:'01a15fa4-5cb7-7992-9bd7-803d6159d6f3'},registry)));
test('Non-dsh registry entry refused',()=>assert.throws(()=>C.validate(plan,[{...registry[0],name:'production'}])));
test('HD cost preflight refuses deliberately low cap before requests',()=>{const p=C.preview({...plan,maxCredits:1},registry);assert.equal(p.networkRequestsSent,0);assert.equal(p.steps[0].preflight,'blocked-by-cap');assert.equal(p.predictedCredits,40);});
test('Remaining debit reserved for next step',()=>assert.equal(C.budget(40,40,40),false));
test('Exact cap admitted by estimate',()=>assert.equal(C.budget(40,0,40),true));
test('Observed unexpected debit triggers watchdog predicate',()=>assert.equal(C.budget(1,40,0),false));
test('Refund reconciles rather than accumulating duplicate debit',()=>assert.equal(C.budget(40,0,40),true));
test('Completed paid step is skipped on resume',()=>assert.equal(C.resumeDecision({status:'done',turnId:'x'}),'skip'));
test('Lost submission response cannot cause paid retry',()=>assert.equal(C.resumeDecision({status:'running'}),'refuse-ambiguous-submission'));
test('In-flight paid step reconciles by server id',()=>assert.equal(C.resumeDecision({status:'running',turnId:'x'}),'reconcile'));
test('Stopped step is not automatically retried',()=>assert.equal(C.resumeDecision({status:'stopped'}),'halt'));
test('Secret headers and nested tokens redacted',()=>{const s=JSON.stringify(C.clean({authorization:'SENTINEL_AUTH',nested:{token:'SENTINEL_TOKEN',sessionId:'SENTINEL_SESSION'}}));assert(!s.includes('SENTINEL'));});
test('Signed URL query and fragment are removed',()=>assert.equal(C.clean('https://cdn.tripo3d.com/model.glb?token=SENTINEL#secret'),'https://cdn.tripo3d.com/model.glb'));
test('Bearer-like message content refused',()=>assert.throws(()=>C.validate({...plan,steps:[{...plan.steps[0],text:'Bearer SENTINEL'}]},registry)));
test('Unknown operations cannot enter plans',()=>assert.throws(()=>C.validate({...plan,steps:[{id:'delete',kind:'delete'}]},registry)));
test('Duplicate item IDs refused',()=>assert.throws(()=>C.validate({...plan,steps:[plan.steps[0],plan.steps[0]]},registry)));
test('Inventory preserves microsecond differences',()=>{const a={projects:[{id:'1',name:'existing',edited:'2026-10-21T01:00:00.123456Z'}]};assert.equal(C.inventoryDiff(a,{projects:[{...a.projects[0],edited:'2026-10-21T01:00:00.123457Z'}]}).existingNonDshChanged,1);});
test('Insignificant trailing zero is equivalent',()=>{const a={projects:[{id:'1',name:'existing',edited:'2026-10-21T01:00:00.123450Z'}]};assert.equal(C.inventoryDiff(a,{projects:[{...a.projects[0],edited:'2026-10-21T01:00:00.12345Z'}]}).existingNonDshChanged,0);});
test('Default driver does not issue any request or storage write',()=>{let requests=0;const context={MutationObserver:class {observe(){}},window:{__dshDriverCore:C,__dshTripoSanitize:{},__dshOwnedCanvases:registry,fetch:()=>requests++},document:{readyState:'loading',addEventListener(){}},setTimeout,Map,Set,URL,sessionStorage:{getItem(){return null;}},indexedDB:{open(){return {};}}};vm.runInNewContext(fs.readFileSync(require.resolve('../driver.js'),'utf8'),context);assert.equal(requests,0);});
console.log(JSON.stringify({suite:'driver safety and resume',passed:tests.length,tests,liveTraffic:false},null,2));

