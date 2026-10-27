// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),{webcrypto}=require('crypto');
const path=require('node:path');const ext=path.resolve(__dirname,'..'),run=process.env.TRIPO_TEST_REPORT_DIR||path.join(ext,'test-results-v059');fs.mkdirSync(run,{recursive:true});
const pid='11111111-1111-4111-8111-111111111111',cid='22222222-2222-4222-8222-222222222222';
const state={canvas:{projectId:pid,canvasId:cid,revision:'1'},nodes:[{id:'input',type:'NODE_TYPE_UPLOAD_CARD',params:{assetType:'image'},ui:{position:{x:0,y:0}},inputMount:[],nodeAssets:[]},{id:'image',type:'NODE_TYPE_GENERATE_IMAGE',params:{amount:1,scale:'1:1',model_version:'gpt_image_2',t_pose:true,sketch_to_render:false,prompt:'fixture'},ui:{position:{x:0,y:0}},inputMount:[],nodeAssets:[]}],edges:[]};
let runStatus='RUN_STATUS_RUNNING',credit=100,delayed=false,aborted=false,extensionListener;
const calls=[],files=[],tests=[],document=new EventTarget(),memory=new Map();
document.documentElement={dataset:{},appendChild(){}};document.createElement=()=>({});document.querySelectorAll=()=>[];
const rpc='https://msapi.tripo3d.ai/ms/web/api',payment='https://api.tripo3d.ai/v2/studio/user/profile/payment';
const nativeFetch=async(url,init={})=>{
 const operation=new Headers(init.headers).get('x-micro-method')?.split('agent.')[1];
 const body=typeof init.body==='string'?JSON.parse(init.body):undefined;calls.push({operation,url,body});
 if(delayed&&init.signal)return new Promise((resolve,reject)=>init.signal.addEventListener('abort',()=>{aborted=true;reject(Error('Stopped'));},{once:true}));
 let value={error:{code:0}};
 if(url==='https://fixture.test/artifact.glb'){const b=Buffer.alloc(24);b.writeUInt32LE(0x46546c67);b.writeUInt32LE(2,4);b.writeUInt32LE(24,8);return new Response(b);}
 if(operation==='LabService/ListLabJobs')value={jobs:[{jobId:'lab-job',status:'completed'}],activeJob:null};
 if(operation==='LabService/GetLabJob')value={jobId:'lab-job',status:'completed',artifacts:[{artifactId:'lab-artifact',kind:'preview',downloadUrl:'https://fixture.test/artifact.glb'}]};
 if(url.includes('/temporary_token'))value={code:0,data:{host:'s3.us-west-2.amazonaws.com',resource_bucket:'fixture-bucket',resource_uri:'fixture/input.png',sts_ak:'SYNTHETIC_ACCESS',sts_sk:'SYNTHETIC_SECRET',session_token:'SYNTHETIC_SESSION'}};
 if(operation==='AssetService/ImportInputAssets')value={assets:[{assetId:body.objectRefs[0].contentType==='model/gltf-binary'?'artifact-imported':'uploaded-fixture',status:'INPUT_ASSET_STATUS_READY'}]};
 if(url===payment)value={data:{wallet:{total_credit:credit}}};
 if(operation==='CanvasService/GetCanvas'){assert.equal(new Headers(init.headers).get('x-auth-token'),'SYNTHETIC_SECRET');value=state;}
 if(operation==='CanvasService/SaveCanvas'){
   state.nodes=body.nodes;state.edges=body.edges;state.canvas.revision=String(Number(state.canvas.revision)+1);
 }
 if(operation==='ProjectService/CreateProject')value={project:{projectId:'new-project'},canvas:{canvasId:'new-canvas'}};
 if(operation==='RunService/CreateRun'){credit=90;value={runId:'run-1'};}
 if(operation==='RunService/StopRun')runStatus='RUN_STATUS_STOPPED';
 if(operation==='RunService/GetRun')value={run:{runId:'run-1',canvasId:cid,status:runStatus,nodeIds:['image']}};
 return new Response(JSON.stringify(value),{headers:{'content-type':'application/json'}});
};
const common={document,crypto:webcrypto,CustomEvent,Event,AbortController,Headers,Request,Response,URL,Date,Map,Set,performance,Buffer,TextDecoder,TextEncoder,Uint8Array,DataView,ArrayBuffer,Blob,FormData,atob,btoa,setTimeout,clearTimeout};
const main={fetch:nativeFetch,__dshTripoSanitize:{schema:()=>({type:'fixture'})},__dshObserverControl:{start(){},stop(){},dump:()=>({events:[]})}};
const context={...common,window:main,location:{origin:'https://studio.tripo3d.ai',href:'https://studio.tripo3d.ai/projects/'+pid,pathname:'/projects/'+pid},sessionStorage:{getItem:k=>memory.get(k),setItem:(k,v)=>memory.set(k,v),removeItem:k=>memory.delete(k)}};
vm.createContext(context);for(const n of ['shortcut-core.js','native-contracts.js','storage-sign.js','auto-layout.js','durable-state.js','canvas-assets.js','artifact-download.js','lab-operations.js','ui-actions.js','driver.js'])vm.runInContext(fs.readFileSync(ext+'/'+n,'utf8'),context);
const isolated={};vm.runInNewContext(fs.readFileSync(ext+'/lifecycle.js','utf8'),{...common,window:isolated,location:{pathname:'/projects/test'},chrome:{runtime:{id:'fixture',getURL:n=>'chrome-extension://fixture/'+n,getManifest:()=>({version:'0.2.59'}),onMessage:{addListener:f=>extensionListener=f}}},setInterval:()=>1,clearInterval(){}});
const page={...common};vm.createContext(page);vm.runInContext(`this.call=(name,args={})=>new Promise((resolve,reject)=>{const id=crypto.randomUUID();const receive=e=>{if(e.detail.id!==id)return;document.removeEventListener('dsh-shortcut-response',receive);e.detail.ok?resolve(e.detail.result):reject(Error(e.detail.error));};document.addEventListener('dsh-shortcut-response',receive);document.dispatchEvent(new CustomEvent('dsh-shortcut-request',{detail:{id,name,args}}));});`,page);
const call=page.call;
const durableMemory=new Map();main.DshDurableState={create:()=>({load:async k=>durableMemory.get(k)||null,save:async(k,v)=>durableMemory.set(k,JSON.parse(JSON.stringify(v)))})};
document.addEventListener('dsh-writer-request',e=>{const p=e.detail.payload;files.push(p);let result={ok:true};if(p.area==='health')result={ok:true,capabilities:['artifact-chunks']};if(p.area==='artifacts'&&p.final){const b=Buffer.concat(files.filter(x=>x.area==='artifacts'&&x.name===p.name).map(x=>Buffer.from(x.base64,'base64')));result={ok:true,bytes:b.length,sha256:p.sha256,path:'out/'+p.name};}document.dispatchEvent(new CustomEvent('dsh-writer-response',{detail:{id:e.detail.id,result}}));});
async function check(name,fn){await fn();tests.push({name,passed:true});}
async function observe(operation,body){await main.fetch(rpc,{method:'POST',headers:{'x-auth-token':'SYNTHETIC_SECRET',Authorization:'Bearer SYNTHETIC_SECRET','x-micro-method':'/tripo.canvas.api.agent.'+operation},body:JSON.stringify(body)});await new Promise(r=>setTimeout(r,15));}
async function capture(){await call('capture');await observe('CanvasService/GetCanvas',{canvasId:cid});await main.fetch(payment,{headers:{Authorization:'Bearer SYNTHETIC_SECRET'}});await observe('CanvasService/SaveCanvas',{canvasId:cid,clientId:'fixture-client',revision:state.canvas.revision,nodes:state.nodes,edges:state.edges});await new Promise(r=>setTimeout(r,15));}
(async()=>{
 const expected=['capture','read','run','export','stop','createCanvas','uploadAsset','createNode','connectNodes','generate','waitTask','saveCanvas','autoLayout','selectNode','labExportDialog','labExport','listCanvasAssets','listLabArtifacts','setLabInput','publishLabArtifact','labDownloadArtifact'];
 await check('MAIN actions, page DOM events, and popup adapter expose the same registry',async()=>{assert.deepEqual([...main.__dshShortcut.actions()],expected);assert.deepEqual([...(await call('actions'))],expected);const r=await new Promise(resolve=>extensionListener({type:'dsh-shortcut',name:'actions'},{id:'fixture'},resolve));assert.deepEqual([...r.result],expected);assert.equal((await call('status')).version,'0.2.59');});

 await check('First autoLayout click waits for native startup without Capture or reload',async()=>{
  assert.equal((await call('status')).ready,false);const n=calls.length;let finished=false;
  const pending=call('autoLayout').then(v=>{finished=true;return v;});
  await new Promise(r=>setTimeout(r,150));assert.equal(calls.length,n);assert(!finished);
  await observe('CanvasService/GetCanvas',{canvasId:cid});await new Promise(r=>setTimeout(r,150));assert(!finished);assert.equal((await call('status')).ready,false);
  await main.fetch(payment,{headers:{Authorization:'Bearer SYNTHETIC_SECRET'}});const preview=await pending;
  assert.equal(preview.mode,'dry-run');assert.equal((await call('status')).ready,true);assert(!calls.slice(n).some(c=>c.operation==='CanvasService/SaveCanvas'));
 });
 await check('STOP cancels startup waiting before any request',async()=>{
  await call('stop');const n=calls.length,pending=call('autoLayout',{dryRun:false});await new Promise(r=>setTimeout(r,30));await call('stop');await assert.rejects(pending,/Stopped/);assert.equal(calls.length,n);
 });
 await check('Route changes during startup cannot retarget the action',async()=>{
  const n=calls.length,pending=call('autoLayout',{dryRun:false});await new Promise(r=>setTimeout(r,30));context.location.pathname='/projects/another';await assert.rejects(pending,/open canvas changed/);assert.equal(calls.length,n);context.location.pathname='/projects/'+pid;
 });
 await capture();

 await check('Auto-layout dry-run reads once, never saves and returns an inverse',async()=>{const n=calls.length,old=JSON.parse(JSON.stringify(state));const p=await call('autoLayout');assert.equal(p.mode,'dry-run');assert.equal(p.mutatingRequestsSent,0);assert(p.inverse.changes.length===2);assert.deepEqual(state,old);assert.deepEqual(calls.slice(n).map(c=>c.operation),['CanvasService/GetCanvas']);});
 await check('Auto-layout saves only geometry, is idempotent and inverse restores positions',async()=>{const old=JSON.parse(JSON.stringify(state));const a=await call('autoLayout',{dryRun:false});assert.equal(a.mutatingRequestsSent,1);assert.equal(a.balanceBefore,100);assert.equal(a.balanceAfter,100);const n=calls.length;const b=await call('autoLayout',{dryRun:false});assert.equal(b.changedNodes,0);assert(!calls.slice(n).some(c=>c.operation==='CanvasService/SaveCanvas'));await call('autoLayout',{inverse:a.inverse,dryRun:false});assert.deepEqual(state.nodes,old.nodes);assert.deepEqual(state.edges,old.edges);});
 await check('Wrong-target inverse is rejected before dispatch',async()=>{const n=calls.length;await assert.rejects(call('autoLayout',{inverse:JSON.stringify({canvasId:'wrong',changes:[]}),dryRun:false}),/canvas that is open/);assert.equal(n,calls.length);});
 await check('STOP interrupts layout before SaveCanvas',async()=>{const n=calls.length;const pending=call('autoLayout',{origin:{x:200,y:200},dryRun:false});await new Promise(r=>setTimeout(r,60));await call('stop');await assert.rejects(pending,/Stopped/);assert(!calls.slice(n).some(c=>c.operation==='CanvasService/SaveCanvas'));await capture();});
 await check('Upload dry-run makes zero calls',async()=>{const n=calls.length;const r=await call('uploadAsset',{bytes:[1,2]});assert.equal(r.networkRequestsSent,0);assert.equal(n,calls.length);});
 await check('Upload executes ticket, signed PUT, import in order and accounts',async()=>{const n=calls.length;const r=await call('uploadAsset',{bytes:[137,80,78,71],filename:'fixture.png',dryRun:false});assert.equal(r.assetId,'uploaded-fixture');assert.equal(r.observedDebit,0);const c=calls.slice(n);assert(c[1].url.endsWith('/temporary_token'));assert.deepEqual(c[1].body,{client:'aws',format:'png'});assert(c[2].url.includes('.s3-accelerate.amazonaws.com/fixture/input.png'));assert.equal(c[3].operation,'AssetService/ImportInputAssets');assert.equal(c[3].body.objectRefs[0].sizeBytes,'4');});
 await check('Public RPC cannot replace authenticated replay headers',async()=>{
  await main.fetch(rpc,{method:'POST',headers:{'x-micro-method':'/tripo.canvas.api.agent.TemplateService/ListTemplates'},body:'{}'});await new Promise(r=>setTimeout(r,15));
  const result=await call('read');assert.equal(result.canvas.canvas.canvasId,cid);
 });
 await check('CreateCanvas defaults to dry-run with zero requests',async()=>{const n=calls.length;assert.equal((await call('createCanvas',{name:'dsh-test'})).networkRequestsSent,0);assert.equal(calls.length,n);});
 await check('Creation replays observed empty CreateProject body, then separate rename',async()=>{const n=calls.length;const result=await call('createCanvas',{name:'dsh-test',dryRun:false});assert.equal(result.canvasId,'new-canvas');assert.deepEqual(calls.slice(n).map(c=>c.operation),['ProjectService/CreateProject','ProjectService/UpdateProject']);assert.deepEqual(calls[n].body,{});assert.deepEqual(calls[n+1].body,{projectId:'new-project',name:'dsh-test'});});
 await check('Wrong canvas rejected before any dispatch',async()=>{const n=calls.length;await assert.rejects(call('createNode',{canvasId:'wrong',type:'NODE_TYPE_GENERATE_IMAGE',dryRun:false}),/canvas that is open/);assert.equal(calls.length,n);});
 let added;
 await check('CreateNode dry-run leaves native body unchanged and sends nothing',async()=>{const n=calls.length;const preview=await call('createNode',{type:'NODE_TYPE_GENERATE_IMAGE',params:{amount:1}});assert.equal(preview.body.nodes.length,3);assert.equal(state.nodes.length,2);assert.equal(calls.length,n);});
 await check('CreateNode appends using captured node and save envelope; one save and one revision read',async()=>{const n=calls.length;added=await call('createNode',{type:'NODE_TYPE_GENERATE_IMAGE',params:{amount:1},dryRun:false});assert.equal(state.nodes.length,3);assert(state.nodes.some(n=>n.id===added.nodeId));assert.deepEqual(calls.slice(n).map(c=>c.operation),['CanvasService/SaveCanvas','CanvasService/GetCanvas']);});
 await check('ConnectNodes uses observed source/target/port shape',async()=>{const result=await call('connectNodes',{from:'input',to:'image',dryRun:false});assert.equal(state.edges[0].id,result.edgeId);assert.deepEqual(state.edges[0].source,{nodeId:'input',port:''});assert.deepEqual(state.edges[0].target,{nodeId:'image',port:''});});
 await observe('RunService/CreateRun',{canvasId:cid,idempotencyKey:'fixture',includeCompleted:true,mode:'MODE_CONTROL',nodeIds:['image'],origin:'RUN_ORIGIN_CANVAS'});credit=100;
 await check('Generate dry-run contains recipe and captured run constants with zero requests',async()=>{const n=calls.length;const r=await call('generate',{nodeId:'image',model:'gpt_image_2',amount:1,scale:'1:1',t_pose:true,sketch_to_render:false,prompt:'original'});assert.equal(calls.length,n);assert.equal(r.runBody.mode,'MODE_CONTROL');assert.equal(r.body.nodes.find(n=>n.id==='image').params.prompt,'original');});
 await check('Generate saves parameters, submits once, and records balance',async()=>{const n=calls.length;const r=await call('generate',{nodeId:'image',prompt:'original',dryRun:false});assert.equal(r.runId,'run-1');assert.equal(r.balanceBefore,100);assert.equal(r.balanceAfter,90);assert.equal(calls.slice(n).filter(c=>c.operation==='RunService/CreateRun').length,1);assert.equal(state.nodes.find(n=>n.id==='image').params.prompt,'original');});
 await check('Submitted task remains tracked; a second generation is rejected',async()=>{const n=calls.length;await assert.rejects(call('generate',{nodeId:'image',dryRun:false}),/still tracked/);assert.equal(calls.length,n);});
 await check('WaitTask polls terminal state and returns redacted output plus final accounting',async()=>{runStatus='RUN_STATUS_SUCCEEDED';state.nodes.find(n=>n.id==='image').nodeAssets=[{assetId:'output',url:'https://example.test/result.png?Signature=SYNTHETIC_SECRET'}];const r=await call('waitTask',{runId:'run-1'});assert.equal(r.resultUrl,'https://example.test/result.png');assert.equal(r.observedDebit,10);});
 await check('Fixed model, texture, rig and UV types use captured CreateRun without changing their recipes',async()=>{const original=JSON.parse(JSON.stringify(state.nodes));for(const type of ['NODE_TYPE_GENERATE_SM_MODEL','NODE_TYPE_GENERATE_HD_MODEL','NODE_TYPE_TEXTURE','NODE_TYPE_RIGGING','NODE_TYPE_SMART_UV']){const n=state.nodes.find(x=>x.id==='image');n.type=type;n.params={model_version:'observed-fixture',custom:'keep'};await call('read');const preview=await call('generate',{nodeId:'image'});assert.equal(preview.runBody.mode,'MODE_CONTROL');assert.deepEqual(JSON.parse(JSON.stringify(preview.body.nodes.find(x=>x.id==='image').params)),n.params);}state.nodes=original;});
 await check('Final save retains outputs returned by the latest read',async()=>{await call('saveCanvas',{dryRun:false});assert.equal(state.nodes.find(n=>n.id==='image').nodeAssets[0].assetId,'output');});
 await check('STOP aborts pending transport immediately',async()=>{await call('generate',{nodeId:'image',dryRun:false});delayed=true;const waiting=call('waitTask',{runId:'run-1'});await new Promise(r=>setTimeout(r,10));const start=performance.now();await call('stop');await assert.rejects(waiting,/Stopped/);assert(aborted);assert(performance.now()-start<1000);delayed=false;await new Promise(r=>setTimeout(r,2200));assert(calls.some(c=>c.operation==='RunService/StopRun'));});
 await check('Evidence does not persist auth or signed URL query values',async()=>{await call('export');assert(!JSON.stringify(files).includes('SYNTHETIC_SECRET'));});
 await check('Popup has all buttons and parses arguments for named actions',async()=>{const html=fs.readFileSync(ext+'/popup.html','utf8');for(const name of expected)assert(html.includes('data-action="'+name+'"'));new vm.Script(fs.readFileSync(ext+'/popup.js','utf8'));});
 await check('Fresh canvas needs no prior native SaveCanvas or CreateRun template',async()=>{
  await call('stop');state.nodes=[];state.edges=[];state.canvas.revision='1';runStatus='RUN_STATUS_RUNNING';
  await call('capture');await observe('CanvasService/GetCanvas',{canvasId:cid});await main.fetch(payment,{headers:{Authorization:'Bearer SYNTHETIC_SECRET'}});await new Promise(r=>setTimeout(r,15));
  const upload=await call('createNode',{type:'NODE_TYPE_UPLOAD_CARD',params:{assetType:'image'},inputMount:[{assetId:'uploaded-fixture'}],dryRun:false});
  const gen=await call('createNode',{type:'NODE_TYPE_GENERATE_IMAGE',params:{t_pose:true,template_id:'',prompt:'original'},dryRun:false});
  await call('connectNodes',{from:upload.nodeId,to:gen.nodeId,fromPort:'image',toPort:'image',dryRun:false});
  credit=100;const submission=await call('generate',{nodeId:gen.nodeId,dryRun:false});assert.equal(submission.runId,'run-1');assert.equal(state.nodes.length,2);assert.equal(state.edges.length,1);assert.equal(state.nodes[1].params.t_pose,true);assert.equal(state.nodes[1].params.template_id,'');
  runStatus='RUN_STATUS_FAILED';await assert.rejects(call('waitTask',{runId:'run-1'}),/balance 100 -> 90/);await call('stop');
 });
 await capture();
 let labNode,nextLab;
 await check('Lab template creates a fresh native Lab without a supplied template',async()=>{labNode=await call('createNode',{type:'NODE_TYPE_AI_3D_LAB',dryRun:false});nextLab=await call('createNode',{type:'NODE_TYPE_AI_3D_LAB',dryRun:false});assert(labNode.nodeId);});
 await check('Existing canvas asset binding uses real public action and native input edge',async()=>{const before=calls.length;await call('setLabInput',{nodeId:labNode.nodeId,assetId:'uploaded-fixture'});assert(!calls.slice(before).some(c=>c.operation==='CanvasService/SaveCanvas'));const r=await call('setLabInput',{nodeId:labNode.nodeId,assetId:'uploaded-fixture',dryRun:false});assert.equal(r.assetId,'uploaded-fixture');assert.equal(r.binding,'native-edge');assert(state.edges.some(e=>e.id===r.edgeId&&e.target.nodeId===labNode.nodeId));});
 await check('Non-image Lab output/input ports survive native save and revision read',async()=>{await call('connectNodes',{from:labNode.nodeId,to:nextLab.nodeId,fromPort:'output',toPort:'input',dryRun:false});assert(state.edges.some(e=>e.source.nodeId===labNode.nodeId&&e.source.port==='output'&&e.target.port==='input'));});
 await check('Lab job/artifact discovery uses ownership-scoped read contracts',async()=>{const jobs=await call('listLabArtifacts',{nodeId:labNode.nodeId});assert.equal(jobs.jobs[0].jobId,'lab-job');const artifacts=await call('listLabArtifacts',{nodeId:labNode.nodeId,jobId:'lab-job'});assert.equal(artifacts.artifacts[0].filename,'artifact.glb');});
 await check('Unpublished GLB artifact uploads/imports once and appends native reference',async()=>{const n=calls.length,r=await call('publishLabArtifact',{nodeId:labNode.nodeId,jobId:'lab-job',artifactId:'lab-artifact',dryRun:false});assert.equal(r.assetId,'artifact-imported');const ticket=calls.slice(n).find(c=>c.url.includes('temporary_token'));assert.equal(ticket.body.format,'glb');const im=calls.slice(n).find(c=>c.operation==='AssetService/ImportInputAssets');assert.equal(im.body.objectRefs[0].contentType,'model/gltf-binary');const again=await call('publishLabArtifact',{nodeId:labNode.nodeId,jobId:'lab-job',artifactId:'lab-artifact',dryRun:false});assert.equal(again.alreadyPublished,true);assert.equal(calls.slice(n).filter(c=>c.operation==='AssetService/ImportInputAssets').length,1);});
 await check('Original artifact download traverses writer bridge and returns verified receipt',async()=>{const r=await call('labDownloadArtifact',{nodeId:labNode.nodeId,jobId:'lab-job',artifactId:'lab-artifact',dryRun:false});assert.equal(r.download.completed,true);assert.equal(r.download.bytes,24);assert.equal(r.converted,false);});
 const result={version:'0.2.59',passed:tests.length,actions:expected,tests,liveBrowser:false,scope:'Actual source, MAIN/isolated/page-event bridge, mocked transport; no Tripo requests',limitations:['Offline transport tests only; the new actions still require live verification after extension reload.']};
 fs.writeFileSync(run+'/tests-driver-v059.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
})().catch(e=>{console.error(e);process.exitCode=1;});
