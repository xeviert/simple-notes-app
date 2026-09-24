# Builds SimpleNotes.exe and installs it with Desktop and Start Menu shortcuts.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$installDir = "$env:LOCALAPPDATA\Programs\SimpleNotes"
$shortcuts = @(
    "$([Environment]::GetFolderPath('Desktop'))\Simple Notes.lnk",
    "$([Environment]::GetFolderPath('Programs'))\Simple Notes.lnk"
)

if (Get-Process SimpleNotes -ErrorAction SilentlyContinue) {
    throw "Simple Notes is running. Close it and run this script again."
}

if (-not (Test-Path .venv)) {
    python -m venv .venv
}
.\.venv\Scripts\python.exe -m pip install --quiet --upgrade pyinstaller pillow
.\.venv\Scripts\python.exe make_icon.py

.\.venv\Scripts\pyinstaller.exe notes.pyw `
    --name SimpleNotes --windowed --onedir --noconfirm --clean `
    --icon "$PSScriptRoot\icon.ico" --add-data "$PSScriptRoot\icon.ico;." `
    --distpath dist --workpath build --specpath build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

if (Test-Path $installDir) { Remove-Item $installDir -Recurse -Force }
Copy-Item dist\SimpleNotes $installDir -Recurse

$shell = New-Object -ComObject WScript.Shell
foreach ($path in $shortcuts) {
    $link = $shell.CreateShortcut($path)
    $link.TargetPath = "$installDir\SimpleNotes.exe"
    $link.WorkingDirectory = $installDir
    $link.IconLocation = "$installDir\SimpleNotes.exe,0"
    $link.Description = "Simple Notes"
    $link.Save()
}

Write-Host "Installed to $installDir"
Write-Host "Shortcuts: $($shortcuts -join ', ')"
