$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = "C:\Users\adolf\AppData\Local\Programs\Python\Python313\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

& $Python -m PyInstaller `
    --onefile `
    --name autoresearch `
    --console `
    --distpath dist-exe `
    --workpath build `
    --specpath . `
    scripts\autoresearch_entry.py

Write-Output "Built: $Root\dist-exe\autoresearch.exe"
