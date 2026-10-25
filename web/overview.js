// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors
import * as THREE from 'three';
import {GLTFLoader} from './vendor/loaders/GLTFLoader.js';
import {createHeadController} from './head-controller.js';

const status = document.querySelector('#status');
let stopped = false;
document.querySelector('#stop').addEventListener('click', () => { stopped = true; status.textContent = 'Stopping after the current tile…'; });
let renderer, control;
try {
  const started = performance.now();
  const [manifest, view, binding, gltf] = await Promise.all([
    fetch('/control_manifest.json').then(r => r.json()), fetch('/viewer.json').then(r => r.json()),
    fetch('/input-binding.json').then(r => r.json()), new GLTFLoader().loadAsync('/head.glb')
  ]);
  const poses = [{label: 'Neutral', group: 'Reference', values: {}}];
  for (const key of [...manifest.original_controls, ...manifest.added_morphs]) poses.push({label: key + ' 100%', group: 'Individual control', values: {[key]: 1}});
  for (const [key, label] of [['blinkLeft', 'Left blink'], ['blinkRight', 'Right blink'], ['blink', 'Both blink'], ['jawOpen', 'Jaw']]) {
    for (const weight of [.25, .5, .75, 1]) poses.push({label: label + ' ' + weight * 100 + '%' + (key === 'jawOpen' ? ' / ' + weight * manifest.jaw.maximum_degrees + ' deg' : ''), group: key === 'jawOpen' ? 'Jaw bone' : 'Sampled eyelids', values: {[key]: weight}});
  }
  for (const [key, values] of Object.entries(manifest.recipes)) if (key !== 'neutral') poses.push({label: key, group: 'Full preset recipe', values});
  const canvas = document.createElement('canvas');
  renderer = new THREE.WebGLRenderer({canvas, antialias: true, preserveDrawingBuffer: true});
  renderer.setSize(384, 384); renderer.setPixelRatio(1);
  renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.NoToneMapping;
  const scene = new THREE.Scene(); scene.background = new THREE.Color('#777777');
  scene.add(new THREE.HemisphereLight(0xffffff, 0x555566, 2));
  const light = new THREE.DirectionalLight(0xffffff, 1.2); light.position.set(1, 1.5, -.7); scene.add(light);
  const half = view.ortho_height / 2;
  const camera = new THREE.OrthographicCamera(-half, half, half, -half, .01, 10);
  camera.position.set(...view.position); camera.lookAt(...view.target);
  scene.add(gltf.scene); control = createHeadController(gltf.scene, manifest);
  const sheet = document.querySelector('#sheet'); sheet.width = 2832; sheet.height = 132 + Math.ceil(poses.length / 7) * 464 + 76;
  const ctx = sheet.getContext('2d'); ctx.fillStyle = '#15202d'; ctx.fillRect(0, 0, sheet.width, sheet.height);
  ctx.fillStyle = '#f3f7fc'; ctx.font = 'bold 44px Arial'; ctx.fillText('HEAD WORKFLOW  /  EXPRESSION OVERVIEW', 24, 58);
  ctx.font = '24px Arial'; ctx.fillStyle = '#b6cadc'; ctx.fillText(poses.length + ' views • fixed front camera and lighting • individual controls at 100% • presets use saved mixes', 24, 103);
  const vector = new THREE.Vector3();
  function positions() {
    return control.meshes.map(mesh => {
      const out = new Float64Array(mesh.geometry.attributes.position.count * 3);
      for (let i = 0; i < out.length / 3; i++) { mesh.getVertexPosition(i, vector).applyMatrix4(mesh.matrixWorld); out.set(vector.toArray(), i * 3); }
      return out;
    });
  }
  function family(mesh) { const names = []; for (let p = mesh; p && p !== gltf.scene; p = p.parent) names.push(p.name); return names.join('/'); }
  const eyeMeshIndices = control.meshes.flatMap((m, i) => /closed.globe/i.test(family(m)) ? [i] : []);
  if (eyeMeshIndices.length < 2) throw Error('Cannot identify both closed globe meshes for the blink test');
  control.apply({}); const baseline = positions(); const rows = []; let resetMax = 0;
  for (let i = 0; i < poses.length; i++) {
    if (stopped) throw Error('Stopped by operator; no completed report saved');
    const pose = poses[i]; control.apply(pose.values); renderer.render(scene, camera);
    const x = 24 + i % 7 * 400, y = 132 + Math.floor(i / 7) * 464;
    ctx.drawImage(canvas, x, y, 384, 384); ctx.fillStyle = '#233447'; ctx.fillRect(x, y + 384, 384, 64);
    ctx.fillStyle = '#8dcbed'; ctx.font = '18px Arial'; ctx.fillText(pose.group, x + 12, y + 407);
    ctx.fillStyle = '#ffffff'; ctx.font = 'bold 22px Arial'; ctx.fillText(pose.label, x + 12, y + 435);
    const current = positions(); let maxDisplacement = 0, eyeMaxDisplacement = 0, finite = true;
    current.forEach((array, meshIndex) => {
      for (let j = 0; j < array.length; j += 3) {
        const distance = Math.hypot(...[0, 1, 2].map(k => array[j + k] - baseline[meshIndex][j + k]));
        if (!Number.isFinite(distance)) finite = false;
        maxDisplacement = Math.max(maxDisplacement, distance);
        if (eyeMeshIndices.includes(meshIndex)) eyeMaxDisplacement = Math.max(eyeMaxDisplacement, distance);
      }
    });
    rows.push({...pose, finite, maxDisplacement, eyeMaxDisplacement});
    control.apply({}); positions().forEach((array, m) => array.forEach((v, j) => { resetMax = Math.max(resetMax, Math.abs(v - baseline[m][j])); }));
    status.textContent = 'Rendered ' + (i + 1) + ' / ' + poses.length;
    await new Promise(requestAnimationFrame);
  }
  ctx.fillStyle = '#b6cadc'; ctx.font = '22px Arial';
  ctx.fillText('Left/right refer to the character • sampled eyelid interpolation • jaw maximum ' + manifest.jaw.maximum_degrees + ' degrees', 24, sheet.height - 48);
  ctx.fillText('Three.js r' + THREE.REVISION + ' • original mesh and textures • neutral reset between every view • no image generation or retouching', 24, sheet.height - 18);
  const report = {count: poses.length, width: sheet.width, height: sheet.height, elapsedMs: performance.now() - started, resetMax,
    allFinite: rows.every(r => r.finite), allNonNeutralMoved: rows.slice(1).every(r => r.maxDisplacement > 0),
    blinkLeavesEyeballsStationary: rows.filter(r => r.group === 'Sampled eyelids').every(r => r.eyeMaxDisplacement < 1e-7),
    eyeMeshPrimitives: eyeMeshIndices.length, engine: 'Three.js r' + THREE.REVISION, webgl2: renderer.capabilities.isWebGL2, binding, camera: view, rows};
  if (!report.allFinite || !report.allNonNeutralMoved || !report.blinkLeavesEyeballsStationary || resetMax !== 0) throw Error('Expression verification failed');
  if (stopped) throw Error('Stopped by operator');
  const blob = await new Promise(resolve => sheet.toBlob(resolve, 'image/png'));
  for (const [url, body, type] of [['/save-png', blob, 'image/png'], ['/save-report', JSON.stringify(report, null, 2), 'application/json']]) {
    const response = await fetch(url, {method: 'POST', headers: {'Content-Type': type}, body});
    if (!response.ok) throw Error(await response.text());
  }
  status.textContent = 'Complete: ' + report.count + ' views. Finite, moving controls; stationary eyeballs during blinks; exact neutral reset.';
} catch (error) {
  status.textContent = 'ERROR: ' + error.message;
  if (!stopped) console.error(error);
} finally {
  if (control) control.apply({});
  if (renderer) renderer.dispose();
  document.querySelector('#stop').disabled = true;
}
