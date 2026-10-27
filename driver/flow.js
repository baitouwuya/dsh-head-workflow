// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

/* Durable, append-only DSH state. Bulk data stays in IndexedDB; localStorage holds pointers. */
(function(root){
'use strict';
const DB='dsh-tripo-history-v1',CAP=64000,LOCK='dsh-tripo-durable-writer-v1';
function create(options={}){
 const ls=options.localStorage||root.localStorage,storage=options.storage||root.navigator.storage,locks=options.locks||root.navigator.locks;
 const cryptoApi=options.crypto||root.crypto,encoder=new TextEncoder();
 const sha=async raw=>Array.from(new Uint8Array(await cryptoApi.subtle.digest('SHA-256',encoder.encode(raw))),x=>x.toString(16).padStart(2,'0')).join('');
 const marker=r=>JSON.stringify({dsh:1,r});
 const parseMarker=raw=>{try{const x=JSON.parse(raw);return x?.dsh===1&&/^[a-f0-9]{64}$/.test(x.r)?x:null;}catch{return null;}};
 const id=(key,hash)=>key+'\n'+hash;
 let dbPromise;
 async function database(){if(!dbPromise)dbPromise=new Promise((resolve,reject)=>{const r=(options.indexedDB||root.indexedDB).open(DB,1);r.onupgradeneeded=()=>{const d=r.result;d.createObjectStore('revisions',{keyPath:'id'});d.createObjectStore('heads',{keyPath:'key'});};r.onerror=()=>reject(r.error);r.onblocked=()=>reject(Error('DSH IndexedDB upgrade blocked'));r.onsuccess=()=>{r.result.onversionchange=()=>r.result.close();resolve(r.result);};});return dbPromise;}
 const repository=options.repository||{
  async get(store,key){const db=await database();return new Promise((resolve,reject)=>{const tx=db.transaction(store,'readonly'),r=tx.objectStore(store).get(key);let value;r.onsuccess=()=>{value=r.result;};tx.oncomplete=()=>resolve(value);tx.onerror=()=>reject(tx.error||r.error);tx.onabort=()=>reject(tx.error||Error('IndexedDB read aborted'));});},
  async commit(record,head){const db=await database();return new Promise((resolve,reject)=>{const tx=db.transaction(['revisions','heads'],'readwrite');if(record)tx.objectStore('revisions').add(record);if(head)tx.objectStore('heads').put(head);tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error||Error('IndexedDB commit failed'));tx.onabort=()=>reject(tx.error||Error('IndexedDB commit aborted'));});}
 };
 async function probe(kind,extra={}){
  const estimate=await storage.estimate();
  const keys=[];for(let i=0;i<ls.length;i++){const key=ls.key(i);if(!key?.startsWith('dsh-'))continue;const raw=ls.getItem(key)||'';keys.push({key,characters:raw.length,utf16Bytes:2*(key.length+raw.length)});}
  keys.sort((a,b)=>a.key.localeCompare(b.key));
  const result={at:new Date().toISOString(),kind,estimate:{quota:estimate.quota,usage:estimate.usage,usageDetails:estimate.usageDetails},keys,totalUtf16Bytes:keys.reduce((n,k)=>n+k.utf16Bytes,0),capBytes:CAP,...extra};
  if(!Number.isFinite(estimate.quota)||!Number.isFinite(estimate.usage))throw Error('Storage estimate unavailable; write blocked');
  options.onProbe?.(result);return result;
 }
 async function locked(fn){if(!locks?.request)throw Error('Origin-wide storage lock unavailable; write blocked');return locks.request(LOCK,{mode:'exclusive'},fn);}
 async function verify(key,hash,expected){const r=await repository.get('revisions',id(key,hash));if(!r||r.key!==key||r.sha256!==hash||await sha(r.raw)!==hash||(expected!==undefined&&r.raw!==expected))throw Error('Durable history readback/hash verification failed for '+key);return r;}
 async function archive(key,raw,predecessorLocalRaw=raw){
  const hash=await sha(raw),recordId=id(key,hash),existing=await repository.get('revisions',recordId);
  const current=await repository.get('heads',key);
  if(existing)await verify(key,hash,raw);
  const p=await probe('indexeddb-commit',{key,sha256:hash,newRevision:!existing,rawUtf8Bytes:encoder.encode(raw).length});
  const predecessorLocalSha256=predecessorLocalRaw===null?null:await sha(predecessorLocalRaw);
  const record=existing?null:{id:recordId,key,sha256:hash,raw,createdAt:p.at,priorRevision:current?.revision||null,writeProbe:p};
  const headRecord={key,revision:hash,predecessorLocalSha256,updatedAt:p.at};
  const candidate=JSON.stringify({record,head:headRecord});
  const needed=2*Math.max(encoder.encode(candidate).length,2*candidate.length)+4096;
  if(p.estimate.quota-p.estimate.usage<needed)throw Error('Insufficient estimated IndexedDB space including complete record/probe/head metadata; write blocked for '+key);
  // The revision is immutable. Commit completion is awaited before any pointer changes.
  await repository.commit(record,headRecord);
  await verify(key,hash,raw);
  const head=await repository.get('heads',key);if(head?.revision!==hash)throw Error('Durable head readback failed for '+key);
  return {key,hash,rawCharacters:raw.length,probe:p};
 }
 async function replaceMarker(entry,{migration=false,finalTargetBytes=null}={}){
  const current=ls.getItem(entry.key),replacement=marker(entry.hash);
  if(current===replacement)return {key:entry.key,alreadyMarker:true};
  if(current!==entry.raw)throw Error('Legacy value changed during migration/save; pointer not replaced: '+entry.key);
  await verify(entry.key,entry.hash,entry.raw);
  const p=await probe(migration?'migration-marker-replace':'marker-write',{key:entry.key,sha256:entry.hash});
  const oldBytes=current===null?0:2*(entry.key.length+current.length),newBytes=2*(entry.key.length+replacement.length);
  const projected=p.totalUtf16Bytes-oldBytes+newBytes;
  const shrinking=migration&&current!==null&&newBytes<oldBytes&&projected<p.totalUtf16Bytes&&Number.isFinite(finalTargetBytes)&&finalTargetBytes<CAP;
  if(projected>=CAP&&!shrinking)throw Error('DSH localStorage total would reach/exceed 64000 bytes; marker write blocked');
  if(migration&&!shrinking)throw Error('Migration only permits strictly shrinking verified replacements');
  const step={...p,beforeBytes:p.totalUtf16Bytes,projectedBytes:projected,finalTargetBytes,legacyOverCapReduction:projected>=CAP};
  ls.setItem(entry.key,replacement);
  if(ls.getItem(entry.key)!==replacement)throw Error('Marker persistence readback failed for '+entry.key);
  options.onStep?.(step);return step;
 }
 async function loadRaw(key){
  if(!key.startsWith('dsh-'))throw Error('Only dsh-* state is supported');
  const raw=ls.getItem(key),m=parseMarker(raw),head=await repository.get('heads',key);
  if(head){
   if(raw!==null){const localHash=await sha(raw);if((!m&&localHash!==head.revision&&localHash!==head.predecessorLocalSha256)||(m&&m.r!==head.revision&&localHash!==head.predecessorLocalSha256))throw Error('Legacy state conflict: local value is not the committed revision or its verified predecessor; history retained: '+key);}
   return (await verify(key,head.revision)).raw;
  }
  if(m)return (await verify(key,m.r)).raw;
  return raw;
 }
 async function saveRaw(key,raw){
  if(!key.startsWith('dsh-')||typeof raw!=='string')throw Error('State key/value invalid');
  return locked(async()=>{
   const p=await probe('save-preflight',{key});if(p.totalUtf16Bytes>=CAP)throw Error('Legacy DSH footprint exceeds cap; complete verified migration before ordinary writes');
   const old=ls.getItem(key),newHash=await sha(raw),plannedMarker=marker(newHash);
   const plannedTotal=p.totalUtf16Bytes-(old===null?0:2*(key.length+old.length))+2*(key.length+plannedMarker.length);
   if(plannedTotal>=CAP)throw Error('DSH marker footprint would reach/exceed 64000 bytes; no durable head commit');
   const saved=await archive(key,raw,old);
   // IDB may be newer than the small pointer after an interrupted marker write; loadRaw uses its verified head.
   const entry={key,hash:saved.hash,raw:old};
   const replacement=marker(saved.hash),beforeMarker=await probe('marker-write',{key,sha256:saved.hash});
   const projected=beforeMarker.totalUtf16Bytes-(old===null?0:2*(key.length+old.length))+2*(key.length+replacement.length);
   if(projected>=CAP)throw Error('DSH marker footprint would reach/exceed 64000 bytes; write blocked');
   if(ls.getItem(key)!==old)throw Error('Concurrent legacy writer changed key; marker not replaced');
   ls.setItem(key,replacement);if(ls.getItem(key)!==replacement)throw Error('Marker readback failed');
   options.onStep?.({...beforeMarker,projectedBytes:projected});return {key,revision:saved.hash,markerBytes:2*(key.length+replacement.length),totalUtf16Bytes:projected};
  });
 }
 async function migrate({stageOnly=false}={}){return locked(async()=>{
  const initial=await probe('migration-plan'),entries=[];
  for(const x of initial.keys){const raw=ls.getItem(x.key),m=parseMarker(raw);if(m){await verify(x.key,m.r);continue;}const hash=await sha(raw);entries.push({key:x.key,raw,hash});}
  // Tiny operational values that cannot shrink remain unchanged; they are also archived in full.
  const replacements=entries.filter(e=>marker(e.hash).length<e.raw.length);
  const byKey=new Map(replacements.map(e=>[e.key,marker(e.hash)]));
  const finalTargetBytes=initial.keys.reduce((sum,x)=>sum+2*(x.key.length+(byKey.has(x.key)?byKey.get(x.key).length:x.characters)),0);
  if(finalTargetBytes>=CAP)throw Error('Complete marker set cannot fit below 64000 bytes; no migration writes made');
  const copied=[];for(const e of entries){await archive(e.key,e.raw);copied.push({key:e.key,sha256:e.hash,rawCharacters:e.raw.length});}
  // Verify ALL immutable copies before replacing ANY localStorage value.
  for(const e of entries)await verify(e.key,e.hash,e.raw);
  if(stageOnly)return {database:DB,status:'all-copies-verified-no-markers-replaced',initial,finalTargetBytes,copied,historyDeleted:false,historyCompressed:false};
  const steps=[];for(const e of replacements)steps.push(await replaceMarker(e,{migration:true,finalTargetBytes}));
  const final=await probe('migration-complete');if(final.totalUtf16Bytes>=CAP)throw Error('Migration incomplete: aggregate is still over cap; durable history retained');
  return {database:DB,status:'complete',initial,final,finalTargetBytes,copied,steps,historyDeleted:false,historyCompressed:false};
 });}
 return {database:DB,capBytes:CAP,probe,loadRaw,load:async key=>{const raw=await loadRaw(key);return raw===null?null:JSON.parse(raw);},saveRaw,save:(key,value)=>saveRaw(key,JSON.stringify(value)),migrate,readRevision:async(key,hash)=>(await verify(key,hash)).raw};
}
function showFailure({key,error,jobId=null,requestState='unknown',storage=true}){
 if(!root.document?.body)return;
 const proof={at:new Date().toISOString(),key,error,jobId,requestState,storage};
 root.document.body.dataset.dshPersistenceError=JSON.stringify(proof);
 root.document.getElementById('dsh-storage-error')?.remove();
 const box=root.document.createElement('div');box.id='dsh-storage-error';box.setAttribute('role','alert');
 box.style.cssText='position:fixed;left:20px;bottom:20px;max-width:680px;padding:14px;background:#4a1515;color:#fff;border:2px solid #ff9a9a;z-index:2147483647;font:14px sans-serif;white-space:pre-wrap';
 const status=jobId?'Known job '+jobId+'. Monitor/resume that ID; this error does not confirm cancellation.':requestState==='not-sent'?'No new request was sent. Fix persistence before the next mutation.':'Mutation outcome unknown. Inspect native canvas/job history; no automatic retry.';
 const text=root.document.createElement('div');text.textContent=(storage?'DSH storage error':'DSH flow paused')+'\nKey: '+key+'\n'+error+'\n'+status;box.appendChild(text);
 const close=root.document.createElement('button');close.textContent='Dismiss';close.onclick=()=>box.remove();box.appendChild(close);root.document.body.appendChild(box);
}
root.DshDurableState={create,database:DB,capBytes:CAP,showFailure};
if(typeof module!=='undefined'&&module.exports)module.exports=root.DshDurableState;
})(typeof window!=='undefined'?window:globalThis);

