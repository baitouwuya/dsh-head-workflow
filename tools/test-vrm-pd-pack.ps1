# SPDX-License-Identifier: GPL-3.0-or-later
param(
  [Parameter(Mandatory)][string]$VrmPath,
  [Parameter(Mandatory)][string]$PrivatePackDirectory,
  [Parameter(Mandatory)][string]$ReportPath
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$sources = @{}
foreach ($name in @('gltf','convert','runtime','driver')) {
  $sources[$name] = [IO.File]::ReadAllText((Join-Path $repo "head_workflow/pd_pack/$name.py"))
}
$payload = @{sources=$sources; runner=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'pd_pack_host_check.py')); source=$VrmPath; output=$PrivatePackDirectory} | ConvertTo-Json -Depth 10 -Compress
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($payload))
$code = @"
import base64,json,sys,types
payload=json.loads(base64.b64decode('$encoded'))
prefix='_pdpack_check';package=types.ModuleType(prefix);package.__path__=[];sys.modules[prefix]=package
for name in ['gltf','convert','runtime']:
    module=types.ModuleType(prefix+'.'+name);module.__package__=prefix;sys.modules[module.__name__]=module
    exec(compile(payload['sources'][name],'<pd-pack/'+name+'>','exec'),module.__dict__)
runner={};exec(compile(payload['runner'],'<pd-pack/host-check>','exec'),runner)
result=runner['run'](payload['source'],payload['output'],payload['sources'])
print('PD_PACK_PROOF_JSON:'+json.dumps(result,allow_nan=False))
"@
$scratch=Join-Path $repo '.reference-work'
New-Item -ItemType Directory -Force $scratch | Out-Null
$script=Join-Path $scratch ('pack-proof-'+[guid]::NewGuid().ToString('N')+'.py')
[IO.File]::WriteAllText($script,$code,(New-Object Text.UTF8Encoding($false)))
$reply=& 'C:\ProgramData\dsh\hostcap\blender-call.ps1' -File $script -TimeoutMs 180000 | ConvertFrom-Json
if (-not $reply.ok -or -not $reply.body.ok -or $reply.body.result.isError) { throw ($reply | ConvertTo-Json -Depth 20) }
$message=$reply.body.result.content.text -join "`n"
if (-not $message.Contains('PD_PACK_PROOF_JSON:')) { throw $message }
$proof=($message -split 'PD_PACK_PROOF_JSON:',2)[1] | ConvertFrom-Json
$parent=Split-Path $ReportPath -Parent
if ($parent) { New-Item -ItemType Directory -Force $parent | Out-Null }
[IO.File]::WriteAllText($ReportPath,($proof | ConvertTo-Json -Depth 100),(New-Object Text.UTF8Encoding($false)))
$proof | ConvertTo-Json -Depth 20
