// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(() => {
  'use strict';
  const version='0.2.59', rpc='https://msapi.tripo3d.ai/ms/web/api';
  const prefix='/tripo.canvas.api.agent.', payment='https://api.tripo3d.ai/v2/studio/user/profile/payment';
  const S=window.__dshTripoSanitize, templates=new Map(), writes=new Map();
  let capturing=false, originalFetch, wrapper, auth, paymentRead, canvas, conversation;
  let message='Ready', stopped=true, dispatches=0, job, step, remoteStop, evidencePath;
  const events=[], contracts=window.__dshNativeContracts;
  const storageToken='https://api.tripo3d.ai/v2/studio/storage/temporary_token';
  let storageRead;
  const clean=value=>{
    if(typeof value==='string')return /Bearer\s|eyJ[A-Za-z0-9_-]{12,}\./.test(value)?'<redacted>':value.replace(/https:\/\/[^\s"<>]+/g,s=>{try{const u=new URL(s);return u.origin+u.pathname;}catch{return '<url>';}});
    if(Array.isArray(value))return value.map(clean);
    if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,/authorization|cookie|token|password|secret|credential|signature|policy|access.?key|sts_ak|sts_sk|session|csrf|client.?id|api.?key/i.test(k)?'<redacted>':clean(v)]));
    return value;
  };
  function log(text,data){message=text;events.push({at:new Date().toISOString(),text,data:clean(data)});if(events.length>400)events.shift();}
  const parse=value=>typeof value==='string'?JSON.parse(value):value;
  const project=()=>location.pathname.split('/')[2];
  const contextReady=()=>!!(auth&&paymentRead&&canvas?.canvas?.projectId===project()&&canvas?.canvas?.canvasId);
  async function awaitContext(signal){
    const opened=project();
    if(!opened||opened==='all')throw Error('Open a canvas before using Auto-layout.');
    if(!capturing)capture();
    if(contextReady())return;
    log('Waiting for the canvas startup requests…');
    const started=Date.now();
    while(!contextReady()){
      if(project()!==opened)throw Error('The open canvas changed while waiting. No changes were sent.');
      if(Date.now()-started>=30000)throw Error('Canvas startup did not finish within 30 seconds. No changes were sent. Check that Studio has finished loading.');
      await pause(100,signal);
    }
    if(project()!==opened)throw Error('The open canvas changed while waiting. No changes were sent.');
  }
  function target(plan={}){
    if(!project()||project()==='all')throw Error('no open canvas');
    const current=canvas?.canvas;
    if(!current||current.projectId!==project())throw Error('Capture requests, then reopen the canvas to observe its identity.');
    if((plan.projectId&&plan.projectId!==current.projectId)||(plan.canvasId&&plan.canvasId!==current.canvasId))throw Error('The plan must target the canvas that is open.');
    return current;
  }
  function pause(ms,signal){
    return new Promise((resolve,reject)=>{
      const cancel=()=>{clearTimeout(timer);reject(Error('Stopped'));};
      const timer=setTimeout(()=>{signal?.removeEventListener('abort',cancel);resolve();},ms);
      if(signal?.aborted)cancel();else signal?.addEventListener('abort',cancel,{once:true});
    });
  }
  async function json(response){
    if([403,429].includes(response.status)){stopped=true;throw Error('Service challenge or rate limit. Stopped; no retry.');}
    if(!response.ok)throw Error('Request failed: HTTP '+response.status);
    const value=await response.json();if(value.error?.code)throw Error(value.error.message||'Service error '+value.error.code);return value;
  }
  function capture(){
    if(capturing)return;window.__dshObserverControl?.start();capturing=true;originalFetch=window.fetch;
    wrapper=function(input,init={}){
      const url=new URL(input instanceof Request?input.url:input,location.href);
      const address=url.origin+url.pathname,headers=new Headers(init.headers||(input instanceof Request?input.headers:undefined));
      const operation=(headers.get('x-micro-method')||'').replace(prefix,'');
      let body;try{body=JSON.parse(init.body);}catch{}
      const result=Reflect.apply(originalFetch,this,[input,init]);
      if(address==='https://api.tripo3d.ai/v2/studio/operation/download_with_name'&&typeof body?.file_name==='string'){
        result.then(response=>downloads.observeNativeDownload?.(body.file_name,response)).catch(()=>{});
      }
      if(/(^|\.)tripo3d\.(ai|com)$/.test(url.hostname)||url.hostname.endsWith('.amazonaws.com')){
        let details=body;
        if(init.body instanceof FormData)details={formData:[...init.body.entries()].map(([name,value])=>({name,value:typeof value==='string'?clean({[name]:value})[name]:{fileName:value.name,mimeType:value.type,size:value.size}}))};
        if(init.body instanceof Blob)details={binaryBytes:init.body.size,mimeType:init.body.type};
        if(init.body instanceof ArrayBuffer||ArrayBuffer.isView(init.body))details={binaryBytes:init.body.byteLength};
        log('Native request contract',{operation,url:address,method:init.method||(input instanceof Request?input.method:'GET'),credentials:init.credentials||(input instanceof Request?input.credentials:'same-origin'),headerNames:[...headers.keys()],body:details});
        result.then(async response=>{
          if(!capturing||!/json/i.test(response.headers.get('content-type')||''))return;
          if(Number(response.headers.get('content-length'))>1048576)return;
          const reply=await response.clone().json();
          log('Native response contract',{operation,url:address,status:response.status,body:reply});
        }).catch(()=>{});
      }
      if(address===storageToken)storageRead={headers,credentials:init.credentials||'omit'};
      if(address===rpc||address===payment){
        const observedProject=project();
        result.then(async response=>{
          if(!capturing||!response.ok)return;
          if(address===payment)paymentRead={headers,credentials:init.credentials||'omit',method:init.method||'GET'};
          else {
            if(headers.has('x-auth-token'))auth={headers,credentials:init.credentials||'omit'};
            templates.set(operation,{body,projectId:observedProject});
            if(operation==='RunService/CreateRun'){const reply=await response.clone().json();templates.get(operation).runIdField=reply.run?.runId?'run.runId':reply.runId?'runId':null;}
            if(operation==='SessionService/GetSession')conversation={body,projectId:observedProject};
            if(operation==='CanvasService/GetCanvas')canvas=await response.clone().json();
          }
          log('Observed '+(operation||'balance'),{bodyShape:S.schema(body),status:response.status});
        }).catch(()=>{});
      }
      return result;
    };
    window.fetch=wrapper;log('Capturing requests.');
  }
  function endCapture(){
    if(window.fetch===wrapper)window.fetch=originalFetch;capturing=false;
    auth=null;paymentRead=null;storageRead=null;conversation=null;templates.clear();
    sessionStorage.removeItem('dsh-capture-until');window.__dshObserverControl?.stop();
  }
  async function request(operation,body,signal){
    if(signal?.aborted)throw Error('Stopped');
    if(!auth)throw Error('No observed authentication. Capture requests and reopen the canvas.');
    const headers=new Headers(auth.headers);headers.set('x-micro-method',prefix+operation);dispatches++;
    const response=await (originalFetch||window.fetch)(rpc,{method:'POST',headers,credentials:auth.credentials,body:JSON.stringify(body),signal});
    const value=await json(response);log(operation,{body:clean(body)});return value;
  }
  async function balance(signal){
    if(!paymentRead)throw Error('No observed balance request. Capture requests and reopen the canvas.');
    dispatches++;const value=await json(await (originalFetch||window.fetch)(payment,{...paymentRead,signal}));
    const credit=value.data?.wallet?.total_credit;
    if(!Number.isFinite(credit))throw Error('The service did not return a credit balance.');return credit;
  }
  async function readCanvas(plan,signal){
    const current=target(plan);const value=await request('CanvasService/GetCanvas',{canvasId:current.canvasId},signal);
    if(value.canvas?.canvasId!==current.canvasId||value.canvas?.projectId!==project())throw Error('The returned canvas is not the canvas that is open.');
    canvas=value;return value;
  }
  document.addEventListener('dsh-writer-response',e=>{
    const pending=writes.get(e.detail?.id);if(!pending)return;writes.delete(e.detail.id);clearTimeout(pending.timer);
    e.detail.result?.ok?pending.resolve(e.detail.result):pending.reject(Error(e.detail.result?.error||'Local writer unavailable.'));
  });
  function write(payload,signal){return new Promise((resolve,reject)=>{
    const id=crypto.randomUUID(),timer=setTimeout(()=>{writes.delete(id);reject(Error('Local writer did not respond.'));},20000);
    const cancel=()=>{writes.delete(id);clearTimeout(timer);reject(Error('Stopped'));};
    if(signal?.aborted){cancel();return;}signal?.addEventListener('abort',cancel,{once:true});
    const done=fn=>value=>{signal?.removeEventListener('abort',cancel);fn(value);};
    writes.set(id,{resolve:done(resolve),reject:done(reject),timer});document.dispatchEvent(new CustomEvent('dsh-writer-request',{detail:{id,payload}}));
  });}
  async function exportEvidence(signal){
    const run='p3-recording-'+Date.now();
    const data=clean({version,flow:window.__dshFlowState,job,canvas,events,observer:window.__dshObserverControl?.dump()});
    await write({area:'runs',run,name:'capture.json',text:JSON.stringify(data,null,2)},signal);
    await write({area:'runs',run,name:'checkpoint.json',text:JSON.stringify(clean(window.__dshFlowState||{}),null,2)},signal);
    await write({area:'runs',run,name:'log.txt',text:events.map(e=>e.at+' '+e.text).join('\n')+'\n'},signal);
    evidencePath='Z:\\tripo-studio\\runs\\'+run;return {evidencePath};
  }
  async function assetOutput(item,plan,signal){
    const state=await readCanvas(plan,signal),assets=state.nodes.flatMap(n=>(n.nodeAssets||[]).map(a=>({...a,nodeType:n.type})));
    const asset=item.assetId?assets.find(a=>a.assetId===item.assetId):assets.findLast(a=>a.nodeType==='NODE_TYPE_GENERATE_HD_MODEL');
    if(!asset)throw Error('No matching model output on the open canvas.');
    const detail=await request('NodeService/GetNodeAssetDetail',{assetId:asset.assetId},signal),url=detail.detail?.model_url;
    if(!url)throw Error('This output has no model download URL.');
    const response=await (originalFetch||window.fetch)(url,{credentials:'omit',signal});
    if(!response.ok)throw Error('Model download failed: HTTP '+response.status);
    const bytes=await response.arrayBuffer(),view=new DataView(bytes);
    if(view.byteLength<20||view.getUint32(0,true)!==0x46546c67)throw Error('This output is not a GLB model.');
    if(item.kind==='inspectGlb'){
      const glb=JSON.parse(new TextDecoder().decode(new Uint8Array(bytes,20,view.getUint32(12,true))));
      let faces=0;const positions=new Set();
      for(const mesh of glb.meshes||[])for(const p of mesh.primitives||[]){positions.add(p.attributes.POSITION);faces+=glb.accessors[p.indices??p.attributes.POSITION].count/3;}
      return {assetId:asset.assetId,bytes:bytes.byteLength,faces,vertices:[...positions].reduce((n,i)=>n+glb.accessors[i].count,0)};
    }
    // The existing chunk writer needs a checksum to finish a binary transfer.
    const sha256=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(v=>v.toString(16).padStart(2,'0')).join('');
    const name='dsh-run-'+Date.now()+'-model.glb';let saved;
    for(let offset=0;offset<bytes.byteLength;offset+=524288){
      if(signal.aborted)throw Error('Stopped');
      const part=new Uint8Array(bytes,offset,Math.min(524288,bytes.byteLength-offset));let binary='';
      for(let i=0;i<part.length;i+=8192)binary+=String.fromCharCode(...part.subarray(i,i+8192));
      saved=await write({area:'out',name,offset,base64:btoa(binary),final:offset+part.length===bytes.byteLength,sha256},signal);
    }
    return saved;
  }
  async function cancelServer(){
    if(!step?.turnId&&!step?.runId)return {serverCancellation:step?.submitting?'submission-outcome-unknown':'not-needed'};
    target(job.plan);
    if(!step.runId){const runs=await request('RunService/ListCanvasRuns',{canvasId:job.plan.canvasId});step.runId=runs.runs?.find(r=>r.turnId===step.turnId)?.runId;}
    let cancelError;
    try{if(step.turnId)await request('TurnService/CancelTurn',{turnId:step.turnId});}catch(e){cancelError=e;}
    if(!step.runId){const runs=await request('RunService/ListCanvasRuns',{canvasId:job.plan.canvasId});step.runId=runs.runs?.find(r=>r.turnId===step.turnId)?.runId;}
    if(!step.runId)throw Error(cancelError?.message||'Cancellation sent; the service has not returned a run ID.');
    await pause(2000);await request('RunService/StopRun',{runId:step.runId});
    for(let i=0;i<8;i++){
      const value=await request('RunService/GetRun',{runId:step.runId});
      if(['RUN_STATUS_STOPPED','RUN_STATUS_FAILED','RUN_STATUS_SUCCEEDED'].includes(value.run?.status))return {serverCancellation:'confirmed',status:value.run.status};
      await pause(2000);
    }
    throw Error('Local work stopped; server cancellation is still pending.');
  }
  function stop(){
    stopped=true;window.__dshFlowStopRequested=true;log('Stopped locally.');
    if(step?.turnId||step?.runId||step?.submitting){
      remoteStop??=cancelServer().then(result=>{log('Server cancellation: '+result.serverCancellation);return result;})
        .catch(error=>{log(error.message);return {serverCancellation:'unresolved',error:error.message};}).finally(async()=>{try{if(job)job.balanceAfter=await balance();}catch{}endCapture();step=null;});
      return {localStopped:true,serverCancellation:step.turnId||step.runId?'pending':'submission-outcome-unknown'};
    }
    endCapture();return {localStopped:true,serverCancellation:'not-needed'};
  }
  async function follow(item,plan,signal){
    const start=Date.now();
    while(Date.now()-start<240000){
      await pause(2500,signal);target(plan);
      const value=await request('RunService/ListCanvasRuns',{canvasId:plan.canvasId},signal);
      item.runId=value.runs?.find(r=>r.turnId===item.turnId)?.runId||item.runId;
      if(item.runId){
        const detail=await request('RunService/GetRun',{runId:item.runId},signal);item.serverStatus=detail.run?.status;
        if(item.serverStatus==='RUN_STATUS_SUCCEEDED')return;
        if(['RUN_STATUS_FAILED','RUN_STATUS_STOPPED'].includes(item.serverStatus))throw Error('Run ended: '+item.serverStatus);
      }
      const listing=templates.get('SessionService/ListTurns');
      if(listing?.projectId===project()){
        const turns=await request('SessionService/ListTurns',listing.body,signal),turn=turns.turns?.find(t=>t.turnId===item.turnId);
        if(turn?.requestId&&turn.requestId!==item.continuedRequest){
          await pause(2000,signal);target(plan);
          await request('TurnService/ContinueTurn',{requestId:turn.requestId,selectedOptionIds:item.selectedOptionIds||[],turnId:item.turnId},signal);item.continuedRequest=turn.requestId;
        }
      }
    }
    throw Error('Run timed out after four minutes.');
  }
  async function run(args,signal){
    if(step?.runId||step?.submitting)throw Error('A submitted task is still tracked. Use waitTask or STOP.');
    const plan=parse(args.plan)||{},current=target(plan);
    plan.projectId=current.projectId;plan.canvasId=current.canvasId;
    plan.steps??=[{id:'state',kind:'capture'}];
    if(!Array.isArray(plan.steps))throw Error('Plan steps must be an array.');
    if(args.dryRun!==false)return {mode:'dry-run',networkRequestsSent:0,plan:clean(plan),predictedCredits:plan.steps.reduce((n,s)=>n+(s.kind==='prompt'&&s.costClass==='hd-model'?40:0),0),priceBasis:'Historical observed samples; not a quote or spending cap.'};
    stopped=false;remoteStop=null;job={plan:clean(plan),steps:[],balanceBefore:await balance(signal)};
    try{
      for(const item of plan.steps){
        if(signal.aborted)throw Error('Stopped');target(plan);
        step={...item,status:'running',startedAt:Date.now()};job.steps.push(step);log('Running '+(item.id||item.kind));
        if(item.kind==='capture')step.result=await readCanvas(plan,signal);
        else if(['inspectGlb','exportGlb'].includes(item.kind))step.result=await assetOutput(item,plan,signal);
        else if(item.kind==='prompt'){
          const template=templates.get('SessionService/CreateTurn');
          if(!template||template.projectId!==project()||conversation?.projectId!==project())throw Error('Capture a native task request on this canvas before replaying prompts.');
          const body={...template.body,...conversation.body,text:item.text,nodeId:item.nodeId||'',attachmentIds:[]};
          step.submitting=true;const result=await request('SessionService/CreateTurn',body,signal);step.submitting=false;step.turnId=result.turnId;
          if(!step.turnId)throw Error('The service did not return a task ID.');await follow(step,plan,signal);
        }else if(item.kind==='saveCanvas'){
          const body=parse(item.body);if(body?.canvasId!==current.canvasId)throw Error('Save body must target the open canvas.');
          step.result=await request('CanvasService/SaveCanvas',body,signal);
        }else throw Error('Unknown step: '+item.kind);
        step.status='done';step.elapsedMs=Date.now()-step.startedAt;log('Done '+(item.id||item.kind));step=null;
        if(plan.steps.indexOf(item)+1<plan.steps.length)await pause(2000,signal);
      }
    }catch(error){
      if(step){step.status=signal.aborted?'stopped':'failed';step.error=error.message;}
      if(step?.turnId&&!remoteStop)stop();throw error;
    }finally{
      if(remoteStop)await remoteStop;
      if(job.balanceAfter===undefined){try{job.balanceAfter=await balance();}catch{job.balanceAfter=null;}}
      job.endedAt=new Date().toISOString();step=null;
    }
    return clean(job);
  }
  const clone=value=>JSON.parse(JSON.stringify(value));
  const extraActions=['createCanvas','uploadAsset','createNode','connectNodes','generate','waitTask','saveCanvas','autoLayout',...window.__dshUiActions.nativeActions,...window.__dshLabOperations.actions];
  const downloads=window.__dshArtifactDownload.create({window,location,crypto,fetch:(...args)=>(originalFetch||window.fetch)(...args),write,pause,onProgress:p=>log('Artifact download progress',p)});
  const uiActions=window.__dshUiActions.create({document,location,pause,downloads});
  let artifactStore;
  const journal=()=>{if(!window.DshDurableState)throw Error('Durable publication storage is unavailable; no mutation sent.');return artifactStore??=window.DshDurableState.create();};
  function observedPorts(){
    const observed={};
    for(const n of document.querySelectorAll('.vue-flow__node[data-id]')){
      const entry={source:[],target:[]};for(const h of n.querySelectorAll('[data-handleid]')){const side=h.classList.contains('source')?'source':h.classList.contains('target')?'target':null;if(side)entry[side].push(h.getAttribute('data-handleid'));}observed[n.getAttribute('data-id')]=entry;
    }
    return observed;
  }
  const labOperations=window.__dshLabOperations.create({ready:awaitContext,target,read:readCanvas,draft,save,request,planners:window.__dshCanvasAssets,observedPorts,uuid:()=>crypto.randomUUID(),load:key=>journal().load(key),persist:(key,v)=>journal().save(key,v),readBytes:downloads.readBytes,download:downloads.download,validateBytes:downloads.validateBytes,importBytes:importArtifactBytes});
  function nativeTemplate(operation){
    const entry=templates.get(operation);
    if(!entry?.body)throw Error('Native '+operation+' request not captured.');
    return clone(entry.body);
  }
  function draft(args){
    const current=target(args),observed=templates.get('CanvasService/SaveCanvas')?.body;
    const body=parse(args.body)||{canvasId:current.canvasId,clientId:observed?.clientId||crypto.randomUUID(),nodes:canvas.nodes.map(n=>Object.fromEntries(Object.entries(n).filter(([k])=>['id','pid','type','name','params','ui','inputMount','nodeAssets','displayNo','batchId','extraction'].includes(k)))),edges:canvas.edges};
    body.revision=current.revision;
    if(body.canvasId!==current.canvasId)throw Error('Save body must target the open canvas.');
    if(!Array.isArray(body.nodes)||!Array.isArray(body.edges))throw Error('Save body needs nodes and edges arrays.');
    return clone(body);
  }
  async function save(body,signal){
    target({canvasId:body.canvasId});
    const result=await request('CanvasService/SaveCanvas',body,signal);
    // One read obtains the server revision for the next edit; no equality proof.
    const latest=await readCanvas({canvasId:body.canvasId},signal);
    templates.set('CanvasService/SaveCanvas',{projectId:project(),body:{...body,revision:latest.canvas.revision}});
    return result;
  }
  function editedDraft(name,args){
    const body=draft(args);
    if(name==='createNode'){
      const base=args.nodeTemplate||body.nodes.find(n=>n.type===args.type)||contracts.nodes.find(n=>n.type===args.type);
      if(!base)throw Error('No captured node of this type. Supply nodeTemplate from a native save.');
      const node={...clone(base),id:crypto.randomUUID(),type:args.type||base.type,params:parse(args.params)||{}};
      node.name=args.name||base.name;node.inputMount=clone(args.inputMount||[]);node.nodeAssets=[];
      node.ui={...node.ui,position:args.position||{x:0,y:0}};
      delete node.pid;node.displayNo='#'+(body.nodes.length+1);body.nodes.push(node);return {body,nodeId:node.id};
    }
    if(name==='connectNodes'){
      const observed={};
      for(const n of document.querySelectorAll('.vue-flow__node[data-id]')){
        const entry={source:[],target:[]};for(const h of n.querySelectorAll('[data-handleid]')){const side=h.classList.contains('source')?'source':h.classList.contains('target')?'target':null;if(side)entry[side].push(h.getAttribute('data-handleid'));}observed[n.getAttribute('data-id')]=entry;
      }
      return window.__dshCanvasAssets.connect(body,{...args,edgeId:crypto.randomUUID()},observed);
    }
    if(name==='generate'){
      const node=body.nodes.find(n=>n.id===args.nodeId);
      const fixedTypes=['NODE_TYPE_GENERATE_IMAGE','NODE_TYPE_GENERATE_SM_MODEL','NODE_TYPE_GENERATE_HD_MODEL','NODE_TYPE_TEXTURE','NODE_TYPE_RIGGING','NODE_TYPE_SMART_UV'];
      if(!node||!fixedTypes.includes(node.type))throw Error('Choose a fixed pipeline node on the open canvas. AI 3D Lab uses its native conversation.');
      node.params={...node.params,...parse(args.params)};
      for(const key of ['amount','scale','t_pose','sketch_to_render','prompt'])if(args[key]!==undefined)node.params[key]=args[key];
      if(args.model!==undefined)node.params.model_version=args.model;
      const runBody=clone(templates.get('RunService/CreateRun')?.body||contracts.runBody);
      const runIdField=templates.get('RunService/CreateRun')?.runIdField||contracts.runIdField;
      runBody.canvasId=body.canvasId;runBody.nodeIds=[node.id];runBody.idempotencyKey=crypto.randomUUID();
      return {body,runBody,runIdField,nodeId:node.id};
    }
    return {body};
  }
  async function waitTask(args,signal){
    const current=target(args),runId=args.runId||step?.runId;
    if(!runId)throw Error('waitTask needs the runId returned by generate.');
    if(step?.runId&&step.runId!==runId)throw Error('Another submitted task is still being tracked.');
    const timeout=Number(args.timeoutMs??240000);
    if(!Number.isFinite(timeout)||timeout<=0)throw Error('timeoutMs must be positive.');
    const started=Date.now();
    while(Date.now()-started<timeout){
      target(args);
      const value=await request('RunService/GetRun',{runId},signal),run=value.run;
      if(run?.canvasId!==current.canvasId)throw Error('Task does not belong to the open canvas.');
      step??={runId,status:'waiting'};job??={plan:{canvasId:current.canvasId},steps:[step]};
      if(['RUN_STATUS_SUCCEEDED','RUN_STATUS_FAILED','RUN_STATUS_STOPPED'].includes(run.status)){
        const after=await balance(signal);job.balanceAfter=after;
        const before=job.balanceBefore;step=null;
        if(run.status!=='RUN_STATUS_SUCCEEDED')throw Error('Run ended: '+run.status+'; '+(run.steps||[]).map(s=>s.failCode).filter(Boolean).join(', ')+'; balance '+(before??'unknown')+' -> '+after);
        const state=await readCanvas(args,signal);
        const outputs=state.nodes.filter(n=>(run.nodeIds||[]).includes(n.id)).flatMap(n=>n.nodeAssets||[]);
        return {runId,status:run.status,outputs,resultUrl:outputs.find(a=>a.url)?.url||null,balanceBefore:before??null,balanceAfter:after,observedDebit:Number.isFinite(before)?before-after:null};
      }
      await pause(2500,signal);
    }
    throw Error('Task is still running after the timeout. Call waitTask again or STOP.');
  }
  async function uploadAsset(args,signal){
    const current=target(args);
    if(step?.runId||step?.submitting)throw Error('A submitted task is still tracked. Use waitTask or STOP.');
    const filename=args.filename||'input.png',mime=args.mime||'image/png';
    if(!filename.toLowerCase().endsWith('.png')||mime!=='image/png')throw Error('This captured upload contract supports PNG files.');
    if(!args.sourceUrl&&!args.base64&&!args.bytes)throw Error('uploadAsset needs sourceUrl, base64, or bytes.');
    if(args.dryRun!==false)return {mode:'dry-run',networkRequestsSent:0,filename,mime,operations:['temporary_token','S3 PUT','AssetService/ImportInputAssets'],predictedCredits:0,priceBasis:'Native upload observed at unchanged balance.'};
    let body;
    if(args.sourceUrl){
      const response=await (originalFetch||window.fetch)(args.sourceUrl,{credentials:'omit',signal});
      if(!response.ok)throw Error('Input image download failed: HTTP '+response.status);
      body=await response.arrayBuffer();
    }else if(args.base64){body=Uint8Array.from(atob(args.base64),c=>c.charCodeAt(0)).buffer;}
    else body=new Uint8Array(args.bytes).buffer;
    if(!body.byteLength)throw Error('Input image is empty.');
    const observed=storageRead||paymentRead;
    if(!observed)throw Error('Capture and reload the canvas to observe Studio authentication.');
    const headers=new Headers(observed.headers);headers.set('content-type','application/json');
    const before=await balance(signal);target(args);
    log('Upload started',{filename,mime,bytes:body.byteLength,balanceBefore:before});
    let ticket;
    try{
      const result=await json(await (originalFetch||window.fetch)(storageToken,{method:'POST',headers,credentials:observed.credentials,body:JSON.stringify({client:'aws',format:'png'}),signal}));
      if(result.code)throw Error('Temporary storage ticket failed: '+result.message);
      ticket=result.data;
      await pause(2000,signal);target(args);
      const transfer=await window.__dshStorage.upload({ticket,body,mime,fetch:originalFetch||window.fetch,signal});
      log('Storage upload completed',transfer);
      await pause(2000,signal);target(args);
      const imported=await request('AssetService/ImportInputAssets',{objectRefs:[{contentType:mime,originalFilename:filename,resourceUri:ticket.resource_uri,sizeBytes:String(body.byteLength)}],projectId:current.projectId},signal);
      const asset=imported.assets?.[0];
      if(!asset?.assetId)throw Error('ImportInputAssets returned no asset ID.');
      const after=await balance(signal);
      const resultValue={...asset,balanceBefore:before,balanceAfter:after,observedDebit:before-after};
      log('Upload imported',resultValue);return resultValue;
    }finally{ticket=null;body=null;}
  }

  async function autoLayout(args,signal){
    await awaitContext(signal);
    const restore=parse(args.inverse);target(restore||args);
    const state=await readCanvas(args,signal),dimensions={};
    // offsetWidth/Height are unscaled CSS dimensions, independent of canvas zoom.
    for(const article of document.querySelectorAll('article')){
      const id=article.closest('[data-id]')?.getAttribute('data-id');
      if(id&&article.offsetWidth>0&&article.offsetHeight>0)dimensions[id]={width:article.offsetWidth,height:article.offsetHeight};
    }
    const plan=restore||window.__dshAutoLayout.plan(state,{...args,dimensions});
    if(!Array.isArray(plan.changes))throw Error('Layout inverse needs a changes array.');
    const body=draft({}),original=new Map(body.nodes.map(n=>[n.id,n]));
    const inverse={canvasId:body.canvasId,changes:[]},changed=[],seen=new Set();
    for(const change of plan.changes){
      const n=original.get(change.nodeId),p=change.position;
      if(seen.has(change.nodeId))throw Error('Layout contains a duplicate node ID.');seen.add(change.nodeId);
      if(!n||!Number.isFinite(p?.x)||!Number.isFinite(p?.y))throw Error('Layout needs existing node IDs and finite positions.');
      if(change.size!==undefined&&change.size!==null&&(!Number.isFinite(change.size.width)||!Number.isFinite(change.size.height)||change.size.width<=0||change.size.height<=0))throw Error('Section sizes must be positive.');
      inverse.changes.push({nodeId:n.id,position:clone(n.ui?.position||{x:0,y:0}),...(change.size!==undefined?{size:n.ui?.size??null}:{})});
      const differs=n.ui?.position?.x!==p.x||n.ui?.position?.y!==p.y||(change.size!==undefined&&JSON.stringify(n.ui?.size??null)!==JSON.stringify(change.size));
      n.ui={...n.ui,position:p,...(change.size!==undefined?{size:change.size}:{})};if(differs)changed.push(n.id);
    }
    const result={mode:args.dryRun===false?'apply':'dry-run',canvasId:body.canvasId,changes:plan.changes,inverse,changedNodes:changed.length,metrics:plan.metrics,warnings:plan.warnings||[],geometryBasis:'Rendered card dimensions where available; stored sizes or 303px fallback elsewhere. Metrics describe the plan.',mutatingRequestsSent:0};
    if(args.dryRun!==false){log('Auto-layout preview',result);return result;}
    result.balanceBefore=await balance(signal);
    if(changed.length){await pause(2000,signal);await save(body,signal);result.mutatingRequestsSent=1;}
    result.balanceAfter=await balance(signal);result.revision=canvas.canvas.revision;result.reloadRequired=changed.length>0;
    log('Auto-layout '+(changed.length?'saved':'already arranged'),result);return result;
  }

  async function importArtifactBytes(bytes,spec,signal,args){
    const current=target(args),observed=storageRead||paymentRead;
    if(!observed)throw Error('Native storage authentication is unavailable.');
    if(!['glb','png'].includes(spec.format))throw Error('Unsupported Lab publication format.');
    const headers=new Headers(observed.headers);headers.set('content-type','application/json');let ticket;
    try{
      const result=await json(await (originalFetch||window.fetch)(storageToken,{method:'POST',headers,credentials:observed.credentials,body:JSON.stringify({client:'aws',format:spec.format}),signal}));
      if(result.code)throw Error('Temporary storage ticket failed: '+result.message);ticket=result.data;target(args);
      await window.__dshStorage.upload({ticket,body:bytes,mime:spec.mime,fetch:originalFetch||window.fetch,signal});target(args);
      const imported=await request('AssetService/ImportInputAssets',{objectRefs:[{contentType:spec.mime,originalFilename:spec.filename,resourceUri:ticket.resource_uri,sizeBytes:String(bytes.byteLength)}],projectId:current.projectId},signal);
      const asset=imported.assets?.[0];if(!asset?.assetId)throw Error('ImportInputAssets returned no asset ID; outcome unknown.');return asset;
    }finally{ticket=null;}
  }

  async function shortcut(name,args,signal){
    stopped=false;
    if(window.__dshLabOperations.actions.includes(name)){
      if(args.dryRun===false&&['setLabInput','publishLabArtifact'].includes(name)&&(step?.runId||step?.submitting))throw Error('A submitted task is still tracked. Use waitTask or STOP.');
      return labOperations.run(name,args,signal);
    }
    if(window.__dshUiActions.nativeActions.includes(name)){
      await awaitContext(signal);target(args);
      const result=await uiActions.run(name,args,signal);log(name,result);return result;
    }
    if(name==='uploadAsset')return uploadAsset(args,signal);
    if(name==='waitTask')return waitTask(args,signal);
    if(step?.runId||step?.submitting)throw Error('A submitted task is still tracked. Use waitTask or STOP.');
    if(name==='autoLayout')return autoLayout(args,signal);
    if(name==='createCanvas'){
      if(args.dryRun!==false)return {mode:'dry-run',networkRequestsSent:0,operation:'ProjectService/CreateProject',body:{},name:args.name||null};
      const result=await request('ProjectService/CreateProject',{},signal);
      const projectId=result.project?.projectId,canvasId=result.canvas?.canvasId;
      if(!projectId||!canvasId)throw Error('CreateProject returned no project/canvas IDs. Inspect the project list before retrying.');
      const created={projectId,canvasId,url:location.origin+'/projects/'+projectId};
      if(args.name){
        await pause(2000,signal);
        try{await request('ProjectService/UpdateProject',{projectId,name:args.name},signal);}catch(e){return {...created,renameError:e.message};}
      }
      return created;
    }
    const edit=editedDraft(name,args);
    if(args.dryRun!==false)return {mode:'dry-run',networkRequestsSent:0,...clean(edit)};
    if(name!=='generate')return {...(edit.changed===false?{changed:false}:await save(edit.body,signal)),nodeId:edit.nodeId,edgeId:edit.edgeId};
    job={plan:{canvasId:edit.body.canvasId},steps:[],balanceBefore:await balance(signal)};
    await save(edit.body,signal);await pause(2000,signal);target(args);
    step={nodeId:edit.nodeId,submitting:true,status:'submitting'};job.steps.push(step);
    try{
      const result=await request('RunService/CreateRun',edit.runBody,signal);
      step.runId=edit.runIdField==='run.runId'?result.run?.runId:result.runId;
      if(!step.runId)throw Error('CreateRun returned no run ID; server outcome is unknown. Do not resubmit blindly.');
      step.submitting=false;step.status='submitted';
      job.balanceAfter=await balance(signal);
      return {runId:step.runId,nodeId:edit.nodeId,balanceBefore:job.balanceBefore,balanceAfter:job.balanceAfter,observedDebit:job.balanceBefore-job.balanceAfter};
    }catch(error){log(error.message);throw error;}
  }

  const api=window.__dshShortcutCore.create({clean,actions:extraActions,
    status:()=>({version,ready:contextReady(),hasRpcAuth:!!auth,hasPaymentAuth:!!paymentRead,stopped,capturing,message,evidencePath,driverDispatches:dispatches,canvasId:canvas?.canvas?.canvasId,steps:job?.steps||[],balance:job?.balanceAfter}),
    stop,
    async invoke(name,args,signal){
      if(signal.aborted)throw Error('Stopped');
      if(name==='capture'){window.__dshObserverControl?.start();capture();sessionStorage.setItem('dsh-capture-until',String(Date.now()+60000));return {capturing:true};}
      if(name==='export')return exportEvidence(signal);
      if(name==='run')return run(args,signal);
      if(extraActions.includes(name))return shortcut(name,args,signal);
      stopped=false;const plan=parse(args.plan)||{};target(plan);const before=await balance(signal);let value;
      for(let i=0;i<(args.count||1);i++){value=await readCanvas(plan,signal);if(i+1<(args.count||1))await pause(2000,signal);}
      const after=await balance(signal);log('Read '+value.nodes.length+' nodes.');return clean({canvas:value,balanceBefore:before,balanceAfter:after});
    }
  });
  window.__dshShortcut=api;
  // Observe native authentication before the site's startup requests. Never persist it.
  capture();
  const markReady=()=>{if(document.documentElement)document.documentElement.dataset.dshDriverReady=version;else setTimeout(markReady,10);};
  markReady();
  document.addEventListener('dsh-shortcut-request',event=>{
    const {id,name,args}=event.detail||{};
    Promise.resolve().then(()=>name==='status'?api.status():name==='actions'?api.actions():api.run(name,parse(args)||{}))
      .then(result=>document.dispatchEvent(new CustomEvent('dsh-shortcut-response',{detail:{id,ok:true,result:clean(result)}})))
      .catch(error=>document.dispatchEvent(new CustomEvent('dsh-shortcut-response',{detail:{id,ok:false,error:clean(error.message)}})));
  });
  document.addEventListener('dsh-tripo-teardown',()=>api.run('stop'));
  if(Number(sessionStorage.getItem('dsh-capture-until'))>Date.now()){sessionStorage.removeItem('dsh-capture-until');capture();}
})();
