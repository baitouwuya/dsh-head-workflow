// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(() => {
  'use strict';
  const ui=window.__dshUiActions.create({document,location});
  const clean=window.__dshTripoSanitize.contract;
  const api=window.__dshShortcutCore.create({baseActions:['stop'],actions:window.__dshUiActions.reviewActions,clean,
    status:()=>({version:'0.2.58',surface:'local-review',ready:document.body?.dataset.ready==='true',message:document.body?.dataset.error||'Local review companion'}),
    stop:()=>({stopped:true,limits:'Cancels pending waits and subsequent actions. A synchronous review calculation already dispatched cannot be interrupted or undone.'}),
    invoke:(name,args,signal)=>ui.run(name,args,signal)
  });
  window.__dshShortcut=api;
  document.addEventListener('dsh-shortcut-request',event=>{
    const {id,name,args}=event.detail||{};
    Promise.resolve().then(()=>name==='status'?api.status():name==='actions'?api.actions():api.run(name,typeof args==='string'?JSON.parse(args):args||{}))
      .then(value=>document.dispatchEvent(new CustomEvent('dsh-shortcut-response',{detail:{id,ok:true,result:clean(value)}})))
      .catch(error=>document.dispatchEvent(new CustomEvent('dsh-shortcut-response',{detail:{id,ok:false,error:clean(error.message)}})));
  });
  // Explicit per-navigation action for read-only browser tools. No action by default.
  const name=new URL(location.href).searchParams.get('dshAction');
  if(name){
    const id=crypto.randomUUID();
    const receive=event=>{if(event.detail?.id!==id)return;document.removeEventListener('dsh-shortcut-response',receive);document.body.dataset.dshReviewResult=JSON.stringify(event.detail);};
    document.addEventListener('dsh-shortcut-response',receive);
    document.dispatchEvent(new CustomEvent('dsh-shortcut-request',{detail:{id,name,args:{dryRun:false}}}));
  }
})();
