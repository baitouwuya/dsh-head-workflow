// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors
// Structural export checks. Does not substitute for Blender anatomy or WebGL deformation tests.
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
function verify(filename, manifest) {
  const buffer = fs.readFileSync(filename);
  if (buffer.length < 20 || buffer.readUInt32LE(0) !== 0x46546c67 || buffer.readUInt32LE(4) !== 2 || buffer.readUInt32LE(8) !== buffer.length) throw Error('Invalid GLB header');
  let gltf, binary;
  for (let offset = 12; offset < buffer.length;) {
    if (offset + 8 > buffer.length) throw Error('Truncated chunk');
    const size = buffer.readUInt32LE(offset), kind = buffer.readUInt32LE(offset + 4);
    if (offset + size + 8 > buffer.length) throw Error('Truncated chunk data');
    const chunk = buffer.subarray(offset + 8, offset + 8 + size);
    if (kind === 0x4e4f534a) gltf = JSON.parse(chunk.toString());
    if (kind === 0x004e4942) binary = chunk;
    offset += size + 8;
  }
  if (!gltf || !binary) throw Error('Expected embedded JSON and binary chunks');
  if ((gltf.buffers || []).some(b => b.uri) || (gltf.images || []).some(i => i.uri)) throw Error('GLB must embed its resources');
  let checkedFloats = 0;
  for (const accessor of gltf.accessors || []) {
    if (accessor.componentType !== 5126) continue;
    const dimension = {SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT2: 4, MAT3: 9, MAT4: 16}[accessor.type];
    if (!dimension) throw Error('Invalid accessor type');
    function range(viewIndex, localOffset, length) {
      const view = gltf.bufferViews[viewIndex];
      if (!view || (view.buffer || 0) !== 0 || localOffset < 0 || localOffset + length > view.byteLength || (view.byteOffset || 0) + view.byteLength > binary.length) throw Error('Accessor exceeds buffer view');
      return (view.byteOffset || 0) + localOffset;
    }
    if (accessor.bufferView !== undefined) {
      const view = gltf.bufferViews[accessor.bufferView];
      if (!view) throw Error('Invalid accessor');
      const stride = view.byteStride || dimension * 4;
      const offset = range(accessor.bufferView, accessor.byteOffset || 0, accessor.count ? (accessor.count - 1) * stride + dimension * 4 : 0);
      for (let i = 0; i < accessor.count; i++) for (let k = 0; k < dimension; k++) {
        if (!Number.isFinite(binary.readFloatLE(offset + i * stride + k * 4))) throw Error('Non-finite exported coordinate or weight');
        checkedFloats++;
      }
    }
    if (accessor.sparse) {
      const sparse = accessor.sparse;
      const width = {5121: 1, 5123: 2, 5125: 4}[sparse.indices.componentType];
      if (!width || sparse.count > accessor.count) throw Error('Invalid sparse accessor');
      const indexOffset = range(sparse.indices.bufferView, sparse.indices.byteOffset || 0, sparse.count * width);
      const valueOffset = range(sparse.values.bufferView, sparse.values.byteOffset || 0, sparse.count * dimension * 4);
      let previous = -1;
      for (let i = 0; i < sparse.count; i++) {
        const index = binary.readUIntLE(indexOffset + i * width, width);
        if (index <= previous || index >= accessor.count) throw Error('Invalid sparse index');
        previous = index;
        for (let k = 0; k < dimension; k++) {
          if (!Number.isFinite(binary.readFloatLE(valueOffset + (i * dimension + k) * 4))) throw Error('Non-finite sparse morph value');
          checkedFloats++;
        }
      }
    }
  }
  const bones = [...new Set((gltf.skins || []).flatMap(s => s.joints.map(i => gltf.nodes[i]?.name)))];
  const morphs = [...new Set((gltf.meshes || []).flatMap(m => m.extras?.targetNames || []))];
  for (const name of [manifest.jaw.bone, ...Object.values(manifest.eye_bones)]) if (!bones.includes(name)) throw Error('Missing bone ' + name);
  for (const name of [...manifest.original_controls, ...manifest.added_morphs, ...manifest.blink.left, ...manifest.blink.right]) if (!morphs.includes(name)) throw Error('Missing morph ' + name);
  const meshes = (gltf.nodes || []).filter(n => n.mesh !== undefined);
  if (meshes.some(n => /vroid|gnm|PD_Avatar|Detached/i.test(n.name || ''))) throw Error('Unexpected reference-model mesh name');
  if ((gltf.materials || []).some(m => /N00_000|vroid|GNM/i.test(m.name || ''))) throw Error('Unexpected reference-model material name');
  return {file: path.basename(filename), sha256: crypto.createHash('sha256').update(buffer).digest('hex'), bytes: buffer.length,
    generator: gltf.asset.generator, meshNodes: meshes.length, bones: bones.length, morphs, checkedFloats, passed: true};
}
module.exports = {verify};
if (require.main === module) {
  if (process.argv.length < 4) throw Error('Usage: node tools/verify-glb.cjs head.glb control_manifest.json [report.json]');
  const report = verify(process.argv[2], JSON.parse(fs.readFileSync(process.argv[3])));
  if (process.argv[4]) fs.writeFileSync(process.argv[4], JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}
