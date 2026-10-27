// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

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
