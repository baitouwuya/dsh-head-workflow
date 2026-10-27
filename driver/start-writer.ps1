# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors

param([string]$Root=(Split-Path $PSScriptRoot -Parent),[Parameter(Mandatory=$true)][ValidatePattern('^[a-p]{32}$')][string]$ExtensionId,[string]$NodePath,[string]$WriterDirectory=(Join-Path $env:LOCALAPPDATA 'DSH\tripo-writer'))
$ErrorActionPreference = 'Stop'
$Root=(Resolve-Path -LiteralPath $Root).Path
try {
  $writerHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:43127/health' -Headers @{'X-DSH-Writer'='v020'} -TimeoutSec 2
  if ($writerHealth.ok -and $writerHealth.version -eq '0.2.59' -and $writerHealth.root -eq $Root -and $writerHealth.extensionId -eq $ExtensionId) {
    Write-Output 'DSH local writer is already running.'
    return
  }
} catch { }
if($writerHealth){throw 'Port 43127 has another writer configuration. Stop only your recorded writer PID, then rerun.'}
$writerNode=$NodePath
if(-not $writerNode){$found=Get-Command node -ErrorAction SilentlyContinue;if($found){$writerNode=$found.Source}}
if(-not $writerNode){$writerNode = Get-ChildItem -Path "$env:LOCALAPPDATA\OpenAI\Codex\runtimes\cua_node\*\bin\node.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName}
if (-not $writerNode) { throw 'Node.js 20+ is required. Pass -NodePath with an absolute path to node.exe.' }
New-Item -ItemType Directory -Force -Path $writerDirectory | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'local-writer.cjs') -Destination (Join-Path $writerDirectory 'local-writer.cjs') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'writer-contract.js') -Destination (Join-Path $writerDirectory 'writer-contract.js') -Force
$configPath=Join-Path $writerDirectory 'writer-config.json'
@{root=$Root;extensionId=$ExtensionId}|ConvertTo-Json|Set-Content -LiteralPath $configPath -Encoding UTF8
$scriptPath=Join-Path $writerDirectory 'local-writer.cjs'
$writerProcess = Start-Process -FilePath $writerNode -ArgumentList @('"'+$scriptPath+'"','"'+$configPath+'"') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $writerDirectory 'stdout.log') -RedirectStandardError (Join-Path $writerDirectory 'stderr.log') -PassThru
$writerProcess.Id | Set-Content -LiteralPath (Join-Path $writerDirectory 'pid.txt')
Start-Sleep -Milliseconds 400
$writerHealth = Invoke-RestMethod -Uri 'http://127.0.0.1:43127/health' -Headers @{'X-DSH-Writer'='v020'} -TimeoutSec 2
if (-not $writerHealth.ok -or $writerHealth.root -ne $Root -or $writerHealth.extensionId -ne $ExtensionId) { throw 'Writer health/config check failed' }
Write-Output 'DSH writer ready on loopback 43127; writes bounded task evidence, models and verified artifact downloads.'








