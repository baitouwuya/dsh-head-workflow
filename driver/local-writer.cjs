// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

// Guest-local, loopback-only artifact sink. No credentials, arbitrary paths, deletion, or execution API.
const http=require('http'),fs=require('fs'),path=require('path'),crypto=require('crypto');
const configPath=process.argv[2];
if(!configPath)throw Error('Usage: node local-writer.cjs <writer-config.json>');
const config=JSON.parse(fs.readFileSync(configPath,'utf8').replace(/^\uFEFF/,''));
if(!path.isAbsolute(config.root)||!fs.statSync(config.root).isDirectory()||!/^[a-p]{32}$/.test(config.extensionId))throw Error('Invalid writer root or Chrome extension ID');
const root=path.resolve(config.root),extension='chrome-extension://'+config.extensionId;
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const {allowsName,allowsArtifactName}=require('./writer-contract.js');
const server=http.createServer((req,res)=>{
  // Only the installed extension is allowed CORS access. No site-to-loopback writes.
  if(req.headers.origin&&req.headers.origin!==extension){res.writeHead(403);res.end();return;}
  if(req.headers['x-dsh-writer']!=='v020'){res.writeHead(403);res.end();return;}
  res.setHeader('Access-Control-Allow-Origin',extension);
  if(req.method==='OPTIONS'){res.setHeader('Access-Control-Allow-Headers','content-type,x-dsh-writer');res.setHeader('Access-Control-Allow-Methods','POST,GET');res.end();return;}
  if(req.method==='GET'&&req.url==='/health'){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({ok:true,version:'0.2.59',capabilities:['model-chunks','artifact-chunks'],root,extensionId:config.extensionId}));return;}
  if(req.method!=='POST'||req.url!=='/write'){res.writeHead(404);res.end();return;}
  let chunks=[],size=0;
  req.on('data',b=>{size+=b.length;if(size>6*1024*1024){req.destroy();return;}chunks.push(b);});
  req.on('end',()=>{try{
    const v=JSON.parse(Buffer.concat(chunks));let target,bytes;
    if(v.area==='runs'){
      if(!/^p3-(?:run|recording|dry)-[0-9]{13}$/.test(v.run)||!allowsName(v.name)||typeof v.text!=='string'||v.text.length>4*1024*1024)throw Error('Invalid evidence envelope');
      target=path.resolve(root,'runs',v.run,v.name);bytes=Buffer.from(v.text);
      if(/Bearer\s+[A-Za-z0-9._-]{12,}|eyJ[A-Za-z0-9_-]{12,}\./.test(v.text))throw Error('Secret-like content refused');
      fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target+'.tmp',bytes);fs.renameSync(target+'.tmp',target);
    }else if(v.area==='out'){
      if(!/^dsh-run-[0-9]{13}-[-a-z0-9]{1,48}\.(?:glb|fbx)$/.test(v.name)||typeof v.base64!=='string'||!Number.isInteger(v.offset)||v.offset<0||v.offset>100*1024*1024)throw Error('Invalid model chunk');
      target=path.resolve(root,'out',v.name);bytes=Buffer.from(v.base64,'base64');if(bytes.length>1024*1024)throw Error('Chunk exceeds bound');
      fs.mkdirSync(path.dirname(target),{recursive:true});const staging=target+'.part';
      if(v.offset===0){if(fs.existsSync(target)||fs.existsSync(staging))throw Error('Output exists; refusing overwrite');fs.writeFileSync(staging,bytes,{flag:'wx'});}
      else{if(fs.statSync(staging).size!==v.offset)throw Error('Chunk offset mismatch');fs.appendFileSync(staging,bytes);}
      if(!v.final){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({ok:true,nextOffset:v.offset+bytes.length}));return;}
      const full=fs.readFileSync(staging);const validContainer=v.name.endsWith('.glb')?full.length>=12&&full.readUInt32LE(0)===0x46546c67&&full.readUInt32LE(8)===full.length:full.length>=27&&full.subarray(0,23).equals(Buffer.from('Kaydara FBX Binary  \0\x1a\0'))&&[7400,7500].includes(full.readUInt32LE(23));if(hash(full)!==v.sha256||!validContainer)throw Error('Model hash/container verification failed');fs.renameSync(staging,target);bytes=full;
    }else if(v.area==='artifacts'){
      if(!allowsArtifactName(v.name)||typeof v.base64!=='string'||!Number.isInteger(v.offset)||v.offset<0||v.offset>512*1024*1024||!/^[a-f0-9]{64}$/.test(v.sha256))throw Error('Invalid artifact chunk');
      bytes=Buffer.from(v.base64,'base64');if(!bytes.length||bytes.length>1024*1024||v.offset+bytes.length>512*1024*1024)throw Error('Artifact chunk exceeds bound');
      target=path.resolve(root,'out',v.name);const staging=target+'.part';fs.mkdirSync(path.dirname(target),{recursive:true});
      if(v.offset===0){if(fs.existsSync(target)||fs.existsSync(staging))throw Error('Output exists; refusing overwrite');fs.writeFileSync(staging,bytes,{flag:'wx'});}
      else{if(fs.statSync(staging).size!==v.offset)throw Error('Chunk offset mismatch');fs.appendFileSync(staging,bytes);}
      if(!v.final){res.setHeader('Content-Type','application/json');res.end(JSON.stringify({ok:true,nextOffset:v.offset+bytes.length}));return;}
      const full=fs.readFileSync(staging);if(hash(full)!==v.sha256)throw Error('Artifact hash verification failed');
      if(v.name.endsWith('.glb')&&(full.length<20||full.readUInt32LE(0)!==0x46546c67||full.readUInt32LE(4)!==2||full.readUInt32LE(8)!==full.length))throw Error('Invalid GLB artifact');
      fs.renameSync(staging,target);bytes=full;
    }else throw Error('Area refused');
    res.setHeader('Content-Type','application/json');res.end(JSON.stringify({ok:true,path:path.relative(root,target).replaceAll('\\','/'),bytes:bytes.length,sha256:hash(bytes)}));
  }catch(e){res.writeHead(400,{'Content-Type':'application/json'});res.end(JSON.stringify({ok:false,error:e.message}));}});
});
server.listen(43127,'127.0.0.1',()=>console.log('DSH writer listening on loopback 43127; bounded runs/out only'));








