# Descarga yt-dlp, ffmpeg y deno de sus releases OFICIALES y verifica su SHA-256 publicado.
# Resultado: %LOCALAPPDATA%\DescargadorDeVideos-build\herramientas  (+ licencias)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$DenoVersion = '2.9.8'
$base = Join-Path $env:LOCALAPPDATA 'DescargadorDeVideos-build'
$descargas = Join-Path $base 'descargas'
$herramientas = Join-Path $base 'herramientas'
$licencias = Join-Path $base 'licencias'
foreach ($d in $descargas, $herramientas, $licencias) { New-Item -ItemType Directory -Force $d | Out-Null }

function Bajar([string]$url, [string]$destino) {
    Write-Host "  Descargando $url"
    Invoke-WebRequest -Uri $url -OutFile $destino -UseBasicParsing -UserAgent 'DescargadorDeVideos-build'
}

function Verificar([string]$archivo, [string]$esperado) {
    $esperado = $esperado.Trim().ToLower()
    $real = (Get-FileHash $archivo -Algorithm SHA256).Hash.ToLower()
    if ($real -ne $esperado) {
        Remove-Item $archivo -Force
        throw "La huella SHA-256 de $(Split-Path $archivo -Leaf) NO coincide. Archivo borrado. (esperado $esperado, real $real)"
    }
    Write-Host "  OK  $(Split-Path $archivo -Leaf)  sha256 verificado"
}

# Extrae el hash de 64 caracteres hexadecimales, sea cual sea el formato del archivo de sumas.
function PrimerToken([string]$texto) {
    $m = [regex]::Match($texto, '\b[0-9a-fA-F]{64}\b')
    if (-not $m.Success) { throw "No se encontró un hash SHA-256 en: $texto" }
    $m.Value
}

function YaVerificado([string]$archivo, [string]$esperado) {
    (Test-Path $archivo) -and ((Get-FileHash $archivo -Algorithm SHA256).Hash -eq $esperado.ToUpper())
}

# --- yt-dlp -------------------------------------------------------------
Write-Host 'yt-dlp'
$ytdlp = Join-Path $descargas 'yt-dlp.exe'
$sumas = Join-Path $descargas 'SHA2-256SUMS'
Bajar 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe' $ytdlp
Bajar 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/SHA2-256SUMS' $sumas
$linea = Get-Content $sumas | Where-Object { $_ -match '\syt-dlp\.exe$' } | Select-Object -First 1
if (-not $linea) { throw 'No se encontró yt-dlp.exe en SHA2-256SUMS' }
Verificar $ytdlp (PrimerToken $linea)
Copy-Item $ytdlp $herramientas -Force
Bajar 'https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/LICENSE' (Join-Path $licencias 'yt-dlp-LICENSE.txt')

# --- ffmpeg (gyan.dev essentials) ----------------------------------------
Write-Host 'ffmpeg'
$zipF = Join-Path $descargas 'ffmpeg-release-essentials.zip'
$hashF = (Invoke-WebRequest 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256' -UseBasicParsing).Content
if ($hashF -is [byte[]]) { $hashF = [Text.Encoding]::ASCII.GetString($hashF) }
$hashF = PrimerToken $hashF
if (-not (YaVerificado $zipF $hashF)) { Bajar 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' $zipF }
Verificar $zipF $hashF
$extF = Join-Path $descargas 'ffmpeg'
if (Test-Path $extF) { Remove-Item $extF -Recurse -Force }
Expand-Archive $zipF $extF
$binF = Get-ChildItem $extF -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1
Copy-Item (Join-Path $binF.DirectoryName 'ffmpeg.exe'), (Join-Path $binF.DirectoryName 'ffprobe.exe') $herramientas -Force
$licF = Get-ChildItem $extF -Recurse -Filter 'LICENSE*' | Select-Object -First 1
Copy-Item $licF.FullName (Join-Path $licencias 'ffmpeg-LICENSE.txt') -Force

# --- deno ----------------------------------------------------------------
Write-Host 'deno'
$zipD = Join-Path $descargas 'deno.zip'
$urlD = "https://github.com/denoland/deno/releases/download/v$DenoVersion/deno-x86_64-pc-windows-msvc.zip"
Bajar $urlD $zipD
$sumD = Join-Path $descargas 'deno.sha256sum'
Bajar "$urlD.sha256sum" $sumD
Verificar $zipD (PrimerToken (Get-Content $sumD -Raw))
Expand-Archive $zipD $herramientas -Force
Bajar 'https://raw.githubusercontent.com/denoland/deno/main/LICENSE.md' (Join-Path $licencias 'deno-LICENSE.txt')

Write-Host "`nListo. Herramientas en $herramientas"
Get-ChildItem $herramientas | ForEach-Object { '{0,-14} {1,8:N1} MB' -f $_.Name, ($_.Length / 1MB) }
