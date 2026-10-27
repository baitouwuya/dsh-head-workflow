// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const tests=[];function check(name,fn){fn();tests.push({name,status:'passed'});}
function element(){return {style:{},listeners:{},hidden:true,value:'',setAttribute(){},addEventListener(n,f){this.listeners[n]=f;},remove(){this.removed=true;}};}
function setup(state){
  const controls=Object.fromEntries(['#status','textarea','#start','#stop','#export','#save','#launcher','#close','#move','section'].map(k=>[k,element()]));
  const panel=element(),layout=element();panel.attachShadow=()=>({innerHTML:'',querySelector:k=>controls[k]});
  const document=Object.assign(new EventTarget(),{body:{appendChild(){}},readyState:'complete',createElement:t=>t==='style'?layout:panel});
  const window=Object.assign(new EventTarget(),{innerWidth:944,innerHeight:609,__dshTripoSanitize:require('../sanitize.js'),fetch(){throw Error('unexpected request');}});
  const context={window,document,Date,Event,CustomEvent,setInterval:()=>1,clearInterval(){},setTimeout,clearTimeout,location:{href:'https://studio.tripo3d.ai/projects'}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../observer.js'),'utf8'),context);
  if(state)document.dispatchEvent(new CustomEvent('dsh-tripo-ui-state',{detail:state}));
  return {window,document,controls,panel,layout};
}
const first=setup();
check("Panel Tab does not reach canvas shortcut handlers and preserves default focus navigation",()=>{let canvasCalls=0;const fn=()=>canvasCalls++;first.window.addEventListener("keydown",fn);const e=new Event("keydown",{cancelable:true});Object.defineProperty(e,"key",{value:"Tab"});Object.defineProperty(e,"composedPath",{value:()=>[{id:"dsh-canvas-observer"}]});first.window.dispatchEvent(e);first.window.removeEventListener("keydown",fn);assert.equal(canvasCalls,0);assert.equal(e.defaultPrevented,false);});
check('first mount is one 32px floating launcher without a site stylesheet',()=>{assert(first.controls.section.hidden);assert(!first.controls['#launcher'].hidden);assert.equal(first.panel.style.width,'32px');assert.equal(first.layout.textContent,undefined);});
first.controls['#launcher'].listeners.click();
check('explicit expansion floats without a site-root rewrite',()=>{assert(!first.controls.section.hidden);assert.equal(first.panel.style.width,'420px');assert.equal(first.layout.textContent,undefined);});
let saved;first.document.addEventListener('dsh-tripo-ui-save',e=>{saved=e.detail;});
first.controls['#move'].listeners.pointerdown({button:0,clientY:400,preventDefault(){}});
const movement=new Event('pointermove');Object.assign(movement,{clientX:900,clientY:200});first.window.dispatchEvent(movement);first.window.dispatchEvent(new Event('pointerup'));
check('drag docks to the opposite edge and emits bounded position',()=>{assert.equal(saved.side,'right');assert(saved.y>=0&&saved.y<=1);assert.equal(first.panel.style.right,'8px');});
const restored=setup(saved);
check('restored state preserves edge, vertical position and expansion',()=>{assert.equal(restored.panel.style.right,'8px');assert(!restored.controls.section.hidden);assert.equal(restored.controls.section.style.top,first.controls.section.style.top);});
const escape=new Event('keydown');escape.key='Escape';restored.window.dispatchEvent(escape);
check('Escape collapses to one floating launcher',()=>{assert(restored.controls.section.hidden);assert.equal(restored.panel.style.width,'32px');});
first.controls['#export'].listeners.click();
check('Export collapses while keeping sanitized JSON in the hidden panel',()=>{assert(first.controls.section.hidden);assert.equal(JSON.parse(first.controls.textarea.value).version,JSON.parse(fs.readFileSync(path.join(__dirname,'../manifest.json'),'utf8')).version);});
first.controls['#launcher'].listeners.click();
for(const [w,h] of [[320,240],[944,609],[1914,1200],[128,96]]){first.window.innerWidth=w;first.window.innerHeight=h;first.window.dispatchEvent(new Event('resize'));assert(parseFloat(first.panel.style.width)<=w);assert(parseFloat(first.controls.section.style.height)<=h);}
check('floating sizing remains bounded at four viewport sizes',()=>assert(true));
first.document.dispatchEvent(new Event('dsh-tripo-teardown'));
check('disable removes panel; never created a site stylesheet',()=>{assert(first.panel.removed);assert.equal(first.layout.removed,undefined);});
(async()=>{
  const document=new EventTarget();let persisted;const chrome={runtime:{id:'test',getManifest:()=>({})},storage:{local:{get:async()=>({}),set:async v=>{persisted=v;}}}};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../lifecycle.js'),'utf8'),{document,chrome,Event,CustomEvent,setInterval:()=>1,clearInterval(){},setTimeout,clearTimeout});
  await Promise.resolve();
  document.dispatchEvent(new CustomEvent('dsh-tripo-ui-save',{detail:{collapsed:false,side:'right',y:.25,token:'MUST_NOT_STORE'}}));
  await new Promise(r=>setTimeout(r,200));
  check('storage bridge persists only three UI fields, never arbitrary payload',()=>{assert.deepEqual(JSON.parse(JSON.stringify(persisted)),{dshObserverUiV1:{collapsed:false,side:'right',y:.25}});});
  document.dispatchEvent(new CustomEvent('dsh-tripo-ui-save',{detail:{collapsed:false,side:'secret',y:Infinity}}));
  await new Promise(r=>setTimeout(r,200));
  check('invalid storage event is rejected',()=>assert.equal(persisted.dshObserverUiV1.side,'right'));
  console.log(JSON.stringify({suite:'observer UI regression',tests,passed:tests.length,liveTraffic:false},null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
