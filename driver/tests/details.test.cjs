// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

'use strict';
const assert=require('node:assert/strict'),S=require('../sanitize.js');
const secret='DO_NOT_STORE_TOKEN_123',id='00000000-0000-4000-8000-000000000001';
const data=S.details({projectId:id,prompt:secret,sessionId:secret,token:secret,authorization:secret,status:'completed',wallet:{total_credit:10},projects:[{projectId:id,name:'dsh-test',updateTime:'2026-10-21T18:00:00Z',coverImageUrl:'https://example.tripo3d.ai/image.webp?signature='+secret}],total:1});
assert(!JSON.stringify(data).includes(secret));assert.equal(data.projectInventory.projects[0].id,id);assert.equal(data.projectInventory.projects[0].thumbnail,'https://example.tripo3d.ai/image.webp');
assert.equal(S.operation('canvas.Run'),'canvas.Run');assert.equal(S.operation('Bearer '+secret),'<unknown-or-redacted>');
assert.equal(S.operation('eyJlongvalue.eyJsecondpart.signature'),'<unknown-or-redacted>');
assert.deepEqual(S.details('x'.repeat(70000)),{});
console.log(JSON.stringify({suite:'allowlisted observation details',passed:7,networkRequests:0},null,2));
