// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(() => {
  'use strict';
  if (window.__dshCanvasObserverLoaded) return;
  window.__dshCanvasObserverLoaded = true;
  const S = window.__dshTripoSanitize;
  const CAP = 400;
  let active = false, seq = 0, dropped = 0, epoch = 0, readers = 0, sseReaders = 0;
  let records = [], restore = [], cleanup = new Set();
  let lastPulse = Date.now(), lastRoute = '', removed = false;
  const safe = fn => { try { return fn(); } catch { return undefined; } };
  const route = () => S.url(location.href,location.href);
  function record(kind, data = {}) {
    if (!active) return;
    const row = {seq:++seq,time:new Date().toISOString(),kind,...data};
    if (JSON.stringify(row).length > 24000) { row.detail = 'omitted-size-limit'; delete row.requestBody; delete row.responseBody; }
    records.push(row);
    if (records.length > CAP) { records.shift(); dropped++; }
    render();
  }
  function render() {}
  function replace(object,name,wrapped) {
    const original = object[name]; object[name] = wrapped;
    restore.push(() => { if (object[name] === wrapped) object[name] = original; });
  }
  function requestMeta(input,init) {
    const req = typeof Request !== 'undefined' && input instanceof Request;
    const url = S.url(req ? input.url : input,location.href);
    if (!url) return null;
    const method = String(init?.method || (req ? input.method : 'GET')).toUpperCase();
    const headers=init?.headers || (req?input.headers:null);
    return {url,method:/^[A-Z]{1,12}$/.test(method)?method:'unknown',headers:S.headers(headers),operation:S.operation(new Headers(headers||{}).get('x-micro-method')),requestDetails:init?.body!==undefined?S.details(init.body):{},credentials:['include','omit','same-origin'].includes(init?.credentials || (req?input.credentials:'same-origin'))?(init?.credentials || (req?input.credentials:'same-origin')):'unknown',requestBody:init?.body !== undefined ? S.body(init.body) : {type:req?'request-body-unread':'absent'}};
  }
  async function responseShape(response) {
    if (!/application\/json|\+json/i.test(response.headers.get('content-type') || '')) return {type:'omitted',reason:'not-json'};
    if (Number(response.headers.get('content-length')) > 65536) return {type:'omitted',reason:'size-limit'};
    if (readers >= 2) return {type:'omitted',reason:'reader-limit'};
    let reader, timer; readers++;
    try {
      reader = response.clone().body?.getReader();
      if (!reader) return {type:'absent'};
      let bytes = 0, text = '', timedOut = false;
      const decoder = new TextDecoder();
      timer = setTimeout(() => { timedOut=true; safe(()=>reader.cancel().catch(()=>{})); },2000);
      while (true) {
        const part = await reader.read();
        if (timedOut) return {type:'omitted',reason:'timeout'};
        if (part.done) break;
        bytes += part.value.byteLength;
        if (bytes > 65536) { safe(()=>reader.cancel().catch(()=>{})); return {type:'omitted',reason:'size-limit'}; }
        text += decoder.decode(part.value,{stream:true});
      }
      text += decoder.decode();
      return {...S.body(text),observed:S.details(text)};
    } catch { return {type:'unread'}; }
    finally { clearTimeout(timer); readers--; }
  }
  async function observeSse(response,id,ownEpoch) {
    // Inspect a bounded clone only; never consume or cancel the site's reader.
    if(sseReaders>=2){record('sse.omitted',{id,reason:'reader-limit'});return;}
    let reader,timer,cancel,bytes=0,frames=0,pending='';sseReaders++;
    try{
      reader=response.clone().body?.getReader();if(!reader)return;
      cancel=()=>safe(()=>reader.cancel().catch(()=>{}));cleanup.add(cancel);
      const decoder=new TextDecoder();
      timer=setTimeout(()=>safe(()=>reader.cancel().catch(()=>{})),60000);
      while(active&&ownEpoch===epoch&&frames<100&&bytes<65536){
        const part=await reader.read();if(part.done)break;
        bytes+=part.value.byteLength;if(bytes>65536)break;
        pending+=decoder.decode(part.value,{stream:true}).replace(/\r\n/g,'\n');
        let boundary;
        while((boundary=pending.indexOf('\n\n'))>=0&&frames<100){
          const frame=pending.slice(0,boundary);pending=pending.slice(boundary+2);
          const lines=frame.split('\n'),event=lines.find(x=>x.startsWith('event:'))?.slice(6).trim()||'message';
          const data=lines.filter(x=>x.startsWith('data:')).map(x=>x.slice(5).trimStart()).join('\n');
          if(!data)continue;
          if(active&&ownEpoch===epoch)record('sse.frame',{id,index:++frames,event:/^[A-Za-z][A-Za-z0-9_.:-]{0,63}$/.test(event)?event:'<redacted>',payload:S.body(data),observed:S.details(data)});
        }
      }
      if(active&&ownEpoch===epoch)record('sse.observation-end',{id,frames,bytes,limited:frames>=100||bytes>=65536});
    }catch{if(active&&ownEpoch===epoch)record('sse.observation-end',{id,frames,bytes,error:'reader-ended'});}
    finally{clearTimeout(timer);if(cancel){cleanup.delete(cancel);cancel();}sseReaders--;}
  }
  function start() {
    if (active || removed) return;
    active=true; epoch++; const ownEpoch=epoch;
    const originalFetch = window.fetch;
    replace(window,'fetch',function(...args) {
      const started = performance.now();
      const info = safe(()=>requestMeta(args[0],args[1]));
      const id = info ? 'f'+(++seq) : null;
      if (info) record('fetch.request',{id,...info});
      let promise;
      try { promise=Reflect.apply(originalFetch,this,args); }
      catch (error) { if(info)record('fetch.failure',{id,error:'synchronous-error'}); throw error; }
      if(info) promise.then(response => {
        if(!active || ownEpoch!==epoch)return;
        const contentType=(response.headers.get('content-type')||'').split(';')[0].toLowerCase();
        const mime=['application/json','text/event-stream','application/x-ndjson','text/plain','application/octet-stream'].includes(contentType)?contentType:'other-or-unknown';
        record('fetch.response',{id,status:response.status,elapsedMs:Math.round(performance.now()-started),headers:S.headers(response.headers),mime,redirected:response.redirected});
        if(mime==='text/event-stream')observeSse(response,id,ownEpoch).catch(()=>{});
        responseShape(response).then(shape=>{if(active && ownEpoch===epoch)record('fetch.response-shape',{id,responseBody:shape});}).catch(()=>{});
      },()=>{if(active && ownEpoch===epoch)record('fetch.failure',{id,error:'request-rejected'});}).catch(()=>{});
      return promise;
    });
    const xp=XMLHttpRequest.prototype, open=xp.open, send=xp.send, setHeader=xp.setRequestHeader;
    const pending=new WeakMap();
    replace(xp,'open',function(method,url,...rest) {
      const result=Reflect.apply(open,this,[method,url,...rest]);
      safe(()=>pending.set(this,{url:S.url(url,location.href),method:/^[A-Za-z]{1,12}$/.test(method)?String(method).toUpperCase():'unknown',headers:Object.create(null)}));
      return result;
    });
    replace(xp,'setRequestHeader',function(name,value) {
      const result=Reflect.apply(setHeader,this,[name,value]);
      safe(()=>{const item=pending.get(this);if(item)item.headers[S.key(name)]='<redacted>';});
      return result;
    });
    replace(xp,'send',function(body) {
      safe(()=>{
        const info=pending.get(this); if(!info?.url)return;
        const id='x'+(++seq), started=performance.now();
        record('xhr.request',{id,...info,requestBody:S.body(body),contract:S.payload(body),credentials:this.withCredentials?'include':'same-origin'});
        let removeListener;
        const done=()=>safe(()=>{
          cleanup.delete(removeListener);
          if(!active || ownEpoch!==epoch)return;
          let responseBody={type:'omitted'};
          if(this.responseType==='json')responseBody=S.schema(this.response);
          else if(this.responseType==='' || this.responseType==='text')responseBody=S.body(this.responseText);
          record('xhr.response',{id,status:this.status,elapsedMs:Math.round(performance.now()-started),responseBody,contract:this.responseType==='json'?S.contract(this.response):S.payload(this.responseText)});
        });
        this.addEventListener('loadend',done,{once:true});
        removeListener=()=>this.removeEventListener('loadend',done);
        cleanup.add(removeListener);
      });
      return Reflect.apply(send,this,[body]);
    });
    const NativeWS=window.WebSocket, wsSend=NativeWS.prototype.send;
    const sockets=new WeakMap();
    const WrappedWS=new Proxy(NativeWS,{construct(target,args,newTarget){
      const socket=Reflect.construct(target,args,newTarget);
      safe(()=>{
        const url=S.url(args[0],location.href);if(!url)return;
        const id='w'+(++seq);sockets.set(socket,{id,url});record('ws.create',{id,url,protocols:'<omitted>'});
        for(const type of ['open','message','close','error']){
          const handler=event=>safe(()=>record('ws.'+type,{id,...(type==='message'?{payload:S.body(event.data)}:{}),...(type==='close'?{code:event.code,wasClean:event.wasClean}:{})}));
          socket.addEventListener(type,handler);cleanup.add(()=>socket.removeEventListener(type,handler));
        }
      });return socket;
    }});
    replace(window,'WebSocket',WrappedWS);
    replace(NativeWS.prototype,'send',function(data){
      safe(()=>{const info=sockets.get(this);if(info)record('ws.send',{id:info.id,payload:S.body(data)});});
      return Reflect.apply(wsSend,this,[data]);
    });
    lastRoute=JSON.stringify(route());record('capture.start',{route:route(),mode:'observe-only',dryRun:true});
    const routeTimer=setInterval(()=>{const current=JSON.stringify(route());if(current!==lastRoute){lastRoute=current;record('navigation',{route:route()});}},500);
    cleanup.add(()=>clearInterval(routeTimer));render();
  }
  function stop(reason='operator') {
    if(active)record('capture.stop',{reason});
    active=false;epoch++;
    for(const fn of restore.splice(0).reverse())safe(fn);
    for(const fn of cleanup)safe(fn);
    cleanup.clear();
    render();
  }
  function dump() {
    return {format:'dsh-canvas-trace',version:'0.2.46',exportedAt:new Date().toISOString(),capacity:CAP,dropped,redaction:'schema plus allowlisted operation/state/UUID/project-inventory details; all header map values redacted; URL query values omitted',limitations:['Only requests after Start; no workers or pre-existing sockets','SSE cloned reader: 60s, 100 frames, 64KiB, 2 concurrent; JSON response read capped at 64KiB and 2 readers','Metadata schemas only; no credential persistence or request replay','Ring is document-local; export before a full reload','Diagnostic data from MAIN world is not a trusted authorization boundary'],events:records};
  }
  Object.defineProperty(window,'__dshObserverControl',{value:Object.freeze({start,stop,dump,status:()=>({active,events:records.length,dropped})}),configurable:true});
  function teardown(){stop('extension-disabled');removed=true;clearInterval(lifetime);document.removeEventListener('dsh-tripo-alive',alive);document.removeEventListener('dsh-tripo-teardown',teardown);}
  function alive(){lastPulse=Date.now();}
  document.addEventListener('dsh-tripo-alive',alive);
  document.addEventListener('dsh-tripo-teardown',teardown);
  const lifetime=setInterval(()=>{if(active && Date.now()-lastPulse>15000)stop('heartbeat-timeout-evidence-preserved');},1500);
})();