if (!window.__dshUiActions) {
(function(root){
  'use strict';
  const nativeActions=['selectNode','labExportDialog'];
  const reviewActions=['labTestAllControls','labMeasureAllMorphs'];
  function create({document,location,pause}){
    const wait=pause||((ms,signal)=>new Promise((resolve,reject)=>{
      const cancel=()=>{clearTimeout(timer);reject(Error('Stopped'));};
      const timer=setTimeout(()=>{signal?.removeEventListener('abort',cancel);resolve();},ms);
      if(signal?.aborted)cancel();else signal?.addEventListener('abort',cancel,{once:true});
    }));
    async function run(name,args={},signal){
      if(![...nativeActions,...reviewActions].includes(name))throw Error('Unknown UI action: '+name);
      if(!args||typeof args!=='object'||Array.isArray(args))throw Error('UI action arguments must be an object.');
      const timeout=Number(args.timeoutMs??60000),opened=location.origin+location.pathname,start=Date.now();
      if(!Number.isFinite(timeout)||timeout<=0||timeout>120000)throw Error('timeoutMs must be between1 and120000.');
      let domClicks=0,keyEvents=0,hoverEvents=0;
      const check=()=>{if(signal?.aborted)throw Error('Stopped');if(location.origin+location.pathname!==opened)throw Error('The open page changed.');};
      const until=async(fn,label)=>{while(true){check();const value=fn();if(value)return value;if(Date.now()-start>=timeout)throw Error('Timed out waiting for '+label+'. No retry was sent.');await wait(80,signal);}};
      const click=element=>{check();if(!element||element.disabled)throw Error('Requested native control is unavailable or disabled.');domClicks++;element.click();};
      const result=value=>({...value,domClicks,keyEvents,hoverEvents,elapsedMs:Date.now()-start});
      check();
      if(reviewActions.includes(name)){
        const kind=name==='labTestAllControls'?'testResult':'morphTests';
        const label=name==='labTestAllControls'?'Test all controls':'Measure all morphs';
        const button=document.querySelector('#test');
        if(!button||button.textContent.trim()!==label)throw Error(label+' is available in its DSH local review companion, not in the native Studio Lab panel.');
        if(args.dryRun!==false)return result({mode:'dry-run',surface:'local-review',action:name,button:label,uiEventsSent:0});
        await until(()=>{if(document.body.dataset.error)throw Error(document.body.dataset.error);return document.body.dataset.ready==='true';},'the local model');
        const prior=document.body.dataset[kind];delete document.body.dataset[kind];
        try{
          click(button);
          const values=JSON.parse(await until(()=>document.body.dataset[kind],label+' results'));
          if(!Array.isArray(values))throw Error('The review page returned an unexpected result.');
          return result({mode:'apply',surface:'local-review',action:name,measurementKind:kind==='testResult'?'uv-atlas-controls':'geometric-morph-displacement',results:values,limits:'This repeats the existing review calculation; it does not establish visual or anatomical quality.'});
        }catch(error){if(prior!==undefined&&!document.body.dataset[kind])document.body.dataset[kind]=prior;throw error;}
      }
      if(location.origin!=='https://studio.tripo3d.ai'||!/^\/projects\/[^/]+/.test(location.pathname))throw Error('Open a Studio canvas for this action.');
      if(typeof args.nodeId!=='string'||!args.nodeId)throw Error('nodeId is required.');
      const currentNode=()=>[...document.querySelectorAll('.vue-flow__node[data-id]')].find(n=>n.getAttribute('data-id')===args.nodeId);
      const node=currentNode();
      if(!node)throw Error('The node is not rendered on the open canvas.');
      const selected=()=>currentNode()?.classList.contains('selected');
      const title=node.querySelector('h3');
      const select=async()=>{if(!selected()){click(title);await until(selected,'node selection');}};
      if(name==='selectNode'){
        if(args.dryRun!==false)return result({mode:'dry-run',surface:'studio',nodeId:args.nodeId,selected:selected(),uiEventsSent:0});
        await select();return result({mode:'apply',surface:'studio',nodeId:args.nodeId,selected:true});
      }
      if(!node.querySelector('.forge3d-lab-node-state'))throw Error('Choose an AI 3D Lab node.');
      const operation=args.operation||'open';
      if(!['open','read','close'].includes(operation))throw Error('labExportDialog operation must be open, read or close. Export submission is not part of this action.');
      const dialog=()=>document.querySelector('[role="dialog"][aria-label="Export"]');
      if(args.dryRun!==false)return result({mode:'dry-run',surface:'studio',nodeId:args.nodeId,operation,selected:selected(),dialogOpen:!!dialog(),uiEventsSent:0});
      if(operation==='open'){
        if(dialog()&&!selected())throw Error('Another node has an export dialog open. Close it first.');
        await select();
        if(!dialog()){
          const Mouse=document.defaultView?.MouseEvent||root.MouseEvent,card=currentNode()?.querySelector('article');
          if(!Mouse||!card)throw Error('The selected Lab card is unavailable.');
          check();hoverEvents++;card.dispatchEvent(new Mouse('mouseenter',{bubbles:false,cancelable:false,view:document.defaultView}));
          click(await until(()=>currentNode()?.querySelector('button[aria-label="Export"]'),'the selected Lab export control'));
        }
        await until(()=>dialog()&&!/Loading\.\.\./.test(dialog().textContent),'export options');
      }else if(!selected())throw Error('The requested node is not the selected export owner.');
      if(operation==='close'){
        if(dialog()){
          check();const Key=document.defaultView?.KeyboardEvent||root.KeyboardEvent;
          if(!Key)throw Error('Keyboard events are unavailable on this page.');
          keyEvents++;dialog().dispatchEvent(new Key('keydown',{key:'Escape',code:'Escape',keyCode:27,which:27,bubbles:true,cancelable:true}));
          await until(()=>!dialog(),'export dialog closure');
        }
        return result({mode:'apply',surface:'studio',nodeId:args.nodeId,operation,dialogOpen:false,exportSubmitted:false});
      }
      const d=dialog();if(!d)throw Error('No export dialog is open for the selected node.');
      const combos=[...d.querySelectorAll('[role="combobox"]')],switches=[...d.querySelectorAll('[role="switch"]')];
      return result({mode:'apply',surface:'studio',nodeId:args.nodeId,operation,dialogOpen:true,exportSubmitted:false,options:{filename:d.querySelector('input')?.value??null,format:combos[0]?.textContent.trim()??null,textureResolution:combos[1]?.textContent.trim()??null,exportSkeleton:switches[0]?.getAttribute('aria-checked')==='true',packUv:switches[1]?.getAttribute('aria-checked')==='true'}});
    }
    return Object.freeze({run});
  }
  const api={create,nativeActions,reviewActions,actions:[...nativeActions,...reviewActions]};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else Object.defineProperty(root,'__dshUiActions',{value:api});
})(typeof window==='undefined'?globalThis:window);

}
(() => {
 'use strict';
 const base=window.__dshShortcut,U=window.__dshUiActions;
 if(!base||!U||U.nativeActions.every(n=>base.actions().includes(n)))return;
 const clean=window.__dshTripoSanitize.contract,ui=U.create({document,location});
 const extra=window.__dshShortcutCore.create({actions:U.nativeActions,clean,
   status:()=>({surface:'studio-ui'}),stop:()=>({stopped:true}),
   async invoke(name,args,signal){
     const opened=location.pathname,start=Date.now();
     while(!base.status().ready){
       if(signal.aborted)throw Error('Stopped');
       if(location.pathname!==opened)throw Error('The open canvas changed.');
       if(Date.now()-start>30000)throw Error('Canvas startup did not finish within30 seconds.');
       await new Promise(r=>setTimeout(r,80));
     }
     if(args.canvasId&&args.canvasId!==base.status().canvasId)throw Error('The action must target the open canvas.');
     if(args.projectId&&args.projectId!==location.pathname.split('/')[2])throw Error('The action must target the open project.');
     return ui.run(name,args,signal);
   }
 });
 const facade=Object.freeze({
   actions:()=>[...base.actions(),...U.nativeActions],
   status:()=>({...base.status(),version:'0.2.58',baseDriverVersion:base.status().version,uiRuntime:'flow-loader',active:extra.status().active||base.status().active,lastActions:[...base.status().lastActions,...extra.status().lastActions].sort((a,b)=>a.at.localeCompare(b.at)).slice(-12)}),
   run(name,args={}){
     if(name==='stop')return extra.run('stop').then(()=>base.run('stop'));
     if(U.nativeActions.includes(name)){if(base.status().active)return Promise.reject(Error('An action is running. Use STOP to cancel it.'));return extra.run(name,args);}
     if(extra.status().active)return Promise.reject(Error('An action is running. Use STOP to cancel it.'));
     return base.run(name,args);
   }
 });
 window.__dshShortcut=facade;
 document.addEventListener('dsh-tripo-teardown',()=>extra.run('stop'));
 document.addEventListener('dsh-shortcut-request',event=>{
   const {id,name,args}=event.detail||{};
   if(!['status','actions','stop',...U.nativeActions].includes(name))return;
   // Route new actions before the older event handler can reject their names.
   event.stopImmediatePropagation();
   Promise.resolve().then(()=>name==='status'?facade.status():name==='actions'?facade.actions():facade.run(name,typeof args==='string'?JSON.parse(args):args||{}))
     .then(result=>document.dispatchEvent(new CustomEvent('dsh-shortcut-response',{detail:{id,ok:true,result:clean(result)}})))
     .catch(error=>document.dispatchEvent(new CustomEvent('dsh-shortcut-response',{detail:{id,ok:false,error:clean(error.message)}})));
 },true);
 document.documentElement.dataset.dshUiRuntime='0.2.58';
})();

