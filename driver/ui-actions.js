// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(function(root){
  'use strict';
  const nativeActions=['selectNode','labExportDialog','labExport'];
  const reviewActions=['labTestAllControls','labMeasureAllMorphs'];
  function create({document,location,pause,downloads}){
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
      if(name==='labExport'){
        if(args.format!==undefined&&!['USD','FBX','OBJ','STL','GLB','3MF'].includes(args.format))throw Error('Unsupported native export format.');
        if(args.textureResolution!==undefined&&!['1k','2k','4k','8k','Current'].includes(args.textureResolution))throw Error('Unsupported texture resolution.');
        if(args.filename!==undefined&&(typeof args.filename!=='string'||!args.filename.trim()||/[\\/<>:"|?*\x00-\x1f]/.test(args.filename)||/[. ]$/.test(args.filename)))throw Error('filename must be a plain nonempty basename.');
        for(const key of ['exportSkeleton','packUv'])if(args[key]!==undefined&&typeof args[key]!=='boolean')throw Error(key+' must be boolean.');
        for(const [key,max] of [['maxBytes',512*1024*1024],['idleTimeoutMs',120000],['downloadTimeoutMs',300000]])if(args[key]!==undefined&&(!Number.isSafeInteger(Number(args[key]))||Number(args[key])<=0||Number(args[key])>max))throw Error(key+' is outside its bound.');
        if(args.dryRun!==false)return result({mode:'dry-run',surface:'studio',nodeId:args.nodeId,action:name,source:'studio-export',converted:true,options:{format:args.format??'current',textureResolution:args.textureResolution??'current',filename:args.filename??'current',exportSkeleton:args.exportSkeleton??'current',packUv:args.packUv??'current'},exportSubmitted:false,downloadStarted:false,uiEventsSent:0});
        if(!downloads?.arm)throw Error('Verified download adapter is not loaded; Export was not pressed.');
        await downloads.ready?.(signal);check();
      }
      const operation=args.operation||'open';
      if(!['open','read','close'].includes(operation))throw Error('labExportDialog operation must be open, read or close. Export submission is not part of this action.');
      const dialog=()=>document.querySelector('[role="dialog"][aria-label="Export"]');
      if(args.dryRun!==false)return result({mode:'dry-run',surface:'studio',nodeId:args.nodeId,operation,selected:selected(),dialogOpen:!!dialog(),uiEventsSent:0});
      if(operation==='open'){
        if(dialog()&&!selected())throw Error('Another node has an export dialog open. Close it first.');
        if(name==='labExport'&&dialog()){
          const label=title.textContent.replace(/^#\d+\s*/, '').trim();
          if([...document.querySelectorAll('[role="dialog"]')].some(d=>!['Export',label].includes(d.getAttribute('aria-label'))))throw Error('The export preview belongs to another node.');
        }
        await select();
        if(!dialog()){
          if(name==='labExport'&&currentNode()?.querySelector('button[aria-label="Preview artifact"]')){
            const label=title.textContent.replace(/^#\d+\s*/, '').trim();
            const previews=()=>[...document.querySelectorAll('[role="dialog"]')];
            if(previews().some(d=>d.getAttribute('aria-label')!==label))throw Error('Another artifact dialog is open; close it before exporting this Lab.');
            if(!previews().length)click(currentNode().querySelector('button[aria-label="Preview artifact"]'));
            const preview=await until(()=>previews().find(d=>d.getAttribute('aria-label')===label),'this Lab artifact preview');
            click(await until(()=>[...preview.querySelectorAll('button')].find(b=>b.textContent.trim()==='Export'&&!b.disabled),'preview Export control'));
          }else{
          const Mouse=document.defaultView?.MouseEvent||root.MouseEvent,card=currentNode()?.querySelector('article');
          if(!Mouse||!card)throw Error('The selected Lab card is unavailable.');
          check();hoverEvents++;card.dispatchEvent(new Mouse('mouseenter',{bubbles:false,cancelable:false,view:document.defaultView}));
          click(await until(()=>currentNode()?.querySelector('button[aria-label="Export"]'),'the selected Lab export control'));
          }
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
      if(name==='labExport'){
        const combo=slot=>dialog()?.querySelectorAll('[role="combobox"]')[slot];
        const normalize=text=>String(text||'').replace(/Current/g,'').trim();
        async function choose(slot,value){
          if(value===undefined||value==='Current')return;
          if(normalize(combo(slot)?.textContent)===value)return;
          click(combo(slot));
          const option=await until(()=>[...document.querySelectorAll('[role="listbox"] [role="option"]')].find(e=>normalize(e.textContent)===value),'export option '+value);
          click(option);await until(()=>normalize(combo(slot)?.textContent)===value,'selected export option '+value);
        }
        await choose(0,args.format);await choose(1,args.textureResolution);
        if(args.filename!==undefined){
          const input=dialog()?.querySelector('input');if(!input)throw Error('Export filename field is unavailable.');check();
          const setter=Object.getOwnPropertyDescriptor(document.defaultView?.HTMLInputElement?.prototype||{},'value')?.set;
          if(setter)setter.call(input,args.filename);else input.value=args.filename;
          const E=document.defaultView?.Event||root.Event;input.dispatchEvent(new E('input',{bubbles:true}));input.dispatchEvent(new E('change',{bubbles:true}));
          await until(()=>dialog()?.querySelector('input')?.value===args.filename,'export filename');
        }
        const findSwitch=key=>[...(dialog()?.querySelectorAll('[role="switch"]')||[])].find(s=>(s.getAttribute('aria-label')||s.parentElement?.textContent||'').trim().toLowerCase()===(key==='exportSkeleton'?'export skeleton':'pack uv'));
        for(const key of ['exportSkeleton','packUv'])if(args[key]!==undefined){
          const control=findSwitch(key);if(!control)throw Error(key+' is not offered for this format.');
          if((control.getAttribute('aria-checked')==='true')!==args[key])click(control);
          await until(()=>((findSwitch(key)?.getAttribute('aria-checked')==='true')===args[key]),key+' option');
        }
        const filename=dialog()?.querySelector('input')?.value,format=normalize(combo(0)?.textContent),textureResolution=normalize(combo(1)?.textContent);
        if(!filename||!format)throw Error('Native export options are incomplete.');
        const options={filename,format,textureResolution,exportSkeleton:findSwitch('exportSkeleton')?.getAttribute('aria-checked')??null,packUv:findSwitch('packUv')?.getAttribute('aria-checked')??null};
        const handle=downloads.arm({filename,format,signal,check,args});let submitted=false;
        try{
          const button=await until(()=>[...dialog().querySelectorAll('button')].find(b=>b.textContent.trim()==='Export'&&!b.disabled),'final Export button');
          click(button);submitted=true;
          const download=await handle.promise;check();
          return result({mode:'apply',surface:'studio',nodeId:args.nodeId,action:name,source:'studio-export',converted:true,options,exportSubmitted:true,download});
        }catch(error){throw Error(error.message+(submitted?' Export was pressed once; completion is unconfirmed unless the download receipt exists. Do not automatically resubmit.':''));}
        finally{handle.dispose();}
      }
      const combos=[...d.querySelectorAll('[role="combobox"]')],switches=[...d.querySelectorAll('[role="switch"]')];
      return result({mode:'apply',surface:'studio',nodeId:args.nodeId,operation,dialogOpen:true,exportSubmitted:false,options:{filename:d.querySelector('input')?.value??null,format:combos[0]?.textContent.trim()??null,textureResolution:combos[1]?.textContent.trim()??null,exportSkeleton:switches[0]?.getAttribute('aria-checked')==='true',packUv:switches[1]?.getAttribute('aria-checked')==='true'}});
    }
    return Object.freeze({run});
  }
  const api={create,nativeActions,reviewActions,actions:[...nativeActions,...reviewActions]};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else Object.defineProperty(root,'__dshUiActions',{value:api});
})(typeof window==='undefined'?globalThis:window);
