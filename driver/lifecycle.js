// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(() => {
  'use strict';
  const pending=new Map();
  document.addEventListener('dsh-shortcut-response',e=>{
    const p=pending.get(e.detail?.id);if(!p)return;pending.delete(e.detail.id);clearTimeout(p.timer);
    e.detail.ok?p.resolve(e.detail.result):p.reject(Error(e.detail.error));
  });
  function call(name,args={}){return new Promise((resolve,reject)=>{
    const id=crypto.randomUUID();
    const timer=setTimeout(()=>{pending.delete(id);reject(Error('Action is still running; check status or use STOP.'));},300000);
    pending.set(id,{resolve,reject,timer});
    document.dispatchEvent(new CustomEvent('dsh-shortcut-request',{detail:{id,name,args}}));
  });}
  // Convenience API in the extension's isolated world. Agents use the DOM bridge.
  window.__dshShortcut={status:()=>call('status'),actions:()=>call('actions'),run:call};
  chrome.runtime.onMessage.addListener((msg,sender,reply)=>{
    if(sender.id!==chrome.runtime.id||msg?.type!=='dsh-shortcut')return;
    call(msg.name,msg.args).then(result=>reply({ok:true,result}),e=>reply({ok:false,error:e.message}));return true;
  });
  // The operator-authorized flow executes in MAIN and calls its API directly.
  let injected=false;
  function injectFlow(){
    if(injected||!location.pathname.startsWith('/projects'))return;
    const root=document.documentElement;
    if(!root?.dataset.dshDriverReady){setTimeout(injectFlow,25);return;}
    injected=true;
    const script=document.createElement('script');
    script.id='dsh-flow-script';script.src=chrome.runtime.getURL('flow.js');
    script.onerror=()=>{document.title='DSH ERROR: flow.js did not load';if(document.body)document.body.dataset.dshFlowError='flow.js did not load';};
    root.appendChild(script);
  }
  injectFlow();
  const pulse=()=>{try{chrome.runtime.getManifest();document.dispatchEvent(new Event('dsh-tripo-alive'));}catch{document.dispatchEvent(new Event('dsh-tripo-teardown'));clearInterval(timer);}};
  const timer=setInterval(pulse,1000);pulse();
})();
