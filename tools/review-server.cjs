// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors
// Local-only review host. Reads an external asset directory; writes into a new result directory.
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const crypto = require('node:crypto');
const args = process.argv.slice(2);
function option(name, fallback) {
  const index = args.indexOf(name);
  if (index < 0) return fallback;
  if (!args[index + 1] || args[index + 1].startsWith('--')) throw Error('Missing value for ' + name);
  return args[index + 1];
}
if (args.includes('--help')) {
  console.log('node tools/review-server.cjs --assets build/assets --output review-result [--port 56841] [--profile profiles/original-character.json]');
  process.exit(0);
}
const assetsArg = option('--assets'), outputArg = option('--output');
if (!assetsArg || !outputArg) throw Error('--assets and --output are required');
const assets = path.resolve(assetsArg), output = path.resolve(outputArg);
const web = path.resolve(__dirname, '../web');
const packageRoot = path.resolve(__dirname, '..');
const port = Number(option('--port', '56841'));
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw Error('Invalid port');
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
for (const file of ['head.glb', 'control_manifest.json']) if (!fs.statSync(path.join(assets, file)).isFile()) throw Error('Missing ' + file);
const profilePath = option('--profile');
const profile = profilePath ? JSON.parse(fs.readFileSync(profilePath)) : null;
const viewerPath = path.join(assets, 'viewer.json');
const viewer = profile?.viewer || (fs.existsSync(viewerPath) ? JSON.parse(fs.readFileSync(viewerPath)) : null);
if (!viewer) throw Error('Supply --profile or assets/viewer.json to define the fixed camera');
fs.mkdirSync(output, {recursive: false});
const binding = {
  model_sha256: hash(path.join(assets, 'head.glb')),
  control_manifest_sha256: hash(path.join(assets, 'control_manifest.json')),
  controller_sha256: hash(path.join(web, 'head-controller.js')),
  renderer_sha256: hash(path.join(web, 'overview.js')),
  three_revision: '180', viewer
};
fs.writeFileSync(path.join(output, 'input-binding.json'), JSON.stringify(binding, null, 2));
const mime = {'.js': 'text/javascript', '.html': 'text/html', '.json': 'application/json', '.glb': 'model/gltf-binary', '.png': 'image/png'};
const server = http.createServer((req, res) => {
  let url;
  try { url = new URL(req.url, 'http://127.0.0.1:' + port); } catch { res.writeHead(400).end(); return; }
  if (req.method === 'POST' && ['/save-png', '/save-report'].includes(url.pathname)) {
    if (req.headers.origin !== 'http://127.0.0.1:' + port) { res.writeHead(403).end(); return; }
    const parts = []; let bytes = 0;
    req.on('data', chunk => { bytes += chunk.length; if (bytes > 20_000_000) req.destroy(); else parts.push(chunk); });
    req.on('end', () => {
      try {
        const body = Buffer.concat(parts);
        const name = url.pathname === '/save-png' ? 'expression-overview.png' : 'render-report.json';
        if (name.endsWith('.png') && body.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a') throw Error('Invalid PNG');
        if (name.endsWith('.json')) {
          const report = JSON.parse(body);
          if (!report.allFinite || !report.allNonNeutralMoved || !report.blinkLeavesEyeballsStationary || report.resetMax !== 0) throw Error('Render verification failed');
        }
        if (hash(path.join(assets, 'head.glb')) !== binding.model_sha256) throw Error('Model changed during review');
        fs.writeFileSync(path.join(output, name), body, {flag: 'wx'});
        fs.appendFileSync(path.join(output, 'log.txt'), new Date().toISOString() + ' Saved ' + name + '\n');
        if (name.endsWith('.json')) {
          const files = ['expression-overview.png', 'render-report.json', 'input-binding.json', 'log.txt'].map(p => ({path: p, sha256: hash(path.join(output, p))}));
          fs.writeFileSync(path.join(output, 'manifest.json'), JSON.stringify({status: 'complete', files, credits_spent: 0}, null, 2));
          fs.writeFileSync(path.join(output, 'sha256.txt'), files.map(f => f.sha256 + '  ' + f.path).join('\n') + '\n');
        }
        res.writeHead(200).end('saved');
      } catch (error) { res.writeHead(400).end(error.message); }
    });
    return;
  }
  if (req.method !== 'GET') { res.writeHead(405).end(); return; }
  if (url.pathname === '/license') {
    res.writeHead(200, {'Content-Type': 'text/plain; charset=utf-8'}).end(fs.readFileSync(path.join(packageRoot, 'LICENSE'))); return;
  }
  if (url.pathname === '/source' || url.pathname.startsWith('/source/')) {
    try {
      const manifest = JSON.parse(fs.readFileSync(path.join(packageRoot, 'manifest.json')));
      const names = [...manifest.files.map(f => f.path), 'manifest.json', 'sha256.txt'];
      if (url.pathname === '/source') {
        const links = names.map(name => '<li><a href="/source/' + encodeURIComponent(name) + '">' + name.replaceAll('&', '&amp;').replaceAll('<', '&lt;') + '</a></li>').join('');
        res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8'}).end('<h1>Corresponding source</h1><p>Head Workflow — GPL-3.0-or-later. Source and build scripts for this running version.</p><ul>' + links + '</ul>');
        return;
      }
      const name = decodeURIComponent(url.pathname.slice(8));
      if (!names.includes(name)) { res.writeHead(404).end(); return; }
      res.writeHead(200, {'Content-Type': 'text/plain; charset=utf-8'}).end(fs.readFileSync(path.join(packageRoot, name))); return;
    } catch { res.writeHead(503).end('Source manifest unavailable'); return; }
  }
  if (url.pathname === '/viewer.json') { res.writeHead(200, {'Content-Type': 'application/json'}).end(JSON.stringify(viewer)); return; }
  if (url.pathname === '/input-binding.json') { res.writeHead(200, {'Content-Type': 'application/json'}).end(JSON.stringify(binding)); return; }
  let file;
  if (['/head.glb', '/control_manifest.json'].includes(url.pathname)) file = path.join(assets, url.pathname.slice(1));
  else if (['/expression-overview.png', '/render-report.json'].includes(url.pathname)) file = path.join(output, url.pathname.slice(1));
  else {
    let pathname;
    try { pathname = decodeURIComponent(url.pathname); } catch { res.writeHead(400).end(); return; }
    file = path.resolve(web, pathname === '/' ? 'index.html' : '.' + pathname);
    if (!file.startsWith(web + path.sep)) { res.writeHead(403).end(); return; }
  }
  fs.readFile(file, (error, data) => {
    if (error) { res.writeHead(404).end('Not found'); return; }
    res.writeHead(200, {'Content-Type': mime[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store'}).end(data);
  });
});
server.listen(port, '127.0.0.1', () => console.log('Open http://127.0.0.1:' + port + '/ — stop this process after review.'));
