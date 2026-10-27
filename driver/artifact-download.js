// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(function(root){
  'use strict';
  const extensions=['glb','fbx','blend','zip','png','jpg','jpeg','json','md','txt','obj','stl','usd','usdz','3mf'];
  const hex=b=>Array.from(new Uint8Array(b),v=>v.toString(16).padStart(2,'0')).join('');
  function validateBytes(buffer,extension){
    const b=new Uint8Array(buffer);if(!b.length)throw Error('Downloaded artifact is empty.');
    if(extension==='glb'){
      const v=new DataView(b.buffer,b.byteOffset,b.byteLength);
      if(b.length<20||v.getUint32(0,true)!==0x46546c67||v.getUint32(4,true)!==2||v.getUint32(8,true)!==b.length)throw Error('Downloaded GLB header/length is invalid.');
    }
    if(extension==='png'&&![137,80,78,71,13,10,26,10].every((n,i)=>b[i]===n))throw Error('Downloaded PNG header is invalid.');
    if(['zip','usdz','3mf'].includes(extension)&&!(b[0]===80&&b[1]===75&&[3,5,7].includes(b[2])&&[4,6,8].includes(b[3])))throw Error('Downloaded ZIP container header is invalid.');
    if(extension==='fbx'&&!new TextDecoder().decode(b.subarray(0,80)).match(/^(Kaydara FBX Binary|;\s*FBX)/))throw Error('Downloaded FBX header is invalid.');
  }
  function create({fetch,write,crypto,window,location,pause,onProgress}){
    let nativeResponseHandler=null;
    function observeNativeDownload(filename,response){if(nativeResponseHandler)nativeResponseHandler(filename,response.clone());}
    async function ready(signal){const health=await write({area:'health'},signal);if(!health?.ok||!health.capabilities?.includes('artifact-chunks'))throw Error('The local writer must be updated to support verified artifact downloads; Export was not pressed.');}
    async function readBytes(url,signal,args={},providedResponse){
      const u=new URL(url);if(!['https:','blob:'].includes(u.protocol))throw Error('Download URL must be native HTTPS or blob.');
      const max=Number(args.maxBytes??200*1024*1024),idle=Number(args.idleTimeoutMs??45000),total=Number(args.downloadTimeoutMs??240000);
      if(!Number.isSafeInteger(max)||max<1||max>512*1024*1024||!Number.isFinite(idle)||idle<1||idle>120000||!Number.isFinite(total)||total<1||total>300000)throw Error('Download bounds are invalid.');
      const controller=new AbortController();let idleTimer,totalTimer,reader;
      const cancelRead=()=>{reader?.cancel(controller.signal.reason).catch(()=>{});};
      const abort=()=>controller.abort(signal?.reason||Error('Stopped'));
      if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true});
      const reset=()=>{clearTimeout(idleTimer);idleTimer=setTimeout(()=>controller.abort(Error('Download stalled')),idle);};
      totalTimer=setTimeout(()=>controller.abort(Error('Download timed out')),total);reset();
      try{
        if(controller.signal.aborted)throw Error('Stopped');
        const r=providedResponse||await fetch(url,{credentials:'omit',signal:controller.signal});
        if(!r.ok)throw Error('Download HTTP '+r.status+'; no retry.');
        const declared=Number(r.headers?.get('content-length')||0);if(declared>max)throw Error('Artifact exceeds download size bound.');
        reader=r.body?.getReader();if(!reader)throw Error('Streaming download is unavailable.');controller.signal.addEventListener('abort',cancelRead,{once:true});
        const parts=[];let size=0;
        while(true){reset();const chunk=await reader.read();if(chunk.done)break;size+=chunk.value.byteLength;if(size>max)throw Error('Artifact exceeds download size bound.');parts.push(chunk.value);onProgress?.({bytes:size,totalBytes:declared||null});}
        if(controller.signal.aborted)throw controller.signal.reason||Error('Stopped');
        if(declared&&declared!==size)throw Error('Downloaded length differs from Content-Length.');
        const bytes=new Uint8Array(size);let at=0;for(const part of parts){bytes.set(part,at);at+=part.length;}return bytes.buffer;
      }finally{clearTimeout(idleTimer);clearTimeout(totalTimer);signal?.removeEventListener('abort',abort);controller.signal.removeEventListener('abort',cancelRead);try{await reader?.cancel();}catch{}}
    }
    async function download(url,filename,signal,args={},writerReady=false){
      const extension=filename.split('.').pop().toLowerCase();if(!extensions.includes(extension))throw Error('Unsupported artifact file extension.');
      if(!writerReady)await ready(signal);
      const bytes=await readBytes(url,signal,args);return persistBytes(bytes,filename,signal);
    }
    async function persistBytes(bytes,filename,signal){
      const extension=filename.split('.').pop().toLowerCase();validateBytes(bytes,extension);
      const sha256=hex(await crypto.subtle.digest('SHA-256',bytes));
      const stem=filename.replace(/\.[^.]*$/,'').toLowerCase().replace(/[^a-z0-9-]+/g,'-').replace(/^-|-$/g,'').slice(0,36)||'artifact';
      const name='dsh-artifact-'+Date.now()+'-'+crypto.randomUUID().slice(0,8)+'-'+stem+'.'+extension;
      let saved;
      for(let offset=0;offset<bytes.byteLength;offset+=524288){
        if(signal?.aborted)throw Error('Stopped');const part=new Uint8Array(bytes,offset,Math.min(524288,bytes.byteLength-offset));let binary='';
        for(let i=0;i<part.length;i+=8192)binary+=String.fromCharCode(...part.subarray(i,i+8192));
        saved=await write({area:'artifacts',name,offset,base64:btoa(binary),final:offset+part.length===bytes.byteLength,sha256},signal);
      }
      if(!saved?.ok||saved.sha256!==sha256||saved.bytes!==bytes.byteLength||!saved.path)throw Error('Local artifact write was not verified.');
      return {completed:true,filename,bytes:bytes.byteLength,sha256,path:saved.path,sink:'local-writer'};
    }
    function arm({filename,format,signal,check,args={}}){
      const timeout=Number(args.downloadTimeoutMs??240000);if(!Number.isFinite(timeout)||timeout<=0||timeout>300000)throw Error('downloadTimeoutMs must be between 1 and 300000.');
      const proto=window.HTMLAnchorElement?.prototype;if(!proto?.click)throw Error('Native download capture is unavailable.');
      const old=proto.click,oldDispatch=proto.dispatchEvent,hadOwnDispatch=Object.prototype.hasOwnProperty.call(proto,'dispatchEvent'),opened=location.origin+location.pathname;
      const stem=extensions.includes(filename.split('.').pop().toLowerCase())?filename.replace(/\.[^.]+$/,''):filename;const expected=format?.toLowerCase();
      let timer,finished=false,claimed=false,resolve,reject;
      const urlApi=window.URL,oldObjectURL=urlApi?.createObjectURL;
      const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});promise.catch(()=>{});
      const restore=()=>{clearTimeout(timer);signal?.removeEventListener('abort',abort);if(nativeResponseHandler===receiveNativeResponse)nativeResponseHandler=null;if(proto.click===intercept)proto.click=old;if(proto.dispatchEvent===dispatchIntercept){if(hadOwnDispatch)proto.dispatchEvent=oldDispatch;else delete proto.dispatchEvent;}if(urlApi?.createObjectURL===objectURLIntercept)urlApi.createObjectURL=oldObjectURL;};
      const fail=e=>{if(finished)return;finished=true;restore();reject(e);};
      const abort=()=>fail(Error('Stopped; export outcome may be unknown after submission.'));
      function captureAnchor(){
        const downloadName=this.download||'',extension=downloadName.split('.').pop().toLowerCase();
        const matches=downloadName&&(downloadName===filename||downloadName.startsWith(stem+'.'))&&extensions.includes(extension)&&(!expected||extension===expected||extension==='zip');
        if(!matches||claimed)return false;
        try{check();if(location.origin+location.pathname!==opened)throw Error('The open canvas changed.');}catch(e){fail(e);return true;}
        // Replace this one native save with a bounded, verified sink; unrelated links keep their native behavior.
        const href=this.href;claimed=true;restore();
        // UI export checked the writer before pressing Export. Start reading a blob URL
        // immediately: the native handler may revoke it as soon as anchor.click returns.
        download(href,downloadName,signal,args,true).then(value=>{finished=true;resolve(value);},fail);
        return true;
      }
      function intercept(...callArgs){if(!captureAnchor.call(this))return Reflect.apply(old,this,callArgs);}
      function dispatchIntercept(event,...callArgs){if(event?.type==='click'&&captureAnchor.call(this))return true;return Reflect.apply(oldDispatch,this,[event,...callArgs]);}
      function receiveNativeResponse(downloadName,response){
        const extension=String(downloadName||'').split('.').pop().toLowerCase();
        if(finished||claimed||!(downloadName===filename||downloadName===stem||downloadName.startsWith(stem+'.'))||!response?.ok)return;
        const outputName=extensions.includes(extension)?downloadName:downloadName+'.'+expected;
        try{check();if(signal?.aborted)throw Error('Stopped');}catch(e){fail(e);return;}
        claimed=true;restore();
        Promise.resolve().then(async()=>{
          if(/json/i.test(response.headers?.get('content-type')||'')){
            const reply=await response.json();if(reply.code||!reply.data?.model_url)throw Error('Native export response has no downloadable model.');
            return readBytes(reply.data.model_url,signal,args);
          }
          return readBytes('https://api.tripo3d.ai/v2/studio/operation/download_with_name',signal,args,response);
        })
          .then(bytes=>persistBytes(bytes,outputName,signal))
          .then(value=>{finished=true;resolve({...value,capture:'native-download-response',nativeSavePreserved:true});},fail);
      }
      function objectURLIntercept(blob,...callArgs){
        const value=Reflect.apply(oldObjectURL,this,[blob,...callArgs]);
        // Some native savers cache the anchor click function before capture begins.
        // Mirror the format-checked export Blob while leaving its native save untouched.
        if(blob?.size>0&&blob.size<=Number(args.maxBytes??200*1024*1024)&&typeof blob.arrayBuffer==='function'){
          blob.slice(0,80).arrayBuffer().then(async header=>{
            if(finished||claimed)return;const b=new Uint8Array(header),t=new TextDecoder().decode(b);
            const matches=expected==='glb'?b[0]===103&&b[1]===108&&b[2]===84&&b[3]===70:
              expected==='fbx'?/^(Kaydara FBX Binary|;\s*FBX)/.test(t):
              ['3mf','usd','obj','stl'].includes(expected)&&b[0]===80&&b[1]===75;
            if(!matches)return;check();if(signal?.aborted)throw Error('Stopped');
            claimed=true;restore();const bytes=await blob.arrayBuffer();
            const extension=b[0]===80&&b[1]===75?'zip':expected;
            const saved=await persistBytes(bytes,stem+'.'+extension,signal);finished=true;resolve({...saved,capture:'native-export-blob',nativeSavePreserved:true});
          }).catch(fail);
        }
        return value;
      }
      proto.click=intercept;if(oldDispatch)proto.dispatchEvent=dispatchIntercept;timer=setTimeout(()=>fail(Error('No matching native download was observed after Export. Do not press Export again without checking its outcome.')),timeout);
      if(oldObjectURL)urlApi.createObjectURL=objectURLIntercept;
      nativeResponseHandler=receiveNativeResponse;
      if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true});
      return {promise,dispose:()=>{if(!finished)fail(Error('Export capture closed.'));else restore();}};
    }
    return {ready,readBytes,download,arm,validateBytes,observeNativeDownload};
  }
  const api={create,validateBytes,extensions};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.__dshArtifactDownload=api;
})(typeof window==='undefined'?globalThis:window);
