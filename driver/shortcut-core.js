// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(function(root){
  'use strict';
  function create(adapter){
    const names=Object.freeze([...(adapter.baseActions||['capture','read','run','export','stop']),...(adapter.actions||[])]);
    const history=[];let active=null;
    const clean=adapter.clean;
    const status=()=>clean({...adapter.status(),active:active?.name||null,lastActions:history.slice(-12)});
    function run(name,args={}){
      if(!names.includes(name))return Promise.reject(Error('Unknown action: '+String(name).slice(0,40)));
      if(!args||typeof args!=='object'||Array.isArray(args))return Promise.reject(Error('Action arguments must be an object.'));
      if(name!=='stop'&&active)return Promise.reject(Error('An action is running. Use STOP to cancel it.'));
      const item={name,at:new Date().toISOString(),status:'running'},start=performance.now();history.push(item);if(history.length>40)history.shift();
      const finish=(value,error)=>{item.elapsedMs=performance.now()-start;item.status=error?'failed':'done';if(error)item.error=clean(String(error.message));return value;};
      if(name==='stop'){
        active?.controller.abort();
        try{return Promise.resolve(finish(adapter.stop()));}catch(error){finish(null,error);return Promise.reject(error);}
      }
      const current={name,controller:new AbortController()};active=current;
      return Promise.resolve().then(()=>adapter.invoke(name,args,current.controller.signal))
        .then(value=>finish(clean(value)),error=>{finish(null,error);throw Error(clean(String(error.message)));})
        .finally(()=>{if(active===current)active=null;});
    }
    return Object.freeze({status,actions:()=>[...names],run});
  }
  const api={create};if(typeof module!=='undefined'&&module.exports)module.exports=api;else Object.defineProperty(root,'__dshShortcutCore',{value:api});
})(typeof window==='undefined'?globalThis:window);
