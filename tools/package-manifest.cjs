// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors
// Seal the source-only package and reject common accidental private artifacts.
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const excluded = new Set(['manifest.json', 'sha256.txt', 'manifest.json.sha256']);
function walk(dir) {
  return fs.readdirSync(dir).filter(n => n !== '.git').flatMap(n => {
    const full = path.join(dir, n);
    if (fs.lstatSync(full).isSymbolicLink()) throw Error('Symlinks are not accepted in the publication package');
    return fs.statSync(full).isDirectory() ? walk(full) : [full];
  });
}
const files = [];
for (const full of walk(root)) {
  const relative = path.relative(root, full).replaceAll('\\', '/');
  if (excluded.has(relative)) continue;
  if (relative.includes('__pycache__') || /\.(glb|blend|vrm|fbx|png|jpg|pyc|zip)$/i.test(relative)) throw Error('Unexpected asset/cache: ' + relative);
  const data = fs.readFileSync(full), text = data.toString('utf8');
  if (text.includes('\r\n')) throw Error('Normalize text to LF before sealing: ' + relative);
  if (relative !== 'LICENSE' && !text.slice(0, 800).includes('SPDX-License-Identifier')) throw Error('Missing SPDX header: ' + relative);
  if (/[A-Za-z]:[\\/](?:Users|ProgramData|Staging|tripo-studio|hostshare)/i.test(text) || /\\\\(?:vboxsvr|VBoxSvr)\\/.test(text)) throw Error('Machine-specific path in ' + relative);
  if (/\b(?:Bearer|Cookie:)\s+[a-zA-Z0-9_.=-]{20,}/.test(text) || /\bgh[pousr]_[A-Za-z0-9]{20,}/.test(text)) throw Error('Potential credential in ' + relative);
  files.push({path: relative, bytes: data.length, sha256: crypto.createHash('sha256').update(data).digest('hex')});
}
files.sort((a, b) => a.path.localeCompare(b.path));
const manifest = {'SPDX-License-Identifier': 'GPL-3.0-or-later', 'SPDX-FileCopyrightText': '2026 Head Workflow contributors', name: 'head-workflow', version: '0.1.5-dev', license: 'GPL-3.0-or-later', status: 'Measured corrections reproduced outside Lab; direct Smart Mesh native render succeeded but continuous skin-boundary attachment failed; primary model withheld, no retry; historical verification retained', files};
fs.writeFileSync(path.join(root, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
const hash = crypto.createHash('sha256').update(fs.readFileSync(path.join(root, 'manifest.json'))).digest('hex');
const header = '# SPDX-License-Identifier: GPL-3.0-or-later\n# SPDX-FileCopyrightText: 2026 Head Workflow contributors\n';
fs.writeFileSync(path.join(root, 'sha256.txt'), header + files.map(f => f.sha256 + '  ' + f.path).join('\n') + '\n' + hash + '  manifest.json\n');
fs.writeFileSync(path.join(root, 'manifest.json.sha256'), header + hash + '  manifest.json\n');
console.log(JSON.stringify({files: files.length + 3, bytes: files.reduce((n, f) => n + f.bytes, 0), machinePaths: 0, potentialCredentials: 0, bundledModelAssets: 0, manifest_sha256: hash}, null, 2));