(()=>{if(location.origin!=="https://studio.tripo3d.ai")return;const records=[{"key":"dsh-auto-layout-proof-0.2.55","sha256":"6832948e324675d8ad00c07f2d7d929e036d121d863f43d13dacbe0792491f19","rawCharacters":22156},{"key":"dsh-autonomous-reconstruction-scaffold-001","sha256":"74a93cccc0bea6afe96f82732b70918a817f56943dd5cca4ebbb6349f49468c3","rawCharacters":24870},{"key":"dsh-avatar-fixed-v1","sha256":"422490add6ef9707abeb58eac2fc26bc01ea8453557673ab594649ff39c2f057","rawCharacters":34773},{"key":"dsh-avatar-handoff-final-layout-20261023","sha256":"228ff6d1aca1b7ce4a6227b819b22c197bfbb586f2bf80271ce4e29a73e50534","rawCharacters":47871},{"key":"dsh-avatar-handoff-lab-editor-diagnosis-1","sha256":"31cb18d03cd13bacfbdf55355571f95cdfb217ba6c35f12c197c0cb4aff2f1f6","rawCharacters":163615},{"key":"dsh-avatar-handoff-resume-observe-20261023","sha256":"0be2fda9fd1ddc2da617aba2353d9400826f5ecf553760532a5a992cf340b4ae","rawCharacters":38719},{"key":"dsh-avatar-handoff-source-post-20261023","sha256":"a3846feda29019e17e412afc5139901b30985dd277ea479ede7e879b123688ce","rawCharacters":155575},{"key":"dsh-avatar-local-inputs-v1","sha256":"275225a8ea537653fbbd123d9dad4f66e2e5b83aafdaee9a453b88187f92df6b","rawCharacters":15830},{"key":"dsh-blink-jaw-append-1792846746009","sha256":"d5e1bbfefe441e8c2656c5ea8f06e287eb1f82064587ed267601454012ac433a","rawCharacters":318226},{"key":"dsh-blink-ui-restore-v1","sha256":"1224aa620f179aad62998f9310c6ea05f3d6648e283d12e2273e36594a5b3251","rawCharacters":319580},{"key":"dsh-first-click-0.2.56","sha256":"3279dbcf2bd3a906e831371ff85207257572b633ee5c597557c80707f6cbf0c3","rawCharacters":10500},{"key":"dsh-flow:body-clothes-hair-v1-20261023","sha256":"8822eb8004b3098682285da134ede7edda18a44c7a9a6715029294817b3f87c7","rawCharacters":13965},{"key":"dsh-flow:dsh-avatar-production-v1","sha256":"bb8d7eca05cf37a44dafdcd3b00e98350fc1f6fce51edaa9741cb2f6aa9f60df","rawCharacters":1429},{"key":"dsh-flow:tpose-api-proof-v053-20261023","sha256":"d4e6a23808e4b9144eb6ff0c04f4103da0ae206b957beef825506a5751342c4d","rawCharacters":731},{"key":"dsh-flow:tpose-api-proof-v054-20261023","sha256":"f275146f1340e27e5269819ab68880bd67b1eba5e2801485a70b27bb5ce7f1b2","rawCharacters":2599},{"key":"dsh-head-lab-params-fix-v2","sha256":"f748dfe7e72e2960c7fcdaaa53b2792319102cf01f4a0026a96736023fe073cb","rawCharacters":163622},{"key":"dsh-native-save-holds-v1","sha256":"676af219ba6e581e44d78d65f2f6902160ee0c5d61d4cdd9352d23be67055ab2","rawCharacters":79},{"key":"dsh-original-head-append-v2","sha256":"ec30772ffd5091ad4c4d55f306c498646a9056a0430b065ec1f7d1a32abe6e54","rawCharacters":77794},{"key":"dsh-original-head-append-v2-writer-retry-1","sha256":"6192cb63e6866127def4486a39ef1c0ea05d4cb6cb1bf7377cae8f618629ebeb","rawCharacters":229097},{"key":"dsh-original-lab-blink-jaw-1792846746009-live-1","sha256":"9be64a07110abf555e0c8211293e9d3c5d8bdbd8bade5a69847b78fc3786d3be","rawCharacters":189854},{"key":"dsh-original-lab-blink-jaw-1792846746009-live-2","sha256":"f1a2bd80722072545d4f1c6eac64d2d5d4187b700960c8c3b2b4a92dda1f4392","rawCharacters":281601},{"key":"dsh-original-lab-expressions-live-1","sha256":"0b2e05e31515a6f86af4650b72fe9595875ff6be77683c57071b8a4b5b204f10","rawCharacters":179614},{"key":"dsh-original-lab-final-live-1","sha256":"207cef6df5ca357842c0862c970766748ff8a750b253fb4048eb8a4541f44100","rawCharacters":192499},{"key":"dsh-original-lab-garment-live-1","sha256":"0ccdc48207fcec22f6484ff9804e6cdee0b92561694f85d0522540ae68a57859","rawCharacters":176322},{"key":"dsh-original-lab-garment-live-2","sha256":"122b3fb7a3bb61ef2239fa3de9c1b5340dfd17d95330ebada52ab03292b41478","rawCharacters":180887},{"key":"dsh-original-lab-head-body-dry-1","sha256":"410cea4da726d1aeb0975d2c583982d529c1665ca2920cc4e95293c6ee9db945","rawCharacters":85474},{"key":"dsh-original-lab-head-body-live-1","sha256":"7a1b74af924afd424e0907d01b877357727ce1ca79407288ede83fe2d2864ff5","rawCharacters":180736},{"key":"dsh-original-lab-head-parallel-clean-route-1793030400000","sha256":"f59cbe0103bb799dbe77e939b8f7e31ec8c51cd0ae3d41c6caaf3e677e161e3c","rawCharacters":210098},{"key":"dsh-original-lab-head-refinement-1792921289985","sha256":"d99fcd3f8464b5840f4e9af738bd41cb426b438e56e677a4687049a2aa64c4fe","rawCharacters":453},{"key":"dsh-original-lab-head-refinement-1792921289985-surface-repair-2","sha256":"bbdc0cd380eecf190bd68c0f0442a9d75ec0a849596b099d6cf7f909aefd2b2e","rawCharacters":453},{"key":"dsh-original-lab-published-head-fd7b5d5-1792903277668","sha256":"ed8a511e7a7555a9010fc2dc8dcae97ab3c17af5c6a3a9b85cd8a414c4ce419a","rawCharacters":211946},{"key":"dsh-original-lab-published-head-fd7b5d5-compat-1792903968967","sha256":"6cfca189e22d72636513aa413dcc34faa896953211594186354c026726fb4dd4","rawCharacters":219958},{"key":"dsh-original-lab-socket-mouth-lab-1792854089294","sha256":"6440787ed3dfa4a3859c85483455bf28c528aa7ca0d8b6a086f2f1ff70570f15","rawCharacters":295472},{"key":"dsh-original-lab-socket-mouth-lab-1792854089294-continuation-1","sha256":"7e5e6b5ee5abd6976756a0f63c9f2fb2120287cc046e9bfcf1b347407d78250e","rawCharacters":300783},{"key":"dsh-sm-carrier-381c1ad2bd1a","sha256":"594c31a6dc89e6a7fe6501f763964d36e7a4022db08e5997556bf381bc6ad8fd","rawCharacters":12077},{"key":"dsh-sm-carrier-44de11c5db06","sha256":"2478dd3ae59c3817c92fdd91a111b79f3abab51601f85c244df549ccc550e2f9","rawCharacters":12077},{"key":"dsh-sm-carrier-4c929f1c05d2-new-card-5812c13a-5bee-42a7-8501-d8460a0d7dc8-apply","sha256":"8f5105706dd37d2304f9d41923613fbfa5d47172c29b647019b2dd52a9eef3c8","rawCharacters":3869},{"key":"dsh-sm-carrier-9fafe1cdda84","sha256":"ef48d2f8b8906476192a71823f8c9f96489557f836755dd8486be93c601767b0","rawCharacters":10201},{"key":"dsh-sm-carrier-e448bd48525a","sha256":"67a234f0a497f8c22cd4c6f82bb859abf9fa7477d9f88f45307991d23aef39c3","rawCharacters":10198},{"key":"dsh-sm-carrier-fe4809f14f34","sha256":"6fa02b2fdb97d49dbd393766119afea4d4566af3f73843ced000f1fed9c7459d","rawCharacters":10199},{"key":"dsh-sm-lab-autonomous-reconstruction-001-20261026T0025Z","sha256":"4e3132bf2813562c484a8e6e057a1e015a321e4600b18e04818c13038780d833","rawCharacters":37904},{"key":"dsh-sm-lab-sm-local-adapter-0.1.0-20261025T1948Z","sha256":"074e25512a57a1e1dd97a352f8d3e19eb19b61ee3a2ac8e7ec849f3d7a57b218","rawCharacters":76073},{"key":"dsh-sm-lab-sm-local-adapter-0.1.0-carrier-20261025T1955Z","sha256":"0c05cf73361c9853b925574a6419ea4b88ecb90044299cb4a9061963a2b41b51","rawCharacters":874},{"key":"dsh-sm-lab-sm-local-adapter-0.1.1-carrier-20261025T2004Z","sha256":"b6ab526305e3a03e753ce041e860fc35ad0bca86bfe04ebff3007773ea1011d9","rawCharacters":912},{"key":"dsh-sm-lab-sm-local-adapter-0.1.2-carrier-20261025T2032Z","sha256":"af19cc30fff6c3ecc6a66ad57f0e54e97555ee914045bff5efd81dcb1d92f526","rawCharacters":912},{"key":"dsh-sm-lab-sm-local-adapter-0.1.3-carrier-20261025T2124Z","sha256":"dd317f59dc7430289612a56ad3617e90b35f07cd5a2126b07bf0995b14ce99f7","rawCharacters":892},{"key":"dsh-sm-lab-sm-local-adapter-0.1.4-carrier-20261025T2300Z","sha256":"2abe467e78eb8481e2c7ca2c5dc903cd77afd8507b7feb68555e8d5a7e3666ae","rawCharacters":892},{"key":"dsh-sm-lab-sm-local-adapter-0.1.5-carrier-20261025T2326Z","sha256":"e562a035adbb32bd31ca1ed078d60f8d8ec522212eb2660709f55c79625ce917","rawCharacters":900},{"key":"dsh-sm-lab-sm-local-adapter-0.1.7-carrier-20261026T0130Z","sha256":"346eb99eca8c20531091def3b4f79b8dd049b7d67d4078f3c5af625756e53187","rawCharacters":6177},{"key":"dsh-sm-primary-head-1793030400000","sha256":"90db2c2a62933f1d9f56bdd18c037451f073db72d5d4f1b15fdc653fc769d1c4","rawCharacters":25148},{"key":"dsh-sm-source-carrier-7049e385","sha256":"32d7c0a3cd0ff15a454bc92650c63256c1f1234419811be9ebd927eb5e23f2af","rawCharacters":9242},{"key":"dsh-sm-texture-reference-288022ee","sha256":"4aa5ca3b76cac226eef7a34cb7480789c9c40fecb755ac980e1a5897b407a852","rawCharacters":10106},{"key":"dsh-ui-proof-v058-1792857827564","sha256":"dd239debe0f861b05fde768640d3dea86f69048c19ae03fd0463758e888090da","rawCharacters":179931},{"key":"dsh-ui-proof-v058-close-fix-1792857827564","sha256":"2a8664eb6e8735f7a12805a00c2a9c267267adbc738c606c8cb5343f6d637c73","rawCharacters":178270},{"key":"dsh-ui-proof-v058-hover-fix-1792857827564","sha256":"20d3e6cd1bb8547234e54eab7166f6b631ccca99767ff5ff5640a274a8a209ff","rawCharacters":267616}];const state={phase:"reading-idle-storage-proof",serviceRequests:0};const publish=()=>{document.body.dataset.dshDurableFinal=JSON.stringify(state);};const store=window.DshDurableState.create();(async()=>{try{state.history=[];for(const r of records){const raw=await store.readRevision(r.key,r.sha256);if(raw.length!==r.rawCharacters)throw Error("History size mismatch");state.history.push({key:r.key,sha256:r.sha256,characters:raw.length,verified:true});}state.storage=await store.probe("final-idle-read-only");if(state.storage.totalUtf16Bytes>=64000)throw Error("Footprint exceeds strict cap");state.knownJobs=[];for(const key of ["dsh-sm-lab-sm-local-adapter-0.1.7-carrier-20261026T0130Z","dsh-sm-lab-autonomous-reconstruction-001-20261026T0025Z"]){const s=await store.load(key);state.knownJobs.push({key,jobId:s.jobId,status:s.status,nativeStatus:s.job?.status});}const c=await store.load("dsh-sm-carrier-4c929f1c05d2-new-card-5812c13a-5bee-42a7-8501-d8460a0d7dc8-apply");state.carrier={phase:c.phase,pending:c.pending||null,assetId:c.upload?.assetId};state.phase="idle-under-cap-all-history-intact";}catch(e){state.error=e.message;state.phase="failed-read-only";}publish();})();})();

