# SPDX-License-Identifier: GPL-3.0-or-later
param(
  [Parameter(Mandatory)][string]$VrmPath,
  [Parameter(Mandatory)][string]$OutputDirectory,
  [string]$AddonDirectory = '',
  [string]$PackDirectory = 'D:\Staging\PD\vroid'
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$source = @{}
foreach ($name in @('geometry','pd_adapter','fit','vrm','quality')) {
  $source[$name] = [IO.File]::ReadAllText((Join-Path $repo "head_workflow/reference/$name.py"))
}
$source['gltf'] = [IO.File]::ReadAllText((Join-Path $repo 'head_workflow/pd_pack/gltf.py'))
$payload = @{
  sources = $source
  runner = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'vrm_reference_host.py'))
  addon = $AddonDirectory
  pack = $PackDirectory
  vrm = $VrmPath
} | ConvertTo-Json -Depth 10 -Compress
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($payload))
$code = @"
import base64, json, sys, types
payload=json.loads(base64.b64decode('$encoded'))
prefix='_dsh_pd_reference_task'
pkg=types.ModuleType(prefix);pkg.__path__=[];sys.modules[prefix]=pkg
for child in ['reference','pd_pack']:
    package=types.ModuleType(prefix+'.'+child);package.__path__=[];sys.modules[package.__name__]=package
module=types.ModuleType(prefix+'.pd_pack.gltf');module.__package__=prefix+'.pd_pack';sys.modules[module.__name__]=module
exec(compile(payload['sources']['gltf'],'<reference/gltf>','exec'),module.__dict__)
for name in ['geometry','pd_adapter','fit','vrm','quality']:
    module=types.ModuleType(prefix+'.reference.'+name);module.__package__=prefix+'.reference'
    sys.modules[module.__name__]=module
    sys.modules[prefix+'.'+name]=module
    exec(compile(payload['sources'][name],'<reference/'+name+'>','exec'),module.__dict__)
runner={}
exec(compile(payload['runner'],'<reference/vrm-runner>','exec'),runner)
result=runner['run'](payload['vrm'],payload['addon'],payload['pack'])
print('VRM_REFERENCE_JSON:'+json.dumps(result,allow_nan=False))
"@
$scratch = Join-Path $repo '.reference-work'
New-Item -ItemType Directory -Force $scratch | Out-Null
$script = Join-Path $scratch ('vrm-host-' + [guid]::NewGuid().ToString('N') + '.py')
[IO.File]::WriteAllText($script,$code,(New-Object Text.UTF8Encoding($false)))
$reply = & 'C:\ProgramData\dsh\hostcap\blender-call.ps1' -File $script -TimeoutMs 180000 | ConvertFrom-Json
if (-not $reply.ok -or -not $reply.body.ok -or $reply.body.result.isError) {
  throw ('Host test failed: ' + ($reply | ConvertTo-Json -Depth 20))
}
$message = $reply.body.result.content.text -join "`n"
if (-not $message.Contains('VRM_REFERENCE_JSON:')) { throw $message }
$result = ($message -split 'VRM_REFERENCE_JSON:',2)[1] | ConvertFrom-Json
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$utf8 = New-Object Text.UTF8Encoding($false)
foreach ($entry in @(@('profile','base-vrm.json'),@('fit','base-vrm-fit.json'),@('verification','base-vrm-verification.json'))) {
  [IO.File]::WriteAllText((Join-Path $OutputDirectory $entry[1]),
    ($result.($entry[0]) | ConvertTo-Json -Depth 100),$utf8)
}
$result.verification.live_experiment | ConvertTo-Json -Depth 20
