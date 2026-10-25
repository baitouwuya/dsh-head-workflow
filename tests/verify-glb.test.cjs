// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const {verify} = require('../tools/verify-glb.cjs');
test('rejects a truncated GLB instead of claiming a successful export', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'head-glb-test-'));
  const file = path.join(dir, 'invalid.glb');
  try { fs.writeFileSync(file, Buffer.alloc(14)); assert.throws(() => verify(file, {}), /header/); }
  finally { fs.unlinkSync(file); fs.rmdirSync(dir); }
});

function sparseFixture(value, sparseIndex = 0) {
  const json = {asset: {version: '2.0'}, buffers: [{byteLength: 8}],
    bufferViews: [{buffer: 0, byteOffset: 0, byteLength: 1}, {buffer: 0, byteOffset: 4, byteLength: 4}],
    accessors: [{componentType: 5126, type: 'SCALAR', count: 1, sparse: {count: 1, indices: {bufferView: 0, componentType: 5121}, values: {bufferView: 1}}}],
    nodes: [{name: 'jaw'}, {name: 'eyeL'}, {name: 'eyeR'}], skins: [{joints: [0, 1, 2]}], meshes: []};
  let text = JSON.stringify(json); while (Buffer.byteLength(text) % 4) text += ' ';
  const body = Buffer.from(text), bin = Buffer.alloc(8); bin[0] = sparseIndex; bin.writeFloatLE(value, 4);
  const out = Buffer.alloc(12 + 8 + body.length + 8 + bin.length);
  out.writeUInt32LE(0x46546c67, 0); out.writeUInt32LE(2, 4); out.writeUInt32LE(out.length, 8);
  out.writeUInt32LE(body.length, 12); out.writeUInt32LE(0x4e4f534a, 16); body.copy(out, 20);
  const offset = 20 + body.length; out.writeUInt32LE(bin.length, offset); out.writeUInt32LE(0x004e4942, offset + 4); bin.copy(out, offset + 8);
  return out;
}
const controls = {jaw: {bone: 'jaw'}, eye_bones: {left: 'eyeL', right: 'eyeR'}, original_controls: [], added_morphs: [], blink: {left: [], right: []}};
for (const [name, value, index, error] of [['finite sparse morph', 1, 0, null], ['nonfinite sparse morph', NaN, 0, /Non-finite sparse/], ['out-of-range sparse index', 1, 2, /Invalid sparse index/]]) {
  test(name, () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'head-sparse-test-')), file = path.join(dir, 'fixture.glb');
    try {
      fs.writeFileSync(file, sparseFixture(value, index));
      if (error) assert.throws(() => verify(file, controls), error);
      else assert.equal(verify(file, controls).checkedFloats, 1);
    } finally { fs.unlinkSync(file); fs.rmdirSync(dir); }
  });
}
