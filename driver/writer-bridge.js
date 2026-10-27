// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(() => {
  const {allowsName,allowsArtifactName}=globalThis.__dshWriterContract;
  const markReady=()=>{if(document.documentElement)document.documentElement.dataset.dshWriterBridgeReady='0.2.59-artifacts';else setTimeout(markReady,20);};markReady();
  document.addEventListener('dsh-writer-request',async e=>{
    const d=e.detail;if(!d||typeof d.id!=='string'||!d.payload)return;
    const p=d.payload;
    if(p.area==='runs'&&(!/^p3-(?:run|recording|dry)-[0-9]{13}$/.test(p.run)||!allowsName(p.name)||typeof p.text!=='string'||p.text.length>4*1024*1024))return;
    if(p.area==='out'&&(!/^dsh-run-[0-9]{13}-[-a-z0-9]{1,48}\.(?:glb|fbx)$/.test(p.name)||typeof p.base64!=='string'||p.base64.length>1400000))return;
    if(p.area==='artifacts'&&(!allowsArtifactName(p.name)||typeof p.base64!=='string'||p.base64.length>1400000))return;
    if(!['runs','out','artifacts','health'].includes(p.area))return;
    let result;try{result=await chrome.runtime.sendMessage({type:'dsh-write',payload:p});}catch{result={ok:false,error:'Local writer bridge unavailable'};}
    document.dispatchEvent(new CustomEvent('dsh-writer-response',{detail:{id:d.id,result}}));
  });
})();

