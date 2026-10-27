// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(function(root){
  'use strict';
  const actions=['listCanvasAssets','listLabArtifacts','setLabInput','publishLabArtifact','labDownloadArtifact'];
  const id=v=>typeof v==='string'&&v.length>0;
  function create(A){
    async function run(name,args={},signal){
      if(!actions.includes(name))throw Error('Unknown Lab asset action.');
      await A.ready(signal);const opened=A.target(args),projectId=opened.projectId,canvasId=opened.canvasId;
      const check=()=>{if(signal?.aborted)throw Error('Stopped');A.target({projectId,canvasId});};
      const state=await A.read(args,signal);check();
      if(name==='listCanvasAssets')return {mode:'read',canvasId,assets:A.planners.assets(state),mutatingRequestsSent:0};
      const node=state.nodes.find(n=>n.id===args.nodeId);
      if(!node||node.type!=='NODE_TYPE_AI_3D_LAB')throw Error('nodeId must identify a Lab on the open canvas.');
      if(name==='listLabArtifacts'){
        const list=await A.request('LabService/ListLabJobs',{nodeId:node.id},signal);check();
        const jobs=[...(list.jobs||[]),...(list.activeJob?[list.activeJob]:[])];
        if(!args.jobId)return {mode:'read',nodeId:node.id,jobs:[...new Map(jobs.map(j=>[j.jobId,{jobId:j.jobId,status:j.status??null}])).values()],activeJobId:list.activeJob?.jobId||null,mutatingRequestsSent:0};
        if(!jobs.some(j=>j.jobId===args.jobId))throw Error('Job is not associated with this Lab on the open canvas.');
        const job=await A.request('LabService/GetLabJob',{jobId:args.jobId},signal);check();
        if(job.jobId!==args.jobId)throw Error('Lab job identity mismatch.');
        return {mode:'read',nodeId:node.id,jobId:job.jobId,status:job.status,...(args.includeProgress?{phase:job.phase,deliveryState:job.deliveryState,errorCode:job.errorCode,errorMessage:job.errorMessage,phaseTimings:job.phaseTimings,lines:(job.lines||[]).slice(-10).map(l=>({seq:l.seq,kind:l.kind,text:String(l.text||'').slice(-6000)}))}:{}),artifacts:(job.artifacts||[]).map(a=>({artifactId:a.artifactId,nodeAssetId:a.nodeAssetId||null,kind:a.kind,title:a.title||null,filename:a.downloadUrl?decodeURIComponent(new URL(a.downloadUrl).pathname.split('/').pop()):null})),mutatingRequestsSent:0};
      }
      if(name==='setLabInput'){
        const plan=A.planners.labInput(A.draft({}),{...args,edgeId:A.uuid()},state,A.observedPorts?.()||{});
        if(args.dryRun!==false)return {mode:'dry-run',...plan,mutatingRequestsSent:0};
        if(plan.changed){
          const jobs=await A.request('LabService/ListLabJobs',{nodeId:node.id},signal);check();
          if(jobs.activeJob)throw Error('Cannot change inputs while a Lab job is active.');
          const fresh=await A.read(args,signal);check();
          if(fresh.canvas.revision!==state.canvas.revision)throw Error('Canvas revision changed; re-plan before changing inputs.');
          await A.save(plan.body,signal);
        }
        const after=await A.read(args,signal);check();
        const actual=after.nodes.find(n=>n.id===node.id)?.inputMount||[];
        const edge=after.edges.find(e=>e.source?.nodeId===plan.source.nodeId&&e.source?.port===plan.source.port&&e.target?.nodeId===plan.target.nodeId&&e.target?.port===plan.target.port);
        if(!edge)throw Error('Lab input connection was not confirmed; inspect the canvas before retrying.');
        A.planners.labInput({nodes:after.nodes,edges:after.edges},{...args,edgeId:A.uuid()},after,A.observedPorts?.()||{});
        return {mode:'apply',nodeId:node.id,assetId:args.assetId,sourceNodeId:plan.sourceNodeId,binding:'native-edge',edgeId:edge.id,changed:plan.changed,inputMount:actual,mutatingRequestsSent:plan.changed?1:0,revision:after.canvas.revision};
      }
      if(!id(args.jobId)||!id(args.artifactId))throw Error('jobId and artifactId are required.');
      const list=await A.request('LabService/ListLabJobs',{nodeId:node.id},signal);check();
      if(![...(list.jobs||[]),...(list.activeJob?[list.activeJob]:[])].some(j=>j.jobId===args.jobId))throw Error('Job is not associated with this Lab on the open canvas.');
      const job=await A.request('LabService/GetLabJob',{jobId:args.jobId},signal);check();
      if(job.jobId!==args.jobId)throw Error('Lab job identity mismatch.');
      const artifact=job.artifacts?.find(a=>a.artifactId===args.artifactId);
      if(!artifact)throw Error('Artifact is not in the requested Lab job.');
      const url=new URL(artifact.downloadUrl),filename=decodeURIComponent(url.pathname.split('/').pop());
      if(url.protocol!=='https:')throw Error('Native artifact must have an HTTPS download URL.');
      const extension=filename.split('.').pop().toLowerCase();
      const descriptor={nodeId:node.id,jobId:job.jobId,artifactId:artifact.artifactId,filename,kind:artifact.kind,nodeAssetId:artifact.nodeAssetId||null};
      if(name==='labDownloadArtifact'){
        if(args.dryRun!==false)return {mode:'dry-run',...descriptor,source:'original-lab-artifact',converted:false,mutatingRequestsSent:0,downloadStarted:false};
        const download=await A.download(url.href,filename,signal,args);check();
        return {mode:'apply',...descriptor,source:'original-lab-artifact',converted:false,download,mutatingRequestsSent:0};
      }
      if(!['glb','png'].includes(extension))throw Error('Canvas publication currently supports native GLB and PNG artifacts. Other files can be downloaded with labDownloadArtifact.');
      if(job.status!=='completed')throw Error('Only a completed Lab job can publish an artifact.');
      const existing=artifact.nodeAssetId&&A.planners.assets(state).find(a=>a.assetId===artifact.nodeAssetId);
      if(existing)return {mode:args.dryRun===false?'apply':'dry-run',...descriptor,assetId:artifact.nodeAssetId,alreadyPublished:true,changed:false,mutatingRequestsSent:0};
      if(args.dryRun!==false)return {mode:'dry-run',...descriptor,operations:artifact.nodeAssetId?['reuse-native-asset','CanvasService/SaveCanvas']:['download-original','temporary_token','S3 PUT','AssetService/ImportInputAssets','CanvasService/SaveCanvas'],createsReferenceNode:true,changesExistingNodes:false,mutatingRequestsSent:0};
      const key='dsh-lab-publish-'+canvasId+'-'+artifact.artifactId;
      let journal=await A.load(key);check();
      if(journal&&(journal.canvasId!==canvasId||journal.projectId!==projectId||journal.jobId!==job.jobId||journal.artifactId!==artifact.artifactId||!id(journal.referenceNodeId)))throw Error('Publication journal identity mismatch.');
      if(journal?.phase==='complete')return {...journal.result,alreadyPublished:true};
      if(journal?.phase==='importing')throw Error('Previous import outcome is unknown. Inspect the saved publication journal; no duplicate upload/import was sent.');
      if(journal?.phase==='saving'){
        const found=state.nodes.find(n=>n.id===journal.referenceNodeId);
        if(!found?.inputMount?.some(a=>a.assetId===journal.assetId))throw Error('Previous reference save outcome is unknown; no duplicate save was sent.');
      }
      if(!journal){journal={phase:'prepared',canvasId,projectId,nodeId:node.id,jobId:job.jobId,artifactId:artifact.artifactId,referenceNodeId:A.uuid(),...(artifact.nodeAssetId?{assetId:artifact.nodeAssetId,reusedNativeAsset:true}:{})};await A.persist(key,journal);check();}
      if(!journal.assetId){
        const data=await A.readBytes(url.href,signal,args);check();
        A.validateBytes(data,extension);
        // Commit intent before the irreversible import. Never persist signed URLs or tokens.
        journal.phase='importing';await A.persist(key,journal);check();
        const imported=await A.importBytes(data,{filename,format:extension,mime:extension==='glb'?'model/gltf-binary':'image/png'},signal,args);check();
        if(!id(imported.assetId))throw Error('Import did not return an asset ID; outcome unknown.');
        journal.assetId=imported.assetId;journal.phase='imported';await A.persist(key,journal);check();
      }
      const fresh=await A.read(args,signal);check();
      const same=fresh.nodes.find(n=>n.id===journal.referenceNodeId);
      if(!same){
        const owner=fresh.nodes.find(n=>n.id===node.id);if(!owner)throw Error('Source Lab was removed; imported asset retained in journal.');
        const position=args.position||{x:(owner.ui?.position?.x||0)+420,y:owner.ui?.position?.y||0};
        const plan=A.planners.reference(A.draft({}),{assetId:journal.assetId,filename,format:extension,kind:extension==='png'?'image':'model',name:args.name||filename,position,nodeId:journal.referenceNodeId});
        journal.phase='saving';await A.persist(key,journal);check();await A.save(plan.body,signal);
      }else if(!same.inputMount?.some(a=>a.assetId===journal.assetId))throw Error('Reference node identity conflict.');
      const after=await A.read(args,signal);check();
      if(!after.nodes.find(n=>n.id===journal.referenceNodeId)?.inputMount?.some(a=>a.assetId===journal.assetId))throw Error('Publication save not confirmed; journal retained.');
      journal.result={mode:'apply',...descriptor,assetId:journal.assetId,referenceNodeId:journal.referenceNodeId,changed:true,source:'original-lab-artifact',reusedNativeAsset:!!journal.reusedNativeAsset,uploadedBytesUnchanged:!journal.reusedNativeAsset,canvasRepresentation:journal.reusedNativeAsset?'Existing native Lab asset reused.':'Studio may process imported models; inspect the resulting asset before claiming rig or image preservation.',revision:after.canvas.revision};
      journal.phase='complete';await A.persist(key,journal);return journal.result;
    }
    return {run};
  }
  const api={create,actions};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.__dshLabOperations=api;
})(typeof window==='undefined'?globalThis:window);
