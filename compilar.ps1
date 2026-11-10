# Genera salida\Negi-Setup.exe
#   1) herramientas oficiales verificadas  2) ícono  3) pruebas  4) PyInstaller  5) Inno Setup
# Uso:  powershell -ExecutionPolicy Bypass -File compilar.ps1
$ErrorActionPreference = 'Stop'
$raiz = $PSScriptRoot
$build = Join-Path $env:LOCALAPPDATA 'DescargadorDeVideos-build'   # fuera de OneDrive
$salida = Join-Path $raiz 'salida'
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw 'Falta Inno Setup 6:  winget install JRSoftware.InnoSetup --version 6.7.3' }

function Paso($t) { Write-Host "`n==> $t" -ForegroundColor Cyan }

Paso 'Herramientas (yt-dlp, ffmpeg, deno)'
$h = Join-Path $build 'herramientas'
if (-not (Test-Path "$h\yt-dlp.exe") -or -not (Test-Path "$h\ffmpeg.exe") -or -not (Test-Path "$h\deno.exe")) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $raiz 'empaquetado\binarios.ps1')
    if ($LASTEXITCODE) { throw 'Falló la descarga de herramientas' }
} else { Write-Host '  Ya están descargadas y verificadas.' }

Paso 'Ícono'
python (Join-Path $raiz 'empaquetado\icono.py'); if ($LASTEXITCODE) { throw 'Falló el ícono' }

Paso 'Pruebas'
python -m pytest (Join-Path $raiz 'tests') -q -m 'not red' -p no:cacheprovider
if ($LASTEXITCODE) { throw 'Las pruebas fallaron: no se compila.' }

Paso 'PyInstaller'
python -m PyInstaller (Join-Path $raiz 'empaquetado\app.spec') --noconfirm --clean `
    --distpath (Join-Path $build 'dist') --workpath (Join-Path $build 'work')
if ($LASTEXITCODE) { throw 'Falló PyInstaller' }

Paso 'Instalador (Inno Setup)'
New-Item -ItemType Directory -Force $salida | Out-Null
Push-Location (Join-Path $raiz 'empaquetado')
try {
    & $iscc /Q "/DBuild=$build" "/DSalida=$salida" 'instalador.iss'
    if ($LASTEXITCODE) { throw 'Falló Inno Setup' }
} finally { Pop-Location }

$setup = Get-Item (Join-Path $salida 'Negi-Setup.exe')
# Huella para que la app verifique la actualización antes de instalarla.
$hash = (Get-FileHash $setup.FullName -Algorithm SHA256).Hash.ToLower()
[IO.File]::WriteAllText("$($setup.FullName).sha256", "$hash  Negi-Setup.exe`n")
Write-Host ("`nListo: {0}  ({1:N1} MB)" -f $setup.FullName, ($setup.Length / 1MB)) -ForegroundColor Green
