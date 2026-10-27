# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Head Workflow contributors

param([string]$Source=$PSScriptRoot,[string]$Destination='<EXT_DIR>')
$ErrorActionPreference='Stop'
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$files=@('manifest.json','sanitize.js','observer.js','shortcut-core.js','native-contracts.js', 'storage-sign.js', 'input.png','flow.js','durable-state.js','auto-layout.js','canvas-assets.js','artifact-download.js','lab-operations.js','ui-actions.js','ui-hot-runtime.js','review-bridge.js','driver.js','lifecycle.js','writer-contract.js','writer-bridge.js','writer-worker.js','popup.html','popup.css','popup.js')
foreach($name in $files){Copy-Item -LiteralPath (Join-Path $Source $name) -Destination (Join-Path $Destination $name) -Force}
Write-Output 'Synced v0.2.59. Reload the extension and its Studio tab to load the new content scripts and writer bridge. Update the owned local writer runtime too.'
