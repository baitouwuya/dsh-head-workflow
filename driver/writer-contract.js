// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(function(root){
  'use strict';
  // Shared by the isolated browser bridge and the guest-local writer.
  const evidenceNames=Object.freeze(['checkpoint.json','trace.json','held-plan.json','log.txt','manifest.json','manifest.sha256','capture.json','recording.json','inverse-map.json','timing.json']);
  // Retain previously allowed evidence names; no permission or size-limit expansion.
  const legacyNames=Object.freeze(['baseline.json','dry-run.json']);
  const names=new Set([...evidenceNames,...legacyNames]);
  const allowsArtifactName=name=>typeof name==='string'&&/^dsh-artifact-[0-9]{13}-[a-f0-9]{8}-[a-z0-9-]{1,36}\.(?:glb|fbx|blend|zip|png|jpg|jpeg|json|md|txt|obj|stl|usd|usdz|3mf)$/.test(name);
  const contract=Object.freeze({evidenceNames,legacyNames,allowsName:name=>typeof name==='string'&&names.has(name),allowsArtifactName});
  if(typeof module!=='undefined'&&module.exports)module.exports=contract;
  else Object.defineProperty(root,'__dshWriterContract',{value:contract});
})(typeof globalThis==='undefined'?this:globalThis);

