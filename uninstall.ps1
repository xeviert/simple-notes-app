# Removes the app and its shortcuts. Notes in %APPDATA%\SimpleNotes are kept.
$ErrorActionPreference = "Stop"

if (Get-Process SimpleNotes -ErrorAction SilentlyContinue) {
    throw "Simple Notes is running. Close it and run this script again."
}

Remove-Item "$env:LOCALAPPDATA\Programs\SimpleNotes" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$([Environment]::GetFolderPath('Desktop'))\Simple Notes.lnk" -ErrorAction SilentlyContinue
Remove-Item "$([Environment]::GetFolderPath('Programs'))\Simple Notes.lnk" -ErrorAction SilentlyContinue

Write-Host "Uninstalled. Notes kept in $env:APPDATA\SimpleNotes"
