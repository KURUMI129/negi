"""Dónde vive cada cosa, tanto instalada como en desarrollo."""

from __future__ import annotations

import os
import shutil
import sys
import threading
from pathlib import Path

CARPETA_DATOS = "DescargadorDeVideos"
CARPETA_BUILD = "DescargadorDeVideos-build"


def _localappdata() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")


def es_instalada() -> bool:
    return bool(getattr(sys, "frozen", False))


def dir_herramientas() -> Path:
    """ffmpeg, ffprobe, deno y la copia inicial de yt-dlp."""
    if es_instalada():
        return Path(sys.executable).parent / "herramientas"
    return _localappdata() / CARPETA_BUILD / "herramientas"


def dir_ui() -> Path:
    if es_instalada():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "descargador" / "ui"
    return Path(__file__).parent / "ui"


def dir_datos() -> Path:
    """Carpeta escribible del usuario: yt-dlp activo y ajustes."""
    personalizada = os.environ.get("DESCARGADOR_DATOS")
    carpeta = Path(personalizada) if personalizada else _localappdata() / CARPETA_DATOS
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def herramienta(nombre: str) -> Path:
    return dir_herramientas() / nombre


_candado_copia = threading.Lock()


def ytdlp_activo() -> Path:
    """Copia de yt-dlp que se puede actualizar sola. Si falta o está vacía, se restaura.

    Se copia a un archivo temporal y luego se renombra: nadie puede ejecutar una copia a medias.
    """
    activo = dir_datos() / "bin" / "yt-dlp.exe"
    with _candado_copia:
        if not activo.is_file() or activo.stat().st_size == 0:
            activo.parent.mkdir(parents=True, exist_ok=True)
            temporal = activo.with_name(f"yt-dlp.{os.getpid()}.tmp")
            shutil.copy2(herramienta("yt-dlp.exe"), temporal)
            os.replace(temporal, activo)
    return activo
