"""Habla con yt-dlp.exe: vista previa, descarga con progreso, cancelar y actualizar."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

from . import rutas
from .errores import limpiar, mensaje_amigable

SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

FORMATOS = {
    "max": ["-f", "bv*+ba/b", "--merge-output-format", "mkv"],
    "mp4": ["-f", "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/bv*+ba/b", "--merge-output-format", "mp4"],
    "mp3": ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "0"],
}

AUDIO_KBPS = (320, 192, 128)

# Título recortado a 150 bytes: evita pasar el límite de rutas de Windows con títulos larguísimos.
PLANTILLA_NOMBRE = "%(title).150B [%(id)s].%(ext)s"
PLANTILLA_PROGRESO = ("download:PROG %(progress._percent_str)s|%(progress._speed_str)s|"
                      "%(progress._eta_str)s|%(info.vcodec)s|%(info.id)s")
PLANTILLA_PROCESO = "postprocess:POST %(progress.postprocessor)s"

BASURA = re.compile(r"(\.part(-Frag\d+)?|\.ytdl|\.f\d+\.\w+|\.temp\.\w+)$")

_candado_actualizar = threading.Lock()


class ErrorDescarga(Exception):
    """Error ya traducido a un mensaje entendible."""


def _entorno() -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _comunes() -> list[str]:
    args = ["--encoding", "utf-8", "--color", "never", "--no-warnings", "--socket-timeout", "15",
            "--ffmpeg-location", str(rutas.dir_herramientas())]
    deno = rutas.herramienta("deno.exe")
    if deno.is_file():
        args += ["--js-runtimes", f"deno:{deno}"]
    return args


def _comando(args: list[str]) -> list[str]:
    return [str(rutas.ytdlp_activo()), *args]


def _matar_arbol(pid: int) -> None:
    """yt-dlp.exe abre un proceso hijo (y ffmpeg otro): hay que cerrar todo el árbol."""
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, creationflags=SIN_VENTANA)


def formato(modo: str, calidad: int | None = None) -> list[str]:
    """Selector de formato. Para video, `calidad` = alto máximo en píxeles (si el video no la tiene,
    baja la mejor). Para MP3, `calidad` = kbps (320/192/128); sin calidad = la máxima (VBR 0)."""
    if modo == "mp3":
        if calidad in AUDIO_KBPS:
            return [*FORMATOS["mp3"][:-1], f"{int(calidad)}K"]
        return FORMATOS["mp3"]
    if not calidad:
        return FORMATOS[modo]
    h = f"[height<={int(calidad)}]"
    if modo == "max":
        selector = f"bv*{h}+ba/b{h}/bv*+ba/b"
    else:
        selector = f"bv*{h}[vcodec^=avc1]+ba[acodec^=mp4a]/bv*{h}+ba/b{h}/bv*+ba/b"
    return ["-f", selector, *FORMATOS[modo][2:]]


def argumentos(modo: str, carpeta: str, url: str, lista: bool = False, calidad: int | None = None) -> list[str]:
    """Argumentos para yt-dlp (sin el ejecutable)."""
    return [
        *_comunes(),
        *formato(modo, calidad),
        "--yes-playlist" if lista else "--no-playlist",
        "--windows-filenames",
        "--newline", "--progress",
        "--progress-template", PLANTILLA_PROGRESO,
        "--progress-template", PLANTILLA_PROCESO,
        "--print", "after_move:FIN %(filepath)s",
        "-P", carpeta,  # aparte de la plantilla: un "%" en el nombre de la carpeta no la rompe
        "-o", PLANTILLA_NOMBRE,
        "--", url,
    ]


def _numero(texto: str) -> float | None:
    try:
        return float(texto.strip().rstrip("%"))
    except ValueError:
        return None


def leer_linea(linea: str) -> dict | None:
    linea = linea.rstrip("\r\n")
    if linea.startswith("PROG "):
        partes = linea[5:].split("|")
        if len(partes) != 5:
            return None
        pct, vel, eta, vcodec, ident = (p.strip() for p in partes)
        return {"tipo": "progreso", "pct": _numero(pct), "vel": vel, "eta": eta,
                "parte": "audio" if vcodec == "none" else "video", "id": ident}
    if linea.startswith("POST "):
        return {"tipo": "procesando", "paso": linea[5:].strip()}
    if linea.startswith("FIN "):
        return {"tipo": "fin", "archivo": linea[4:]}
    if linea.startswith("ERROR:") or "ERROR:" in linea[:20]:
        return {"tipo": "error", "texto": linea.strip()}
    return None


def basura_tras_cancelar(nombres: list[str], antes: set[str], ids: set[str]) -> list[str]:
    """Archivos a medias que dejó una descarga cancelada. Nunca toca lo que ya existía antes."""
    marcas = [f"[{i}]" for i in ids if i and i != "NA"]
    return [n for n in nombres
            if n not in antes and (BASURA.search(n) or any(m in n for m in marcas))]


def _ejecutar(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    p = subprocess.Popen(_comando(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         stdin=subprocess.DEVNULL, creationflags=SIN_VENTANA, env=_entorno())
    try:
        salida, error = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _matar_arbol(p.pid)
        try:
            p.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        raise
    return subprocess.CompletedProcess(p.args, p.returncode, salida, error)


def vista_previa(url: str) -> dict:
    url = url.strip()
    if not url:
        raise ErrorDescarga("Pega primero el enlace del video.")
    try:
        r = _ejecutar([*_comunes(), "-J", "--no-playlist", "--flat-playlist", "--", url], timeout=45)
    except subprocess.TimeoutExpired:
        raise ErrorDescarga("La conexión tardó demasiado. Inténtalo de nuevo.") from None
    salida = r.stdout.decode("utf-8", "replace")
    if r.returncode != 0 or not salida.strip():
        raise ErrorDescarga(mensaje_amigable(r.stderr.decode("utf-8", "replace") or "error desconocido"))
    info = json.loads(salida)
    es_lista = info.get("_type") == "playlist"
    altos = [f.get("height") for f in info.get("formats") or [] if f.get("height") and f.get("vcodec") != "none"]
    miniaturas = info.get("thumbnails") or []
    miniatura = info.get("thumbnail") or (miniaturas[-1].get("url") if miniaturas else "")
    return {
        "titulo": info.get("title") or "Sin título",
        "canal": info.get("channel") or info.get("uploader") or "",
        "duracion": info.get("duration"),
        "miniatura": miniatura or "",
        "alto_max": max(altos) if altos else None,
        "es_lista": es_lista,
        "cantidad": len(info.get("entries") or []) if es_lista else 1,
    }


class Descarga:
    """Una descarga en segundo plano. Avisa con eventos dict a `al_evento`."""

    def __init__(self, url: str, modo: str, carpeta: str,
                 al_evento: Callable[[dict], None], lista: bool = False, calidad: int | None = None) -> None:
        self.url, self.modo, self.carpeta, self.lista = url.strip(), modo, carpeta, lista
        self.calidad = calidad
        self.al_evento = al_evento
        self.proceso: subprocess.Popen | None = None
        self.cancelada = False
        self._antes: set[str] = set()
        self._ids: set[str] = set()
        self._hilo: threading.Thread | None = None

    def iniciar(self) -> None:
        self._hilo = threading.Thread(target=self._trabajar, daemon=True)
        self._hilo.start()

    def esperar(self, timeout: float) -> None:
        """Espera a que el hilo termine (por ejemplo, para limpiar antes de cerrar la app)."""
        if self._hilo:
            self._hilo.join(timeout)

    def cancelar(self) -> None:
        self.cancelada = True
        p = self.proceso
        if p and p.poll() is None:
            _matar_arbol(p.pid)

    def _limpiar(self) -> None:
        carpeta = Path(self.carpeta)
        for intento in range(4):
            try:
                pendientes = basura_tras_cancelar([p.name for p in carpeta.iterdir()], self._antes, self._ids)
            except OSError:
                return  # carpeta borrada o USB quitada: no hay nada que limpiar
            for nombre in pendientes:
                try:
                    (carpeta / nombre).unlink()
                except OSError:
                    pass  # ffmpeg aún lo tiene abierto: se reintenta
            if intento < 3 and any((carpeta / n).exists() for n in pendientes):
                time.sleep(0.3)
            else:
                return

    def _trabajar(self) -> None:
        archivos: list[str] = []
        ultimo_error = ""
        codigo = -1
        try:
            Path(self.carpeta).mkdir(parents=True, exist_ok=True)
            self._antes = {p.name for p in Path(self.carpeta).iterdir()}
            self.proceso = subprocess.Popen(
                _comando(argumentos(self.modo, self.carpeta, self.url, self.lista, self.calidad)),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                creationflags=SIN_VENTANA, env=_entorno())
            if self.cancelada:  # canceló justo mientras arrancaba
                self.cancelar()
            for crudo in self.proceso.stdout:
                evento = leer_linea(crudo.decode("utf-8", "replace"))
                if evento is None:
                    continue
                if evento["tipo"] == "fin":
                    archivos.append(evento["archivo"])
                elif evento["tipo"] == "error":
                    ultimo_error = evento["texto"]
                else:
                    if evento["tipo"] == "progreso":
                        self._ids.add(evento.pop("id"))
                    self.al_evento(evento)
            codigo = self.proceso.wait()
        except (OSError, ValueError) as e:  # ValueError: enlace con caracter nulo u otro argumento inválido
            ultimo_error = str(e)
        try:
            if self.cancelada:
                self._limpiar()
                self.al_evento({"tipo": "cancelado"})
            elif archivos and (codigo == 0 or self.lista):
                # En una lista, si falló algún video pero otros se guardaron, se avisa sin tratarlo como error.
                self.al_evento({"tipo": "listo", "archivo": archivos[-1], "cantidad": len(archivos),
                                "incompleta": codigo != 0})
            else:
                self.al_evento({"tipo": "error",
                                "texto": mensaje_amigable(ultimo_error or f"yt-dlp terminó con código {codigo}")})
        except Exception as e:  # noqa: BLE001 - la interfaz siempre debe recibir un final
            self.al_evento({"tipo": "error", "texto": mensaje_amigable(str(e))})


def version_ytdlp() -> str:
    try:
        return _ejecutar(["--version"], timeout=30).stdout.decode().strip()
    except (OSError, subprocess.TimeoutExpired):
        return "?"


def actualizar_ytdlp() -> str:
    """Actualiza la copia de yt-dlp con su mecanismo oficial. Nunca la deja rota ni corre dos veces a la vez."""
    if not _candado_actualizar.acquire(blocking=False):
        return "Ya se está buscando una actualización."
    try:
        return _actualizar()
    except OSError:
        return "No se pudo buscar actualizaciones. Revisa tu conexión e inténtalo más tarde."
    finally:
        _candado_actualizar.release()


def _actualizar() -> str:
    activo = rutas.ytdlp_activo()
    respaldo = activo.with_suffix(".respaldo")
    shutil.copy2(activo, respaldo)
    try:
        r = _ejecutar(["-U"], timeout=180)
        texto = limpiar((r.stdout + r.stderr).decode("utf-8", "replace"))
    except (OSError, subprocess.TimeoutExpired) as e:
        texto = f"ERROR: {e}"
    finally:
        if not activo.is_file() or activo.stat().st_size == 0:
            shutil.copy2(respaldo, activo)
        respaldo.unlink(missing_ok=True)
    bajo = texto.lower()
    if "up to date" in bajo:
        return "Ya tienes la versión más reciente."
    m = re.search(r"updated yt-dlp to\s+\S*?([\d.]+)", texto, re.IGNORECASE)
    if m:
        return f"Actualizado a la versión {m.group(1)}."
    return "No se pudo buscar actualizaciones. Revisa tu conexión e inténtalo más tarde."