(async()=>{
 const projectId='01a1788c-2397-711a-87e8-e05d36a211d0',nodeId='1305301b-8b28-47ea-9bb1-ce0f68189605';
 if(location.origin!=='https://studio.tripo3d.ai'||location.pathname!=='/projects/'+projectId)return;
 const api=window.__dshShortcut,state={phase:'waiting-startup'},start=Date.now();
 const publish=()=>{window.__dshFlowState=state;if(document.body)document.body.dataset.dshHeadMonitor=JSON.stringify(state);};
 try{
  while(!api.status().ready){if(Date.now()-start>120000)throw Error('Studio startup unavailable');await new Promise(r=>setTimeout(r,200));}
  let last='';
  for(let i=0;i<40;i++){
   const list=await api.run('listLabArtifacts',{projectId,nodeId});state.jobs=list.jobs;
   const jobId=list.activeJobId||list.jobs[0]?.jobId;if(!jobId)throw Error('No native job recorded for this Lab');
   state.job=await api.run('listLabArtifacts',{projectId,nodeId,jobId,includeProgress:true});state.phase=state.job.status;publish();
   const key=JSON.stringify(state.job);if(key!==last){state.evidence=await api.run('export');last=key;publish();}
   if(['completed','failed','canceled','cancelled'].includes(state.job.status))break;
   await new Promise(r=>setTimeout(r,30000));if(location.pathname!=='/projects/'+projectId)break;
  }
 }catch(e){state.phase='monitor-error';state.error=e.message;publish();}
})();
