"""Puente entre la interfaz (JavaScript) y el motor (Python)."""

from __future__ import annotations

import ctypes
import datetime as dt
import json
import os
import subprocess
import threading
from pathlib import Path

from . import NOMBRE, VERSION, actualizador, ajustes, historial, motor, rutas
from .cola import Cola
from .errores import mensaje_amigable


def leer_portapapeles() -> str:
    """Texto del portapapeles de Windows (vacío si no hay texto)."""
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.GetClipboardData.restype = ctypes.c_void_p
    CF_UNICODETEXT = 13
    if not user32.OpenClipboard(None):
        return ""
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = kernel32.GlobalLock(h)
        try:
            return ctypes.wstring_at(p) if p else ""
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def parpadear_ventana() -> None:
    """Hace parpadear en la barra de tareas la ventana de esta app (hasta que se le dé clic)."""
    user32 = ctypes.windll.user32
    pid_propio = os.getpid()
    encontradas: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def revisar(hwnd, _):
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
        if pid.value == pid_propio and user32.IsWindowVisible(ctypes.c_void_p(hwnd)) \
                and user32.GetWindowTextLengthW(ctypes.c_void_p(hwnd)) > 0:
            encontradas.append(hwnd)
        return True

    user32.EnumWindows(revisar, None)

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("hwnd", ctypes.c_void_p), ("dwFlags", ctypes.c_uint),
                    ("uCount", ctypes.c_uint), ("dwTimeout", ctypes.c_uint)]

    FLASHW_ALL, FLASHW_TIMERNOFG = 0x3, 0xC
    for hwnd in encontradas:
        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_ALL | FLASHW_TIMERNOFG, 0, 0)
        user32.FlashWindowEx(ctypes.byref(info))


