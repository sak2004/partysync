<#
.SYNOPSIS
  Build PartySync.exe with PyInstaller.
  Run on Windows with PyAudio drivers installed.
  The resulting exe has NOT been run on real hardware — see docs/NOTES.md.
#>
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot | Split-Path -Parent

# Create isolated venv
python -m venv "$Root\build_venv"
& "$Root\build_venv\Scripts\pip" install --quiet -r "$Root\requirements.txt"
& "$Root\build_venv\Scripts\pip" install --quiet pyinstaller

& "$Root\build_venv\Scripts\pyinstaller" `
    --noconsole `
    --onefile `
    --name PartySync `
    --collect-all pyaudiowpatch `
    --hidden-import partysync.gui `
    --hidden-import partysync.backends.wasapi `
    --hidden-import partysync.backends.fake `
    --add-data "src;src" `
    "$Root\app_flask.py"

Write-Host "Built: $Root\dist\PartySync.exe"
