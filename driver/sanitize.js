// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(() => {
  'use strict';
  const secret = /authorization|cookie|token|secret|password|credential|api.?key|signature|policy|access.?key|sts_ak|sts_sk|session|csrf|jwt/i;
  const key = x => typeof x === 'string' && /^[A-Za-z_][A-Za-z0-9_.-]{0,47}$/.test(x) && !secret.test(x) ? x : '<redacted-key>';
  function schema(value, depth = 0) {
    if (depth > 5) return {type:'truncated'};
    if (value === null) return {type:'null'};
    if (Array.isArray(value)) return {type:'array',length:value.length,items:value.length ? schema(value[0],depth+1) : null};
    if (typeof value === 'object') {
      const properties = Object.create(null);
      for (const k of Object.keys(value).slice(0,40)) properties[key(k)] = secret.test(k) ? {type:'redacted'} : schema(value[k],depth+1);
      return {type:'object',properties,truncated:Object.keys(value).length>40};
    }
    return {type:typeof value};
  }
  function body(value) {
    try {
      if (value == null) return {type:'absent'};
      if (typeof value === 'string') {
        if (value.length > 65536) return {type:'omitted',reason:'size-limit'};
        try { return schema(JSON.parse(value)); } catch { return {type:'text',length:value.length}; }
      }
      if (value instanceof URLSearchParams) return {type:'form',fields:[...value.keys()].slice(0,40).map(key)};
      if (typeof FormData !== 'undefined' && value instanceof FormData) return {type:'form-data',fields:[...value.keys()].slice(0,40).map(key)};
      if (typeof Blob !== 'undefined' && value instanceof Blob) return {type:'binary',bytes:value.size};
      if (value instanceof ArrayBuffer) return {type:'binary',bytes:value.byteLength};
      return {type:'unread'};
    } catch { return {type:'unknown'}; }
  }
  function url(value, base) {
    try {
      const u = new URL(value,base);
      if (!['https:','wss:'].includes(u.protocol) || !(u.hostname === 'tripo3d.ai' || u.hostname.endsWith('.tripo3d.ai') || u.hostname.endsWith('.tripo3d.com') || u.hostname.endsWith('.amazonaws.com'))) return null;
      let redactNext = false;
      const path = u.pathname.split('/').map(part => {
        const sensitive = redactNext; redactNext = secret.test(part);
        if (sensitive || secret.test(part)) return '<redacted>';
        if (/^[a-z][a-z0-9_-]{0,31}$/.test(part) || /^v?[0-9]{1,4}$/.test(part) || part === '') return part;
        return '<id-or-redacted>';
      }).join('/');
      return {origin:u.origin,path,query:[...u.searchParams.keys()].slice(0,40).map(key),queryValues:'<redacted>',fragment:'<omitted>'};
    } catch { return null; }
  }
  function headers(value) {
    const result = Object.create(null);
    try { for (const [name] of new Headers(value || {})) result[/^(authorization|cookie|set-cookie|x-csrf-token)$/i.test(name) ? name.toLowerCase() : key(name)] = '<redacted>'; } catch {}
    return result;
  }
  function operation(value) {
    return typeof value==='string' && value.length<=160 && /^\/?[a-z][a-z0-9_.:/-]*$/i.test(value) && !/^eyJ/.test(value) ? value : '<unknown-or-redacted>';
  }
  function contract(value,field='') {
    if(secret.test(field))return '<redacted>';
    if(typeof value==='string')return /Bearer\s|eyJ[A-Za-z0-9_-]{12,}\./.test(value)?'<redacted>':value.replace(/https:\/\/[^\s"<>]+/g,s=>{try{const u=new URL(s);return u.origin+u.pathname;}catch{return '<url>';}});
    if(Array.isArray(value))return value.map(v=>contract(v,field));
    if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,contract(v,k)]));
    return value;
  }
  function payload(value){
    try{
      if(typeof FormData!=='undefined'&&value instanceof FormData)return {formData:[...value.entries()].map(([name,v])=>({name,value:typeof v==='string'?contract(v,name):{fileName:v.name,mimeType:v.type,size:v.size}}))};
      if(typeof value==='string'&&value.length<=1048576)return contract(JSON.parse(value));
      return undefined;
    }catch{return undefined;}
  }
  function details(value) {
    try {
      if(typeof value==='string'){if(value.length>65536)return {};value=JSON.parse(value);}
      if(!value || typeof value!=='object')return {};
      const out={signals:[]}, uuid=/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i;
      function walk(v,p='',depth=0){
        if(depth>6||out.signals.length>=80||!v||typeof v!=='object')return;
        for(const [k,x] of Object.entries(v).slice(0,40)){
          if(secret.test(k))continue;
          const at=p?p+'.'+key(k):key(k);
          if(/^(projectId|canvasId|nodeId|runId|turnId|jobId|taskId|messageId|assetId)$/.test(k)&&typeof x==='string'&&uuid.test(x))out.signals.push({path:at,value:x});
          else if(/^(type|status|state|phase|event|eventType|cardType|deliveryState|errorCode|code)$/.test(k)&&((typeof x==='string'&&/^[A-Za-z][A-Za-z0-9_.:-]{0,63}$/.test(x))||(typeof x==='number'&&Number.isFinite(x))))out.signals.push({path:at,value:x});
          else if(k==='total_credit'&&typeof x==='number'&&Number.isFinite(x))out.signals.push({path:at,value:x});
          if(typeof x==='object')walk(x,at,depth+1);
          if(out.signals.length>=80)break;
        }
      }
      walk(value);
      if(Array.isArray(value.projects)&&typeof value.total==='number'){
        out.projectInventory={total:value.total,projects:value.projects.slice(0,100).map(p=>{
          let thumbnail=null;try{const u=new URL(p.coverImageUrl);if(u.protocol==='https:'&&(u.hostname.endsWith('.tripo3d.ai')||u.hostname.endsWith('.tripo3d.com') || u.hostname.endsWith('.amazonaws.com')))thumbnail=u.origin+u.pathname;}catch{}
          return {id:uuid.test(p.projectId)?p.projectId:null,name:typeof p.name==='string'?p.name.slice(0,512):null,edited:typeof p.updateTime==='string'&&/^[0-9T:Z+ .-]{1,40}$/.test(p.updateTime)?p.updateTime:null,thumbnail,coverAssetId:uuid.test(p.coverAssetId)?p.coverAssetId:null};
        })};
      }
      return out;
    }catch{return {};}
  }
  const api = Object.freeze({schema,body,url,headers,key,operation,details,contract,payload});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else Object.defineProperty(window,'__dshTripoSanitize',{value:api,configurable:true});
})();

