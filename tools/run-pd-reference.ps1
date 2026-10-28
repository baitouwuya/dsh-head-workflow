# SPDX-License-Identifier: GPL-3.0-or-later
param(
  [string]$AddonDirectory = 'D:\Staging\PD\parametric_deformation-0.1.0',
  [string]$F00Directory = 'D:\Staging\PD\vroid',
  [string]$M00Directory = 'D:\Staging\PD\vroid_m00',
  [Parameter(Mandatory)][string]$OutputDirectory,
  [switch]$VerifyFit
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$source = @{}
foreach ($name in @('geometry','pd_adapter','fit')) {
  $source[$name] = [IO.File]::ReadAllText((Join-Path $repo "head_workflow/reference/$name.py"))
}
$payload = @{
  sources = $source
  runner = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'pd_reference_host.py'))
  addon = $AddonDirectory
  packs = @{F00=$F00Directory; M00=$M00Directory}
  verify = [bool]$VerifyFit
} | ConvertTo-Json -Depth 10 -Compress
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($payload))
$code = @"
import base64, json, sys, types
payload=json.loads(base64.b64decode('$encoded'))
prefix='_dsh_pd_reference_task'
pkg=types.ModuleType(prefix);pkg.__path__=[];sys.modules[prefix]=pkg
for name in ['geometry','pd_adapter','fit']:
    module=types.ModuleType(prefix+'.'+name);module.__package__=prefix
    sys.modules[module.__name__]=module
    exec(compile(payload['sources'][name],'<pd-reference/'+name+'>','exec'),module.__dict__)
runner={}
exec(compile(payload['runner'],'<pd-reference/runner>','exec'),runner)
result=runner['run'](payload['addon'],payload['packs'],payload['verify'])
print('PD_REFERENCE_JSON:'+json.dumps(result,allow_nan=False))
"@
$scratch = Join-Path $repo '.reference-work'
New-Item -ItemType Directory -Force $scratch | Out-Null
$script = Join-Path $scratch ('host-' + [guid]::NewGuid().ToString('N') + '.py')
[IO.File]::WriteAllText($script,$code,(New-Object Text.UTF8Encoding($false)))
$reply = & 'C:\ProgramData\dsh\hostcap\blender-call.ps1' -File $script -TimeoutMs 180000 | ConvertFrom-Json
if (-not $reply.ok -or -not $reply.body.ok -or $reply.body.result.isError) {
  throw ('Host extraction failed: ' + ($reply | ConvertTo-Json -Depth 20))
}
$message = $reply.body.result.content.text -join "`n"
if (-not $message.Contains('PD_REFERENCE_JSON:')) { throw $message }
$result = ($message -split 'PD_REFERENCE_JSON:',2)[1] | ConvertFrom-Json
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$utf8 = New-Object Text.UTF8Encoding($false)
foreach ($label in @('F00','M00')) {
  [IO.File]::WriteAllText((Join-Path $OutputDirectory "$label.json"),
    ($result.profiles.$label | ConvertTo-Json -Depth 100),$utf8)
  [IO.File]::WriteAllText((Join-Path $OutputDirectory "$label-fit.json"),
    ($result.fits.$label | ConvertTo-Json -Depth 100),$utf8)
}
[IO.File]::WriteAllText((Join-Path $OutputDirectory 'host-verification.json'),
  ($result.verification | ConvertTo-Json -Depth 100),$utf8)
$result.verification | ConvertTo-Json -Depth 20
if (-not $result.verification.scene_state_unchanged) { throw 'Blender state changed during extraction' }
if ($VerifyFit -and (-not $result.verification.pd_parameter_recovery.F00.passed -or -not $result.verification.pd_parameter_recovery.M00.passed)) {
  throw 'PD parameter recovery did not meet tolerance'
}
