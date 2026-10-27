// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const {root}=JSON.parse(fs.readFileSync(process.argv[2]||path.join(__dirname,'review-companion.json')));
const old='<SHARE_ROOT>/runs/avatar-pipeline-1792781538496',original='<SHARE_ROOT>/runs/original-head-rework-1792814733380';
const files={'/controls/':root+'/review/controls/index.html','/morphs/':root+'/review/morphs/index.html'};
for(const name of ['sanitize.js','shortcut-core.js','ui-actions.js','review-bridge.js'])files['/runtime/'+name]='<SHARE_ROOT>/ext/'+name;
for(const relative of ['three.module.js','three.core.js','loaders/GLTFLoader.js','utils/BufferGeometryUtils.js'])for(const name of ['controls','morphs'])files['/'+name+'/vendor/'+relative]=original+'/browser-check/vendor/'+relative;
for(const [url,p]of Object.entries({'bodyRig.glb':old+'/bodyRig.glb','expressive-face.glb':old+'/face-kit/expressive-face.glb','face-controller.mjs':old+'/face-kit/face-controller.mjs','face-attachment.mjs':old+'/browser-check/face-attachment.mjs','final-avatar.glb':old+'/final-avatar.glb','final-controller.js':old+'/final-kit/avatar-kit/FaceController.js'}))files['/controls/'+url]=p;
for(const n of ['head-body.glb','expressions.glb','final-avatar.glb'])files['/morphs/'+n]=original+'/'+n;
const server=http.createServer((req,res)=>{const file=files[new URL(req.url,'http://127.0.0.1').pathname];if(req.method!=='GET'||!file||!fs.existsSync(file)){res.writeHead(404);res.end('Not found');return;}res.writeHead(200,{'Content-Type':/\.m?js$/.test(file)?'text/javascript':file.endsWith('.html')?'text/html':'model/gltf-binary','Cache-Control':'no-store'});fs.createReadStream(file).on('error',()=>res.destroy()).pipe(res);});
server.listen(0,'127.0.0.1',()=>{const info={url:'http://127.0.0.1:'+server.address().port+'/',pid:process.pid,root,startedAt:new Date().toISOString()};fs.writeFileSync(root+'/review-server.json',JSON.stringify(info,null,2));console.log(info.url);});
