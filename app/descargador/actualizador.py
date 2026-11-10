"""Actualiza Negi desde GitHub Releases: busca la última versión, baja el instalador,
comprueba su huella SHA-256 y lo ejecuta en silencio."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

# Repositorio público donde se publican las versiones ("usuario/repositorio").
REPO = "KURUMI129/negi"
INSTALADOR = "Negi-Setup.exe"
ORIGENES_PERMITIDOS = ("https://github.com/", "https://objects.githubusercontent.com/")
_HASH = re.compile(r"\b[0-9a-fA-F]{64}\b")


def _numeros(version: str) -> tuple[int, ...] | None:
    v = version.strip().lstrip("vV")
    if not re.fullmatch(r"\d+(\.\d+)*", v):
        return None
    return tuple(int(x) for x in v.split("."))


def es_mas_nueva(remota: str, local: str) -> bool:
    r, l = _numeros(remota), _numeros(local)
    if r is None or l is None:
        return False
    largo = max(len(r), len(l))
    return r + (0,) * (largo - len(r)) > l + (0,) * (largo - len(l))


def leer_lanzamiento(datos: dict) -> dict | None:
    """Extrae versión, notas y enlaces del JSON de GitHub. Solo acepta enlaces de GitHub."""
    archivos = {a.get("name"): a.get("browser_download_url", "") for a in datos.get("assets") or []}
    instalador, huella = archivos.get(INSTALADOR, ""), archivos.get(INSTALADOR + ".sha256", "")
    if not (destino_permitido(instalador) and destino_permitido(huella)):
        return None
    return {"version": (datos.get("tag_name") or "").lstrip("vV"), "notas": datos.get("body") or "",
            "instalador": instalador, "sha256": huella}


HOSTS_PERMITIDOS = {"github.com", "api.github.com", "objects.githubusercontent.com",
                    "release-assets.githubusercontent.com"}


def destino_permitido(url: str) -> bool:
    """Solo https y solo servidores de GitHub (también para cada redirección)."""
    p = urllib.parse.urlsplit(url)
    return p.scheme == "https" and (p.hostname or "").lower() in HOSTS_PERMITIDOS


class _SoloGitHub(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not destino_permitido(newurl):
            raise urllib.error.URLError(f"redirección no permitida: {urllib.parse.urlsplit(newurl).hostname}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_abridor = urllib.request.build_opener(_SoloGitHub)


def _abrir(url: str, timeout: float = 15):
    if not destino_permitido(url):
        raise urllib.error.URLError("dirección no permitida")
    req = urllib.request.Request(url, headers={"User-Agent": "Negi", "Accept": "application/vnd.github+json"})
    return _abridor.open(req, timeout=timeout)


def elegir_mas_nueva(lanzamientos: list[dict]) -> dict | None:
    """La versión publicada (no borrador ni de prueba) más nueva que traiga el instalador de Windows.
    Así una versión que solo trae el APK de Android no confunde a la app de Windows."""
    mejor = None
    for datos in lanzamientos:
        if not isinstance(datos, dict) or datos.get("draft") or datos.get("prerelease"):
            continue
        info = leer_lanzamiento(datos)
        if info and _numeros(info["version"]) and (mejor is None or es_mas_nueva(info["version"], mejor["version"])):
            mejor = info
    return mejor


def buscar(version_local: str) -> dict | None:
    """Devuelve la info de una versión más nueva, o None (sin internet, sin versión nueva, repo sin configurar)."""
    if REPO.startswith("PENDIENTE"):
        return None
    try:
        with _abrir(f"https://api.github.com/repos/{REPO}/releases?per_page=20") as r:
            datos = json.load(r)
        info = elegir_mas_nueva(datos if isinstance(datos, list) else [])
    except (OSError, ValueError):
        return None
    return info if info and es_mas_nueva(info["version"], version_local) else None


def verificar(archivo: Path, texto_huella: str) -> bool:
    m = _HASH.search(texto_huella or "")
    if not m:
        return False
    h = hashlib.sha256()
    with open(archivo, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest().lower() == m.group(0).lower()


def descargar_e_instalar(info: dict, al_progreso: Callable[[float], None]) -> str | None:
    """Baja el instalador, lo verifica y lo lanza. Devuelve None si todo bien, o un mensaje de error."""
    if _numeros(info.get("version", "")) is None:  # solo números y puntos: nunca una ruta
        return "La versión publicada no es válida; no se instaló nada."
    destino = Path(tempfile.gettempdir()) / f"Negi-Setup-{info['version']}.exe"
    try:
        with _abrir(info["sha256"]) as r:
            huella = r.read(4096).decode("utf-8", "replace")
        with _abrir(info["instalador"], timeout=60) as r, open(destino, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            hecho = 0
            for bloque in iter(lambda: r.read(1 << 20), b""):
                f.write(bloque)
                hecho += len(bloque)
                if total:
                    al_progreso(hecho * 100 / total)
    except OSError:
        return "No se pudo descargar la actualización. Revisa tu conexión e inténtalo más tarde."
    if not verificar(destino, huella):
        destino.unlink(missing_ok=True)
        return "La actualización descargada no pasó la verificación de seguridad y se borró."
    # El instalador cierra Negi, lo actualiza y lo vuelve a abrir solo.
    subprocess.Popen([str(destino), "/SILENT", "/CURRENTUSER", "/NORESTART"], close_fds=True)
    return None
