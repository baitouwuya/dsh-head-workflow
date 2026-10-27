// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

chrome.runtime.onMessage.addListener((msg,sender,sendResponse)=>{
  if(sender.id!==chrome.runtime.id||!sender.url?.startsWith('https://studio.tripo3d.ai/projects')||msg?.type!=='dsh-write')return;
  const body=msg.payload;
  if(!body||!['runs','out','artifacts','health'].includes(body.area)){sendResponse({ok:false,error:'Writer envelope refused',bridgeBuild:'0.2.59-artifacts',area:typeof body?.area==='string'?body.area:null});return;}
  const health=body.area==='health';
  fetch('http://127.0.0.1:43127/'+(health?'health':'write'),{method:health?'GET':'POST',headers:{'Content-Type':'application/json','X-DSH-Writer':'v020'},...(health?{}:{body:JSON.stringify(body)})}).then(async r=>{const v=await r.json();sendResponse(health?{...v,bridgeBuild:'0.2.59-artifacts'}:v);}).catch(()=>sendResponse({ok:false,error:'Local writer unavailable'}));
  return true;
});







