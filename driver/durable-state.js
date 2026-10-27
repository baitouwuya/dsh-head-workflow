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
