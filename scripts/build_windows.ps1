$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location "$Root\frontend"
npm ci
npm run build
Set-Location $Root
python scripts/copy_frontend.py
python -m pip install -e "backend[dev]" pyinstaller
pyinstaller --noconfirm --clean --name iracing-analyst --collect-all iracing_analyst --add-data "backend/iracing_analyst/static;iracing_analyst/static" backend/iracing_analyst/__main__.py
Copy-Item README.md,THIRD_PARTY_NOTICES.md -Destination dist/iracing-analyst
Compress-Archive -Path dist/iracing-analyst/* -DestinationPath dist/iracing-analyst-windows-x64.zip -Force

