// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors
import * as THREE from 'three';
export function createHeadController(root, manifest) {
 const meshes=[];root.traverse(o=>{if(o.isMesh)meshes.push(o);});
 root.updateMatrixWorld(true);
 const jaw=root.getObjectByName(manifest.jaw.bone);
 if(!jaw)throw Error('Missing jaw bone '+manifest.jaw.bone);
 const rest=jaw.quaternion.clone();
 const modelWorld=root.getWorldQuaternion(new THREE.Quaternion());
 const axis=new THREE.Vector3(...manifest.jaw.axis_gltf_model).applyQuaternion(modelWorld).applyQuaternion(jaw.getWorldQuaternion(new THREE.Quaternion()).invert()).normalize();
 const eyes={};
 for(const [side,name] of Object.entries(manifest.eye_bones)){
  const bone=root.getObjectByName(name);if(bone)eyes[side]={bone,rest:bone.quaternion.clone(),yaw:new THREE.Vector3(0,1,0).applyQuaternion(modelWorld).applyQuaternion(bone.getWorldQuaternion(new THREE.Quaternion()).invert()).normalize()};
 }
 const clamp=v=>Math.min(1,Math.max(0,Number(v)||0));
 function apply(values={}){
  for(const mesh of meshes){
   if(!mesh.morphTargetInfluences)continue;
   mesh.morphTargetInfluences.fill(0);
   const dict=mesh.morphTargetDictionary;
   for(const [name,value] of Object.entries(values))if(dict[name]!==undefined)mesh.morphTargetInfluences[dict[name]]=clamp(value);
   for(const [side,label] of [['left','Left'],['right','Right']]){
    const w=Math.max(clamp(values.blink),clamp(values['blink'+label]));
    const step=Math.floor(w*4),t=w*4-step;
    if(step>0&&dict['blink'+label+'_'+step*25]!==undefined)mesh.morphTargetInfluences[dict['blink'+label+'_'+step*25]]=1-t;
    if(step<4&&t>0&&dict['blink'+label+'_'+(step+1)*25]!==undefined)mesh.morphTargetInfluences[dict['blink'+label+'_'+(step+1)*25]]=t;
   }
  }
  jaw.quaternion.copy(rest).multiply(new THREE.Quaternion().setFromAxisAngle(axis,THREE.MathUtils.degToRad(manifest.jaw.maximum_degrees)*clamp(values.jawOpen)));
  for(const eye of Object.values(eyes))eye.bone.quaternion.copy(eye.rest).multiply(new THREE.Quaternion().setFromAxisAngle(eye.yaw,THREE.MathUtils.degToRad(10)*Math.max(-1,Math.min(1,Number(values.gaze)||0))));
  root.updateMatrixWorld(true);for(const m of meshes)if(m.skeleton)m.skeleton.update();
 }
 return {apply,meshes,jaw,axis,recipes:manifest.recipes};
}

