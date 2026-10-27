// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Head Workflow contributors

'use strict';
// Offline dry-run of the exact inverse logic used by the driver's one-command rollback.
// Live authenticated rollback is the extension command, never a shell-held credential.
const fs=require('node:fs'),B=require('./section-batch-core');
if(process.argv.length!==5||process.argv[2]!=='--dry-run'){console.error('Usage: node rollback-sections.cjs --dry-run checkpoint.json current-canvas.json');process.exit(2);}
const job=JSON.parse(fs.readFileSync(process.argv[3],'utf8')),current=JSON.parse(fs.readFileSync(process.argv[4],'utf8'));
console.log(JSON.stringify({mode:'dry-run',networkRequests:0,restores:B.rollbackPlan(job,current)},null,2));

