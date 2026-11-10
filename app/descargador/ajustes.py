"""Recuerda la carpeta y el formato elegidos."""

from __future__ import annotations

import ctypes
import json
import threading
import uuid
from pathlib import Path

from . import rutas

MODOS = ("max", "mp4", "mp3")
CALIDADES = ("", "2160", "1440", "1080", "720", "480")  # "" = la máxima disponible
_candado = threading.Lock()

# {374DE290-123F-4565-9164-39C4925E467B} = carpeta "Descargas" de Windows
_FOLDERID_DOWNLOADS = uuid.UUID("374DE290-123F-4565-9164-39C4925E467B")


def carpeta_descargas() -> str:
    """La carpeta Descargas real del usuario, aunque la haya movido a otro disco."""
    try:
        guid = (ctypes.c_byte * 16).from_buffer_copy(_FOLDERID_DOWNLOADS.bytes_le)
        ruta = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(ruta)) == 0:
            try:
                if ruta.value and Path(ruta.value).is_dir():
                    return ruta.value
            finally:
                ctypes.windll.ole32.CoTaskMemFree(ruta)
    except (AttributeError, OSError):
        pass
    return str(Path.home() / "Downloads")


def _por_defecto() -> dict:
    return {"carpeta": carpeta_descargas(), "modo": "max", "calidad": "", "ultima_revision": ""}


def _archivo() -> Path:
    return rutas.dir_datos() / "ajustes.json"


def cargar() -> dict:
    a = _por_defecto()
    try:
        guardados = json.loads(_archivo().read_text(encoding="utf-8"))
        if isinstance(guardados, dict):
            a.update({k: v for k, v in guardados.items() if k in a and isinstance(v, str)})
    except (OSError, ValueError):
        pass
    if a["modo"] not in MODOS:
        a["modo"] = "max"
    if a["calidad"] not in CALIDADES:
        a["calidad"] = ""
    if not Path(a["carpeta"]).is_dir():
        a["carpeta"] = _por_defecto()["carpeta"]
    return a


def guardar(a: dict) -> None:
    with _candado:
        temporal = _archivo().with_suffix(".tmp")
        temporal.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
        temporal.replace(_archivo())
