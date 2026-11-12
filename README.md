# Negi 🌱 · Descargador de videos

Descarga videos de YouTube, TikTok, Facebook, X, Instagram y muchas páginas más, en la máxima
calidad, en MP4 compatible o solo el audio en MP3. Todo pasa en tu computadora: sin páginas web
raras, sin anuncios y sin cuentas.

## Descargar

👉 **[Descargar la última versión](../../releases/latest)**

- **Windows 10/11:** baja `Negi-Setup.exe` y ábrelo.
- **Android:** baja el archivo `.apk` (cuando esté disponible) y ábrelo en el celular.

Negi se actualiza sola: cuando haya una versión nueva te mostrará **"Actualizar"**.

### Si Windows dice "Windows protegió su PC"

Es normal: la app no tiene firma digital de pago. Pulsa **Más información → Ejecutar de todas formas**.
Solo pasa la primera vez.

## Qué puede hacer

- Cola de descargas: agrega varios videos y se bajan uno tras otro.
- Elegir calidad de video (Máxima, 4K, 1440p, 1080p, 720p, 480p) o de audio MP3 (Máxima, 320, 192, 128 kbps).
- Avisa antes de descargar si no hay espacio suficiente.
- Historial de lo descargado, con Reproducir y Abrir carpeta.
- Aviso cuando termina, aunque la ventana esté minimizada.

Descarga solo contenido que tengas derecho a guardar.

## Créditos y licencias

- El nombre "Negi" (ネギ) es el cebollín que siempre lleva Hatsune Miku.
- Ícono basado en la ilustración oficial de **Hatsune Miku, © Crypton Future Media, Inc. 2007**,
  con licencia [CC BY-NC 3.0](https://creativecommons.org/licenses/by-nc/3.0/): Negi es gratuita y
  **no se puede vender**.
- Incluye sin modificar [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense),
  [ffmpeg](https://ffmpeg.org) (GPL, compilación de [gyan.dev](https://www.gyan.dev/ffmpeg/builds/);
  código fuente en ffmpeg.org) y [deno](https://deno.com) (MIT).
- La versión de Android usa [youtubedl-android](https://github.com/yausername/youtubedl-android) (GPL-3.0):
  su código fuente completo va en cada versión como `codigo-fuente.zip`.

## Para desarrolladores

Windows + Python 3.13. `powershell -ExecutionPolicy Bypass -File compilar.ps1` genera
`salida/Negi-Setup.exe` (descarga y verifica las herramientas oficiales, corre las pruebas,
PyInstaller e Inno Setup).
