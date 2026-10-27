// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

(function(root){
  'use strict';
  const clone=x=>JSON.parse(JSON.stringify(x));
  const LAB='NODE_TYPE_AI_3D_LAB';
  function assets(state){
    const found=new Map();
    for(const node of state.nodes||[])for(const asset of [...(node.nodeAssets||[]),...(node.inputMount||[])]){
      if(!asset.assetId)continue;
      const item=found.get(asset.assetId)||{assetId:asset.assetId,nodeIds:[],references:[]};
      if(!item.nodeIds.includes(node.id))item.nodeIds.push(node.id);
      item.references.push(clone(asset));found.set(asset.assetId,item);
    }
    return [...found.values()];
  }
  function labInput(body,args,state=body,observedPorts={}){
    const next=clone(body),node=next.nodes.find(n=>n.id===args.nodeId);
    if(!node||node.type!==LAB)throw Error('nodeId must identify a Lab on the open canvas.');
    if(typeof args.assetId!=='string'||!args.assetId)throw Error('assetId is required.');
    if(!assets(body).some(a=>a.assetId===args.assetId))throw Error('Asset is not on the open canvas. Publish/import it here first.');
    if(args.replace!==undefined&&typeof args.replace!=='boolean')throw Error('replace must be boolean.');
    // Studio rejects direct model inputMount on Labs. Their native socket consumes
    // the selected upstream output through an edge; never silently select another asset.
    const owners=next.nodes.filter(n=>n.id!==node.id&&(
      n.type==='NODE_TYPE_UPLOAD_CARD'&&(n.inputMount||[]).some(a=>a.assetId===args.assetId)||
      (n.nodeAssets||[]).some(a=>a.assetId===args.assetId)&&
      ((state.nodeRuns||[]).find(r=>r.nodeId===n.id)?.selectedAssetId===args.assetId||
       !(state.nodeRuns||[]).find(r=>r.nodeId===n.id)?.selectedAssetId&&n.nodeAssets.length===1)
    ));
    if(!owners.length)throw Error('The asset must be the selected output of an upstream canvas node or an upload reference. No source selection was changed.');
    const priorEdges=clone(next.edges||[]);
    const existing=priorEdges.find(e=>e.target?.nodeId===node.id&&e.target?.port==='input'&&owners.some(n=>n.id===e.source?.nodeId));
    const owner=owners.find(n=>n.id===existing?.source.nodeId)||owners[0];
    if(args.replace===true)next.edges=next.edges.filter(e=>e.target?.nodeId!==node.id||e.target?.port!=='input'||e.source?.nodeId===owner.id);
    const linked=connect(next,{from:owner.id,to:node.id,fromPort:existing?.source.port||'auto',toPort:'input',edgeId:args.edgeId},observedPorts);
    return {...linked,nodeId:node.id,assetId:args.assetId,sourceNodeId:owner.id,binding:'native-edge',changed:JSON.stringify(priorEdges)!==JSON.stringify(linked.body.edges),previousInputMount:clone(node.inputMount||[]),inputMount:clone(node.inputMount||[])};
  }
  function connect(body,args,observedPorts={}){
    const next=clone(body),from=next.nodes.find(n=>n.id===args.from),to=next.nodes.find(n=>n.id===args.to);
    if(!from||!to)throw Error('Both connection nodes must be in the open canvas.');
    if(from.id===to.id)throw Error('A node cannot connect to itself.');
    const resolve=(node,side,supplied)=>{
      // Empty/default remains the legacy contract; explicit non-image ports are validated.
      if(supplied===undefined||supplied==='')return '';
      if(typeof supplied!=='string')throw Error('Ports must be strings.');
      const rendered=new Set(observedPorts[node.id]?.[side]||[]),seen=new Set(rendered);
      for(const e of body.edges||[]){const end=side==='source'?e.source:e.target;if(end?.nodeId===node.id&&end.port)seen.add(end.port);}
      if(node.type===LAB)seen.add(side==='source'?'output':'input');
      if(node.type==='NODE_TYPE_UPLOAD_CARD'&&node.params?.assetType)seen.add(node.params.assetType);
      const imageTypes=['NODE_TYPE_GENERATE_IMAGE','NODE_TYPE_CUTOUT','NODE_TYPE_MULTIVIEW'];
      const modelTypes=['NODE_TYPE_GENERATE_SM_MODEL','NODE_TYPE_GENERATE_HD_MODEL','NODE_TYPE_TEXTURE','NODE_TYPE_RIGGING','NODE_TYPE_SMART_UV','NODE_TYPE_RETOPOLOGY','NODE_TYPE_SEGMENTATION','NODE_TYPE_PBR'];
      if(imageTypes.includes(node.type))seen.add('image');
      if(modelTypes.includes(node.type))seen.add(side==='target'&&/GENERATE_(?:SM|HD)_MODEL/.test(node.type)?'image':'model');
      if(supplied==='auto'){
        if(rendered.size===1)return [...rendered][0];
        if(rendered.size>1)throw Error('Port is ambiguous; specify fromPort/toPort from rendered handles or saved edges.');
        const candidates=[...seen];if(candidates.length!==1)throw Error('Port is ambiguous; specify fromPort/toPort from rendered handles or saved edges.');return candidates[0];
      }
      if(!seen.has(supplied))throw Error('Port '+supplied+' was not observed for '+node.id+' '+side+'.');return supplied;
    };
    const source={nodeId:from.id,port:resolve(from,'source',args.fromPort)},target={nodeId:to.id,port:resolve(to,'target',args.toPort)};
    const old=next.edges.find(e=>e.source?.nodeId===source.nodeId&&e.source?.port===source.port&&e.target?.nodeId===target.nodeId&&e.target?.port===target.port);
    if(old)return {body:next,edgeId:old.id,changed:false,source,target};
    const edge={id:args.edgeId||root.crypto.randomUUID(),source,target};next.edges.push(edge);
    return {body:next,edgeId:edge.id,changed:true,source,target};
  }
  function reference(body,{assetId,filename,format,kind,name,position,nodeId}){
    if(!assetId||!nodeId)throw Error('Imported asset and new reference-node IDs are required.');
    const next=clone(body);if(next.nodes.some(n=>n.id===nodeId))throw Error('Reference node already exists.');
    if(!position||!Number.isFinite(position.x)||!Number.isFinite(position.y))throw Error('Finite reference-node position is required.');
    const assetType=kind==='image'?'image':'model';
    const params={assetType};
    if(assetType==='model')params.uploadSource={assetId,format,transformMatrix:[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]};
    const node={id:nodeId,type:'NODE_TYPE_UPLOAD_CARD',name:name||filename,params,ui:{position},inputMount:[{assetId}],nodeAssets:[],displayNo:'#'+(next.nodes.length+1),batchId:'',extraction:null};
    next.nodes.push(node);return {body:next,nodeId,assetId};
  }
  const api={assets,labInput,connect,reference};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.__dshCanvasAssets=api;
})(typeof window==='undefined'?globalThis:window);
