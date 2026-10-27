// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors
import * as THREE from 'three';
import {GLTFLoader} from '/vendor/loaders/GLTFLoader.js';
import {createHeadController as hostCreate} from '/host/head-controller.js';
import {createHeadController as candidateCreate} from '/candidate/head-controller.js';
const status=document.querySelector('#status');let stopped=false;
document.querySelector('#stop').onclick=()=>{stopped=true;status.textContent='Stopping…';};
const instances=[];let renderer;
try{
 const bindings=await fetch('/bindings.json').then(r=>r.json());
 const scene=new THREE.Scene();scene.background=new THREE.Color('#777777');
 scene.add(new THREE.HemisphereLight(0xffffff,0x555566,2));
 const light=new THREE.DirectionalLight(0xffffff,1.2);light.position.set(1,1.5,-.7);scene.add(light);
 const canvas=document.createElement('canvas');renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});renderer.setPixelRatio(1);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 const camera=new THREE.OrthographicCamera(-.085,.085,.085,-.085,.01,10);
 for(const [role,create] of [['host',hostCreate],['candidate',candidateCreate]]){
  const manifest=await fetch('/'+role+'/control_manifest.json').then(r=>r.json()),gltf=await new GLTFLoader().loadAsync('/'+role+'/head.glb');
  scene.add(gltf.scene);gltf.scene.visible=false;
  const runtime=structuredClone(manifest);
  const control=create(gltf.scene,runtime);control.apply({});
  const box=new THREE.Box3().setFromObject(gltf.scene);
  instances.push({role,manifest,runtime,root:gltf.scene,control,restJaw:control.jaw.quaternion.clone(),neutralBounds:{min:box.min.toArray(),max:box.max.toArray()}});
 }
 const [host,candidate]=instances;
 // Diagnostic blink review only; production acceptance and mouth repair remain deferred.
 const check=()=>{if(stopped)throw Error('Stopped by operator');};
 function valuesFor(instance,pose){const values={...(pose.values||{})};if(pose.degrees!==undefined)values.jawOpen=pose.degrees/instance.runtime.jaw.maximum_degrees;return values;}
 function setupView(view,detail){
  const target=detail==='mouth'?new THREE.Vector3(.02,.875,-.002):detail==='lids'?new THREE.Vector3(.02,.908,-.002):new THREE.Vector3(0,.925,-.002);
  const offset={front:[.5,0,0],left45:[.355,0,-.355],right45:[.355,0,.355],profile:[0,0,-.5]}[view];
  const height=detail==='mouth'?.05:detail==='lids'?.075:.17;
  camera.left=camera.bottom=-height/2;camera.right=camera.top=height/2;camera.position.copy(target).add(new THREE.Vector3(...offset));camera.lookAt(target);camera.updateProjectionMatrix();
  return {view,detail,target:target.toArray(),position:camera.position.toArray(),orthographicHeight:height};
 }
 const cameras=[];
 async function sheet(name,title,poses,pairColumns,size,detail){
  const cellW=size+16,cellH=size+62,columns=pairColumns*2,rows=Math.ceil(poses.length/pairColumns);
  const image=document.createElement('canvas');image.width=columns*cellW+24;image.height=rows*cellH+118;const ctx=image.getContext('2d');ctx.fillStyle='#14202d';ctx.fillRect(0,0,image.width,image.height);ctx.fillStyle='#eff7ff';ctx.font='bold 30px Arial';ctx.fillText(title,16,42);ctx.font='18px Arial';ctx.fillStyle='#b9cddd';ctx.fillText('Same scale, camera, lighting and shading. HOST on the left / LAB on the right of each pair.',16,75);renderer.setSize(size,size);
  for(let i=0;i<poses.length;i++){
   const pose=poses[i];cameras.push(setupView(pose.view,detail));
   for(let side=0;side<2;side++){
    check();const instance=instances[side],x=12+(i%pairColumns*2+side)*cellW,y=94+Math.floor(i/pairColumns)*cellH;
    const unsupported=instance.role==='candidate'&&pose.degrees>instance.manifest.jaw.maximum_degrees;
    if(unsupported){ctx.fillStyle='#382b31';ctx.fillRect(x,y,size,size);ctx.fillStyle='#fff';ctx.font='18px Arial';ctx.fillText('Outside declared Lab range',x+15,y+size/2);}
    else{for(const model of instances)model.root.visible=model===instance;instance.control.apply(valuesFor(instance,pose));renderer.render(scene,camera);ctx.drawImage(canvas,x,y);instance.control.apply({});}
    ctx.fillStyle=side?'#594622':'#233b54';ctx.fillRect(x,y+size,size,48);ctx.fillStyle='#fff';ctx.font='bold 17px Arial';
    ctx.fillText((side?'LAB':'HOST')+' · '+pose.label+' · '+pose.view,x+8,y+size+20);
    ctx.font='14px Arial';ctx.fillText(instance.role==='host'&&pose.degrees>instance.manifest.jaw.maximum_degrees?'Diagnostic: above prior '+instance.manifest.jaw.maximum_degrees+'° range':unsupported?'Not certified':detail==='overview'?'Unretouched model render':'Geometry close-up',x+8,y+size+40);
   }
   status.textContent=title+' '+(i+1)+'/'+poses.length;await new Promise(requestAnimationFrame);
  }
  const blob=await new Promise(resolve=>image.toBlob(resolve,'image/png'));const response=await fetch('/save/'+name,{method:'POST',body:blob});if(!response.ok)throw Error(await response.text());
  const display=document.createElement('img');display.src=URL.createObjectURL(blob);display.alt=title;document.querySelector('#images').append(display);
 }
 const overview=[{label:'Neutral',view:'front'},{label:'Neutral',view:'left45'},{label:'Neutral',view:'profile'},{label:'Blink 50%',view:'front',values:{blink:.5}},{label:'Blink 100%',view:'front',values:{blink:1}},{label:'Blink 100%',view:'left45',values:{blink:1}}];
 await sheet('comparison.png','DIAGNOSTIC BLINK STAGE — ORIGINAL / EDITED EXPORT',overview,3,320,'overview');
 const lids=[0,.5,1].flatMap(blink=>['front','left45'].map(view=>({label:'Blink '+blink*100+'%',view,values:{blink}})));
 await sheet('lids-detail.png','DIAGNOSTIC EYELIDS — ORIGINAL / EDITED EXPORT',lids,2,512,'lids');
 const v=new THREE.Vector3();
 const positions=()=>candidate.control.meshes.map(mesh=>{const a=new Float64Array(mesh.geometry.attributes.position.count*3);for(let i=0;i<a.length/3;i++){mesh.getVertexPosition(i,v).applyMatrix4(mesh.matrixWorld);a.set(v.toArray(),i*3);}return a;});
 function globe(mesh){const names=new Set(Object.values(candidate.manifest.eye_bones));const index=mesh.geometry.attributes.skinIndex,weights=mesh.geometry.attributes.skinWeight;if(!index||!weights||!mesh.skeleton)return false;for(let i=0;i<weights.count;i++)for(let k=0;k<4;k++)if(weights.getComponent(i,k)>1e-5&&!names.has(mesh.skeleton.bones[index.getComponent(i,k)]?.name))return false;return true;}
 const eyeIndices=candidate.control.meshes.flatMap((m,i)=>globe(m)?[i]:[]);if(eyeIndices.length<2)throw Error('Both eyeballs were not identified for blink verification');
 const poses=[{name:'neutral',values:{}}];for(const name of [...candidate.manifest.original_controls,...candidate.manifest.added_morphs])poses.push({name,values:{[name]:1}});
 for(const name of ['blinkLeft','blinkRight','blink'])for(const weight of [.25,.5,.75,1])poses.push({name:name+'_'+weight,values:{[name]:weight},blink:true});
 for(const degrees of [...new Set([5,8,10,15,18,20,candidate.manifest.jaw.maximum_degrees])].filter(d=>d<=candidate.manifest.jaw.maximum_degrees))poses.push({name:'jaw_'+degrees,degrees,values:{jawOpen:degrees/candidate.manifest.jaw.maximum_degrees}});
 for(const [name,values] of Object.entries(candidate.manifest.recipes))if(name!=='neutral')poses.push({name,values});
 candidate.control.apply({});const baseline=positions(),rows=[];let resetMax=0;
 for(const pose of poses){check();candidate.control.apply(pose.values);const current=positions();let max=0,eyeMax=0,finite=true;current.forEach((a,m)=>{for(let i=0;i<a.length;i+=3){const d=Math.hypot(a[i]-baseline[m][i],a[i+1]-baseline[m][i+1],a[i+2]-baseline[m][i+2]);if(!Number.isFinite(d))finite=false;max=Math.max(max,d);if(eyeIndices.includes(m))eyeMax=Math.max(eyeMax,d);}});rows.push({...pose,finite,maxDisplacement:max,eyeMaxDisplacement:eyeMax,jawDegrees:THREE.MathUtils.radToDeg(candidate.control.jaw.quaternion.angleTo(candidate.restJaw))});candidate.control.apply({});positions().forEach((a,m)=>a.forEach((n,i)=>{resetMax=Math.max(resetMax,Math.abs(n-baseline[m][i]));}));await new Promise(requestAnimationFrame);}
 const report={bindings,engine:'Three.js r'+THREE.REVISION,cameras,modelTransformsUnchanged:true,neutralBounds:instances.map(i=>({role:i.role,...i.neutralBounds})),candidateMaximumJawDegrees:candidate.manifest.jaw.maximum_degrees,hostPriorMaximumJawDegrees:host.manifest.jaw.maximum_degrees,hostStressMaximumJawDegrees:8,stage:"blink diagnostic",productionAcceptance:"UNACCEPTED — anatomy/rays and mouth stage are not certified by this viewer",states:rows,allFinite:rows.every(r=>r.finite),allNonNeutralMoved:rows.slice(1).every(r=>r.maxDisplacement>0),blinkEyeballsStationary:rows.filter(r=>r.blink).every(r=>r.eyeMaxDisplacement<1e-7),jawEyeballsStationary:rows.filter(r=>r.degrees!==undefined).every(r=>r.eyeMaxDisplacement<1e-7),jawAngleAccurate:rows.filter(r=>r.degrees!==undefined).every(r=>Math.abs(r.jawDegrees-r.degrees)<.001),resetMax,visualQualityVerdict:'Requires inspection of comparison and close-up images; numeric checks alone do not certify quality.'};
 if(!report.allFinite||!report.allNonNeutralMoved||!report.blinkEyeballsStationary||!report.jawEyeballsStationary||!report.jawAngleAccurate||resetMax!==0)throw Error('Candidate numeric verification failed');
 const response=await fetch('/save/report.json',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(report,null,2)});if(!response.ok)throw Error(await response.text());status.textContent='Saved matched comparison and close-ups; '+rows.length+' candidate kinematic states passed. Full geometry/ray acceptance is NOT established.';
}catch(error){status.textContent='ERROR: '+error.message;console.error(error);}finally{for(const instance of instances)instance.control.apply({});renderer?.dispose();document.querySelector('#stop').disabled=true;}
