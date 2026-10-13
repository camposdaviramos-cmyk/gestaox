$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$skyxPython = 'C:\Users\Administrador\AppData\Local\Programs\Python\Python314\python.exe'
if (-not (Test-Path -LiteralPath $skyxPython)) { $skyxPython = 'python' }
& $skyxPython server.py
