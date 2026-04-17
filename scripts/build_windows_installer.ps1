param(
    [string]$PythonExe = "python",
    [string]$IsccPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = "Stop"

Write-Host "[1/3] Installing build dependencies..."
& $PythonExe -m pip install --upgrade pip pyinstaller

Write-Host "[2/3] Building executable with PyInstaller..."
& $PythonExe -m PyInstaller --noconfirm --onefile --windowed --name QuickBooksProject quickbooks_project/app.py

Write-Host "[3/3] Building installer with Inno Setup..."
& $IsccPath installer/QuickBooksProject.iss

Write-Host "Done. Installer output should be in dist/installer"
