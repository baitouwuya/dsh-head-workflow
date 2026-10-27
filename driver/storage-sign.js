// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(() => {
  'use strict';
  const bytes=value=>typeof value==='string'?new TextEncoder().encode(value):value;
  const hex=value=>Array.from(new Uint8Array(value),n=>n.toString(16).padStart(2,'0')).join('');
  const hash=async value=>hex(await crypto.subtle.digest('SHA-256',bytes(value)));
  async function hmac(key,value){
    const imported=await crypto.subtle.importKey('raw',bytes(key),{name:'HMAC',hash:'SHA-256'},false,['sign']);
    return crypto.subtle.sign('HMAC',imported,bytes(value));
  }
  const encode=value=>encodeURIComponent(value).replace(/[!'()*]/g,c=>'%'+c.charCodeAt(0).toString(16).toUpperCase());
  // AWS SigV4, tested against the public AWS example. Credentials never leave this call.
  async function sign({method='PUT',host,path,query='',headers,body,region,accessKey,secretKey}){
    const h={...headers,host};h['x-amz-content-sha256']??=await hash(body);
    const names=Object.keys(h).sort(),signed=names.join(';');
    const canonical=[method,path,query,names.map(k=>k+':'+String(h[k]).trim().replace(/\s+/g,' ')+'\n').join(''),signed,h['x-amz-content-sha256']].join('\n');
    const date=h['x-amz-date'].slice(0,8),scope=date+'/'+region+'/s3/aws4_request';
    let key=await hmac('AWS4'+secretKey,date);key=await hmac(key,region);key=await hmac(key,'s3');key=await hmac(key,'aws4_request');
    const signature=hex(await hmac(key,'AWS4-HMAC-SHA256\n'+h['x-amz-date']+'\n'+scope+'\n'+await hash(canonical)));
    delete h.host;h.authorization='AWS4-HMAC-SHA256 Credential='+accessKey+'/'+scope+', SignedHeaders='+signed+', Signature='+signature;
    return h;
  }
  async function upload({ticket,body,mime,fetch,signal}){
    const region=/^s3[.-]([a-z0-9-]+)\.amazonaws\.com$/.exec(ticket.host)?.[1];
    if(!region||!ticket.resource_bucket||!ticket.resource_uri)throw Error('Storage response is missing the observed AWS fields.');
    const host=ticket.resource_bucket+'.s3-accelerate.amazonaws.com';
    const path='/'+ticket.resource_uri.split('/').map(encode).join('/');
    const headers=await sign({host,path,body,region,accessKey:ticket.sts_ak,secretKey:ticket.sts_sk,headers:{
      'content-type':mime,'x-amz-date':new Date().toISOString().replace(/[:-]|\.\d{3}/g,''),'x-amz-security-token':ticket.session_token
    }});
    if(signal?.aborted)throw Error('Stopped');
    const response=await fetch('https://'+host+path,{method:'PUT',headers,body,credentials:'omit',signal});
    if(!response.ok)throw Error('Storage upload failed: HTTP '+response.status+'; no retry.');
    return {status:response.status,bytes:body.byteLength};
  }
  window.__dshStorage={sign,upload};
})();
