"""Abre la ventana de la app."""

from __future__ import annotations

import ctypes
import webbrowser

from . import NOMBRE, rutas
from .api import Api

ENLACE_WEBVIEW2 = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"


def _aviso(titulo: str, texto: str, botones: int = 0x40) -> int:
    return ctypes.windll.user32.MessageBoxW(None, texto, titulo, botones)


def main() -> None:
    try:
        import webview
    except Exception as e:  # noqa: BLE001
        _aviso(NOMBRE, f"No se pudo iniciar la ventana:\n{e}", 0x10)
        return

    try:
        # Se prepara yt-dlp antes de abrir la ventana, para que la vista previa y la revisión de
        # actualizaciones no lo copien al mismo tiempo en el primer arranque.
        rutas.ytdlp_activo()
    except OSError as e:
        _aviso(NOMBRE, f"No se pudo preparar el programa:\n{e}\n\nPrueba a reinstalarlo.", 0x10)
        return

    api = Api()
    ventana = webview.create_window(
        NOMBRE, url=str(rutas.dir_ui() / "index.html"), js_api=api,
        width=580, height=760, min_size=(480, 640), background_color="#F3F5F6", text_select=False)
    api.conectar(ventana)

    def al_cerrar():
        if api.descargando():
            # MessageBox nativo: el diálogo de pywebview puede bloquearse dentro del evento de cierre.
            MB_YESNO_PREGUNTA_SEGUNDO = 0x4 | 0x20 | 0x100 | 0x40000  # Sí/No, "?", "No" por defecto, al frente
            if _aviso("Descargas en curso", "Hay descargas en curso o en la cola.\n¿Cerrar y cancelarlas?",
                      MB_YESNO_PREGUNTA_SEGUNDO) != 6:
                return False
            api.cancelar_y_esperar(10)
        return True

    ventana.events.closing += al_cerrar
    ventana.events.loaded += api.revisar_al_abrir

    try:
        webview.start(gui="edgechromium", private_mode=True)
    except Exception:  # noqa: BLE001 - normalmente falta WebView2
        respuesta = _aviso(
            NOMBRE,
            "Para abrir esta app hace falta “Microsoft Edge WebView2”, un componente gratuito de Windows.\n\n"
            "¿Abrir la página oficial de Microsoft para instalarlo?", 0x44)
        if respuesta == 6:  # Sí
            webbrowser.open(ENLACE_WEBVIEW2)


if __name__ == "__main__":
    main()
