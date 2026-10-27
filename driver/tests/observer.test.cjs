// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const S=require('../sanitize.js');
const tests=[];
function check(name,fn){fn();tests.push({name,status:'passed'});}
const sent='DO_NOT_PERSIST_SENTINEL_7a8b9c';
check('body values and credential fields do not persist',()=>{
  const encoded=JSON.stringify(S.body(JSON.stringify({message:sent,token:sent,nested:{password:sent},count:15,ok:true})));
  assert(!encoded.includes(sent));assert(!encoded.includes('15'));assert(encoded.includes('redacted'));
});
check('header values never persist; auth header name is visible',()=>{
  const obj=S.headers({Authorization:'Bearer '+sent,Cookie:sent,'x-custom':sent});
  assert.equal(obj.authorization,'<redacted>');assert(!JSON.stringify(obj).includes(sent));
});
check('URL credentials, query values, fragments and long IDs are removed',()=>{
  const encoded=JSON.stringify(S.url('https://name:'+sent+'@api.tripo3d.ai/canvas/session/'+sent+'?token='+sent+'#'+sent));
  assert(!encoded.includes(sent));assert(!encoded.includes('name'));
  assert.equal(S.url('https://eviltripo3d.ai/a'),null);
});
check('body and schema bounded',()=>{
  assert.equal(S.body('x'.repeat(70000)).reason,'size-limit');
  const o={};for(let i=0;i<100;i++)o['field'+i]=sent;
  assert.equal(Object.keys(S.schema(o).properties).length,40);
});
class Doc extends EventTarget {constructor(){super();this.body={appendChild:()=>{}};this.readyState='complete';}createElement(tag){return tag==='style'?{textContent:'',remove(){}}:panel;}}
function control(){return {listeners:{},style:{},textContent:'',value:'',hidden:true,setAttribute(){},addEventListener(name,fn){this.listeners[name]=fn;}};}
const controls=Object.fromEntries(['#status','textarea','#start','#stop','#export','#save','#launcher','#close','#move','section'].map(k=>[k,control()]));
const panel={id:'',style:{},remove(){this.removed=true;},attachShadow(){return {innerHTML:'',querySelector:k=>controls[k]};}};
class XHR extends EventTarget {open(method,url){this.method=method;this.url=url;}setRequestHeader(){}send(){this.status=200;this.responseType='text';this.responseText=JSON.stringify({secret:sent,done:true});this.dispatchEvent(new Event('loadend'));}}
class WS extends EventTarget {send(data){this.lastData=data;}}
const timers=new Set();
const document=new Doc();
const response=new Response(JSON.stringify({items:[{name:sent}],token:sent}),{headers:{'Content-Type':'application/json'}});
const originalPromise=Promise.resolve(response);
const originalFetch=function(){return originalPromise;};
const win=Object.assign(new EventTarget(),{fetch:originalFetch,WebSocket:WS,__dshTripoSanitize:S,innerWidth:944,innerHeight:609});
let clockOffset=0;
class Clock extends Date {static now(){return Date.now()+clockOffset;}}
const context={window:win,document,XMLHttpRequest:XHR,Request,Response,Headers,URL,URLSearchParams,FormData,Blob,ArrayBuffer,TextDecoder,Date:Clock,performance,location:{href:'https://studio.tripo3d.ai/projects'},setInterval:(fn)=>{timers.add(fn);return fn;},clearInterval:fn=>timers.delete(fn),setTimeout,clearTimeout,Event,CustomEvent};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../observer.js'),'utf8'),context);
(async()=>{
  check('idle means no network wrappers',()=>assert.equal(win.fetch,originalFetch));
  controls['#start'].listeners.click({isTrusted:true});
  const wrapped=win.fetch;
  check('fetch preserves returned promise identity',()=>assert.equal(win.fetch('https://api.tripo3d.ai/canvas/list',{headers:{Authorization:'Bearer '+sent}}),originalPromise));
  await new Promise(r=>setTimeout(r,30));
  const xhr=new XHR();xhr.open('GET','https://api.tripo3d.ai/canvas/state');xhr.setRequestHeader('Authorization',sent);xhr.send();
  const socket=new win.WebSocket('wss://api.tripo3d.ai/canvas/stream?token='+sent);socket.send(sent);socket.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({token:sent,state:'done'})}));
  controls['#export'].listeners.click();
  const first=JSON.parse(controls.textarea.value);
  check('fetch response schema captured',()=>assert(first.events.some(x=>x.kind==='fetch.response-shape')));
  check('XHR response captured',()=>assert(first.events.some(x=>x.kind==='xhr.response')));
  check('WebSocket receive captured',()=>assert(first.events.some(x=>x.kind==='ws.message')));
  controls['#start'].listeners.click({isTrusted:true});
  const socket2=new win.WebSocket('wss://api.tripo3d.ai/canvas/stream');
  for(let i=0;i<410;i++)socket2.send(sent);
  controls['#export'].listeners.click();
  const trace=JSON.parse(controls.textarea.value);
  check('bounded ring and lost-event count',()=>{assert.equal(trace.events.length,400);assert(trace.dropped>0);});
  check('trace contains no sentinel secret',()=>assert(!controls.textarea.value.includes(sent)));
  check('export stops and restores original wrappers',()=>{assert.equal(win.fetch,originalFetch);assert.equal(win.WebSocket,WS);assert.notEqual(wrapped,originalFetch);});
  controls['#start'].listeners.click({isTrusted:true});
  clockOffset=20000;
  for(const timer of [...timers])timer();
  controls['#export'].listeners.click();
  check('heartbeat delay stops safely while retaining exportable evidence',()=>{assert.equal(win.fetch,originalFetch);assert(!panel.removed);assert(JSON.parse(controls.textarea.value).events.some(e=>e.reason==='heartbeat-timeout-evidence-preserved'));});
  clockOffset=0;
  controls['#start'].listeners.click({isTrusted:true});
  document.dispatchEvent(new Event('dsh-tripo-teardown'));
  check('extension teardown restores fetch and removes panel',()=>{assert.equal(win.fetch,originalFetch);assert(panel.removed);assert.equal(timers.size,0);});
  console.log(JSON.stringify({suite:'offline observer safety',tests,passed:tests.length,liveTraffic:false},null,2));
})().catch(e=>{console.error(e.message);process.exitCode=1;});
