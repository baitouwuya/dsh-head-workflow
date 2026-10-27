// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

'use strict';
let tabId;
const $=id=>document.getElementById(id);
async function call(name,args){if(tabId===undefined)throw Error('Open a Studio canvas tab first.');const r=await chrome.tabs.sendMessage(tabId,{type:'dsh-shortcut',name,args});if(!r?.ok)throw Error(r?.error||'Reload the Studio tab to load the driver.');return r.result;}
function render(s){$('status').textContent=s.active?'Running: '+s.active:s.message||'Ready';$('path').textContent=s.evidencePath||'No evidence exported in this tab yet.';$('history').replaceChildren(...s.lastActions.slice().reverse().map(a=>{const li=document.createElement('li');li.textContent=a.at.slice(11,19)+' '+a.name+' — '+a.status+(a.error?' · '+a.error:'');return li;}));}
for(const b of document.querySelectorAll('[data-action]'))b.addEventListener('click',async()=>{
  try{const name=b.dataset.action;let args={};if(name==='run'){if($('plan').value.trim())args.plan=JSON.parse($('plan').value);args.dryRun=$('dry').checked;}if(!['capture','read','run','export','stop'].includes(name)){args=$('plan').value.trim()?JSON.parse($('plan').value):{};args.dryRun=$('dry').checked;}$('result').textContent='';const value=await call(name,args);$('result').textContent=JSON.stringify(value,null,2);render(await call('status'));}
  catch(e){$('result').textContent=e.message;}
});
chrome.tabs.query({active:true,currentWindow:true}).then(async tabs=>{tabId=tabs[0]?.id;render(await call('status'));}).catch(e=>$('status').textContent=e.message);
setInterval(()=>call('status').then(render).catch(()=>{}),1000);
