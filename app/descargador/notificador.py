"""Aviso de versiones nuevas aunque Negi esté cerrada: una tarea diaria de Windows (por usuario, sin admin)
ejecuta `Negi.exe --revisar-actualizacion`, que muestra una notificación una sola vez por versión."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import actualizador, ajustes

NOMBRE_TAREA = r"Negi\Revisar actualizaciones"
AUMID = "KURUMI129.Negi"  # el mismo que lleva el acceso del menú Inicio (instalador)
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# El script es FIJO: el título y el texto llegan por variables de entorno y se escapan como XML dentro de PowerShell.
_SCRIPT = (
    "$ErrorActionPreference='Stop';"
    "[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]|Out-Null;"
    "[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,ContentType=WindowsRuntime]|Out-Null;"
    "$t=[Security.SecurityElement]::Escape($env:NEGI_TITULO);$x=[Security.SecurityElement]::Escape($env:NEGI_TEXTO);"
    "$d=New-Object Windows.Data.Xml.Dom.XmlDocument;"
    "$d.LoadXml(\"<toast><visual><binding template='ToastGeneric'><text>$t</text><text>$x</text></binding></visual></toast>\");"
    "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:NEGI_AUMID).Show("
    "[Windows.UI.Notifications.ToastNotification]::new($d))"
)


def registrar_tarea(exe: Path) -> bool:
    exe = Path(exe)
    if exe.name.lower() != "negi.exe" or not exe.is_file() or '"' in str(exe):
        return False
    r = subprocess.run(["schtasks", "/Create", "/SC", "DAILY", "/ST", "12:00", "/TN", NOMBRE_TAREA,
                        "/TR", f'"{exe}" --revisar-actualizacion', "/F"],
                       capture_output=True, creationflags=SIN_VENTANA)
    return r.returncode == 0


def borrar_tarea() -> bool:
    r = subprocess.run(["schtasks", "/Delete", "/TN", NOMBRE_TAREA, "/F"], capture_output=True,
                       creationflags=SIN_VENTANA)
    return r.returncode == 0


def mostrar_notificacion(titulo: str, texto: str) -> None:
    env = {**os.environ, "NEGI_TITULO": str(titulo)[:120], "NEGI_TEXTO": str(texto)[:240], "NEGI_AUMID": AUMID}
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                        "-WindowStyle", "Hidden", "-Command", _SCRIPT],
                       capture_output=True, creationflags=SIN_VENTANA, env=env, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        pass  # una notificación que no sale no debe romper nada


def revisar_y_avisar(version_local: str) -> str | None:
    """Revisa GitHub; si hay versión nueva que aún no se avisó, muestra la notificación. Devuelve esa versión."""
    a = ajustes.cargar()
    if a.get("aviso_cerrada") == "no":
        return None
    info = actualizador.buscar(version_local)
    if not info or a.get("ultima_avisada") == info["version"]:
        return None
    mostrar_notificacion(f"Negi {info['version']} ya está disponible",
                         "Abre Negi y pulsa «Actualizar» para tener lo más nuevo.")
    a["ultima_avisada"] = info["version"]
    try:
        ajustes.guardar(a)
    except OSError:
        pass
    return info["version"]