class Api:
    """Métodos que la interfaz puede llamar con `pywebview.api.<nombre>()`."""

    def __init__(self) -> None:
        self._ventana = None
        self._ajustes = ajustes.cargar()
        self._recientes: set[str] = set()  # archivos terminados en esta sesión
        self._cola = Cola(self._emitir)
        self._version_nueva: dict | None = None

    # --- uso interno -----------------------------------------------------
    def conectar(self, ventana) -> None:
        self._ventana = ventana

    def _emitir(self, evento: dict) -> None:
        if evento["tipo"] == "listo":
            self._recientes.add(evento["archivo"])
        if self._ventana:
            self._ventana.evaluate_js(f"window.alEvento({json.dumps(evento, ensure_ascii=False)})")

    def descargando(self) -> bool:
        return self._cola.ocupada()

    def _ruta_permitida(self, ruta: str) -> bool:
        """La interfaz solo puede abrir archivos que esta app descargó (no cualquier ruta)."""
        return bool(ruta) and (ruta in self._recientes or historial.contiene(ruta))

    # --- llamadas desde la interfaz -------------------------------------
    def info(self) -> dict:
        return {"nombre": NOMBRE, "version": VERSION, **self._ajustes}

    def vista_previa(self, url: str) -> dict:
        try:
            return {"ok": True, **motor.vista_previa(url)}
        except motor.ErrorDescarga as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:  # noqa: BLE001 - nunca dejar la interfaz colgada
            return {"ok": False, "error": mensaje_amigable(str(e))}

    def agregar_a_cola(self, url: str, modo: str, calidad: str = "", lista: bool = False,
                       titulo: str = "", miniatura: str = "", al_frente: bool = False) -> str | None:
        if modo not in ajustes.MODOS or calidad not in ajustes.CALIDADES or not url.strip():
            return None
        carpeta = self._ajustes["carpeta"]
        if not Path(carpeta).is_dir():
            carpeta = ajustes.cargar()["carpeta"]  # vuelve a Descargas si la carpeta ya no existe
        self._ajustes.update(modo=modo, calidad=calidad, carpeta=carpeta)
        self._guardar()
        return self._cola.agregar(url.strip(), modo, int(calidad) if calidad else None, carpeta,
                                  titulo=titulo, miniatura=miniatura, lista=lista, al_frente=al_frente)

    def descargar(self, url: str, modo: str, calidad: str = "", lista: bool = False,
                  titulo: str = "", miniatura: str = "") -> str | None:
        """'Descargar ahora': entra al frente de la cola."""
        return self.agregar_a_cola(url, modo, calidad, lista, titulo, miniatura, al_frente=True)

    def quitar_de_cola(self, ident: str) -> None:
        self._cola.quitar(ident)

    def cola(self) -> list[dict]:
        return self._cola.elementos()

    def cancelar_y_esperar(self, timeout: float = 10) -> None:
        """Al cerrar la app: vacía la cola y deja que la descarga actual borre sus archivos a medias."""
        self._cola.cancelar_todo_y_esperar(timeout)

    def historial(self) -> list[dict]:
        return historial.cargar()

    def quitar_historial(self, ident: str) -> None:
        historial.quitar(ident)

    def llamar_atencion(self) -> None:
        try:
            parpadear_ventana()
        except (OSError, AttributeError):
            pass

    def elegir_carpeta(self) -> str | None:
        import webview
        tipo = getattr(getattr(webview, "FileDialog", None), "FOLDER", None)
        if tipo is None:
            tipo = webview.FOLDER_DIALOG
        elegida = self._ventana.create_file_dialog(tipo, directory=self._ajustes["carpeta"])
        if not elegida:
            return None
        carpeta = elegida[0] if isinstance(elegida, (list, tuple)) else elegida
        self._ajustes["carpeta"] = str(carpeta)
        self._guardar()
        return str(carpeta)

    def abrir_carpeta(self, archivo: str = "") -> None:
        try:
            if self._ruta_permitida(archivo) and Path(archivo).exists():
                subprocess.Popen(["explorer", "/select,", archivo])
            elif Path(self._ajustes["carpeta"]).is_dir():
                os.startfile(self._ajustes["carpeta"])
            else:
                os.startfile(ajustes.carpeta_descargas())
        except OSError:
            pass

    def reproducir(self, archivo: str) -> bool:
        try:
            if self._ruta_permitida(archivo) and Path(archivo).exists():
                os.startfile(archivo)
                return True
        except OSError:
            pass
        return False

    def portapapeles(self) -> str:
        try:
            return leer_portapapeles().strip()
        except OSError:
            return ""

    def version_motor(self) -> str:
        return motor.version_ytdlp()

    def buscar_actualizacion(self) -> str:
        if self._cola.ocupada():
            return "Espera a que terminen las descargas para actualizar."
        resultado = motor.actualizar_ytdlp()
        self._ajustes["ultima_revision"] = dt.date.today().isoformat()
        self._guardar()
        return resultado

    def abrir_licencias(self) -> None:
        carpeta = rutas.dir_herramientas().parent / "licencias"
        try:
            if carpeta.is_dir():
                os.startfile(carpeta)
        except OSError:
            pass

    # --- actualizaciones de la app (GitHub Releases) ----------------------
    def actualizar_app(self) -> str | None:
        """Baja e instala la versión nueva. Devuelve un mensaje de error o None si arrancó bien."""
        if self._cola.ocupada():
            return "Espera a que terminen las descargas para actualizar Negi."
        info = self._version_nueva or actualizador.buscar(VERSION)
        if not info:
            return "Ya tienes la versión más reciente de Negi."

        def trabajo() -> None:
            error = actualizador.descargar_e_instalar(
                info, lambda pct: self._emitir({"tipo": "actualizando", "pct": pct}))
            if error:
                self._emitir({"tipo": "actualizando", "error": error})
            elif self._ventana:
                self._ventana.destroy()  # el instalador reemplaza los archivos y vuelve a abrir Negi

        threading.Thread(target=trabajo, daemon=True).start()
        return None

    # --- revisión automática al abrir ------------------------------------
    def revisar_al_abrir(self) -> None:
        def buscar_app() -> None:
            self._version_nueva = actualizador.buscar(VERSION)
            if self._version_nueva:
                self._emitir({"tipo": "version_nueva", "version": self._version_nueva["version"],
                              "notas": self._version_nueva["notas"][:400]})

        threading.Thread(target=buscar_app, daemon=True).start()
        hoy = dt.date.today().isoformat()
        if self._ajustes.get("ultima_revision") == hoy:
            return

        def trabajo() -> None:
            resultado = motor.actualizar_ytdlp()
            if not resultado.startswith("No se pudo"):
                self._ajustes["ultima_revision"] = hoy
                self._guardar()
            if resultado.startswith("Actualizado"):
                self._emitir({"tipo": "aviso", "texto": "Se actualizó el motor de descargas. " + resultado})

        threading.Thread(target=trabajo, daemon=True).start()

    def _guardar(self) -> None:
        try:
            ajustes.guardar(self._ajustes)
        except OSError:
            pass
