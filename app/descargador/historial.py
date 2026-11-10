"""Historial de descargas (últimas 100). Quitar algo del historial nunca borra el archivo."""

from __future__ import annotations

import datetime as dt
import json
import threading
import uuid
from pathlib import Path

from . import rutas

MAXIMO = 100
_candado = threading.Lock()


def _archivo() -> Path:
    return rutas.dir_datos() / "historial.json"


def _leer() -> list[dict]:
    try:
        datos = json.loads(_archivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [e for e in datos if isinstance(e, dict) and "id" in e] if isinstance(datos, list) else []


def _escribir(lista: list[dict]) -> None:
    temporal = _archivo().with_suffix(".tmp")
    temporal.write_text(json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(_archivo())


def cargar() -> list[dict]:
    """Lista del más nuevo al más viejo; `existe` dice si el archivo sigue en su lugar."""
    with _candado:
        lista = _leer()
    for e in lista:
        e["existe"] = bool(e.get("archivo")) and Path(e["archivo"]).exists()
    return lista


def agregar(entrada: dict) -> dict:
    nueva = {**entrada, "id": uuid.uuid4().hex[:12], "fecha": dt.datetime.now().isoformat(timespec="minutes")}
    nueva.pop("existe", None)
    with _candado:
        _escribir([nueva, *_leer()][:MAXIMO])
    return nueva


def quitar(ident: str) -> None:
    with _candado:
        _escribir([e for e in _leer() if e.get("id") != ident])


def contiene(ruta: str) -> bool:
    with _candado:
        return any(e.get("archivo") == ruta for e in _leer())
