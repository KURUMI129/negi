"""Ataques reales contra Negi (pruebas de seguridad locales, autorizadas por la dueña).

Cada prueba intenta tumbar o abusar de la app; si alguna falla, hay una vulnerabilidad.
"""

import sys
import threading

import pytest

from descargador import motor
from descargador.api import Api


@pytest.fixture
def api(datos):
    return Api()


# ---- 1. Caracter nulo: no debe dejar la descarga ni la cola colgadas ----

def test_ataque_nulo_en_descarga_termina_con_error(monkeypatch, tmp_path):
    monkeypatch.setattr(motor, "_comando", lambda args: [sys.executable, "-c", "pass", *args])
    final = threading.Event()
    eventos = []

    def al(e):
        eventos.append(e)
        if e["tipo"] in ("listo", "error", "cancelado"):
            final.set()

    motor.Descarga("https://x.com/v\x00--exec calc", "max", str(tmp_path), al).iniciar()
    assert final.wait(10), "la descarga se quedó colgada para siempre"
    assert eventos[-1]["tipo"] == "error"


def test_ataque_nulo_en_vista_previa(api):
    r = api.vista_previa("https://x.com/v\x00")
    assert r["ok"] is False


# ---- 2/3. Enlaces gigantes o que no son de internet ----

@pytest.mark.parametrize("url", [
    "https://x.com/" + "a" * 1_000_000,           # 1 MB
    "file:///C:/Windows/win.ini",                  # leer archivos locales
    "FILE:///C:/Users",                            # mayúsculas
    "javascript:alert(1)",
    "\\\\servidor\\compartido\\x.mp4",            # ruta de red de Windows
    "C:\\Windows\\System32\\calc.exe",
    "https://x.com/\nv",                           # salto de línea
    "https://you​tube.com/watch?v=1",         # espacio invisible que disfraza el dominio
    "https://‮moc.ebutuoy/watch?v=1",         # texto al revés (RTL override)
    "https://youtube.com﻿/watch?v=1",          # marca invisible BOM
])
def test_ataque_enlaces_no_validos_se_rechazan(api, url):
    assert api.agregar_a_cola(url, "max", "") is None
    assert api.vista_previa(url)["ok"] is False
    assert api.cola() == []


def test_enlace_normal_sigue_funcionando(api, monkeypatch):
    monkeypatch.setattr(api._cola, "agregar", lambda *a, **k: "id1")
    assert api.agregar_a_cola("https://www.youtube.com/watch?v=jNQXAC9IVRw", "max", "") == "id1"
    assert api.agregar_a_cola("youtu.be/jNQXAC9IVRw", "max", "") == "id1"  # sin https:// también vale


# ---- 5. La ventana solo ve las funciones que necesita ----

def test_superficie_minima_expuesta_a_la_ventana():
    publicos = {n for n in dir(Api) if not n.startswith("_") and callable(getattr(Api, n))}
    assert publicos == {
        "abrir_carpeta", "abrir_licencias", "actualizar_app", "agregar_a_cola", "buscar_actualizacion",
        "cola", "descargar", "elegir_carpeta", "historial", "info", "llamar_atencion", "portapapeles",
        "quitar_de_cola", "quitar_historial", "reproducir", "revisar_espacio", "version_motor", "vista_previa"}


# ---- 6. Actualizador contra un servidor malicioso (simulado) ----

def test_ataque_redireccion_a_sitio_malicioso():
    import urllib.error
    import urllib.request
    from descargador import actualizador
    req = urllib.request.Request("https://github.com/KURUMI129/negi/releases/download/v9/Negi-Setup.exe")
    with pytest.raises(urllib.error.URLError):
        actualizador._SoloGitHub().redirect_request(req, None, 302, "Found", {}, "https://malo.example/virus.exe")
    with pytest.raises(urllib.error.URLError):
        actualizador._SoloGitHub().redirect_request(req, None, 302, "Found", {}, "http://release-assets.githubusercontent.com/x")


class _RespuestaFalsa:
    def __init__(self, cuerpo: bytes, largo: int | None = None):
        import io
        self._b = io.BytesIO(cuerpo)
        self.headers = {"Content-Length": str(largo if largo is not None else len(cuerpo))}

    def read(self, n=-1):
        return self._b.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _info():
    from descargador import actualizador
    return {"version": "9.9.9", "notas": "", "sha256": "https://github.com/x/negi/releases/download/v9.9.9/h",
            "instalador": "https://github.com/x/negi/releases/download/v9.9.9/Negi-Setup.exe"}


def test_ataque_archivo_gigante_no_llena_el_disco(monkeypatch, tmp_path):
    from descargador import actualizador
    monkeypatch.setattr(actualizador.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(actualizador, "MAX_TAMANO", 1024)
    lanzados = []
    monkeypatch.setattr(actualizador.subprocess, "Popen", lambda *a, **k: lanzados.append(a))

    def abrir(url, timeout=15):
        if url.endswith("/h"):
            return _RespuestaFalsa(b"0" * 64)
        return _RespuestaFalsa(b"x" * 10_000, largo=0)  # miente sobre el tamaño

    monkeypatch.setattr(actualizador, "_abrir", abrir)
    assert actualizador.descargar_e_instalar(_info(), lambda p: None) is not None
    assert lanzados == [] and list(tmp_path.iterdir()) == []


def test_ataque_huella_falsa_no_instala(monkeypatch, tmp_path):
    from descargador import actualizador
    monkeypatch.setattr(actualizador.tempfile, "gettempdir", lambda: str(tmp_path))
    lanzados = []
    monkeypatch.setattr(actualizador.subprocess, "Popen", lambda *a, **k: lanzados.append(a))
    monkeypatch.setattr(actualizador, "_abrir", lambda url, timeout=15: _RespuestaFalsa(
        b"f" * 64 if url.endswith("/h") else b"VIRUS"))
    assert actualizador.descargar_e_instalar(_info(), lambda p: None) is not None
    assert lanzados == [] and list(tmp_path.iterdir()) == []


def test_ataque_bajar_a_version_vieja():
    from descargador import actualizador
    vieja = {"tag_name": "v0.1.0", "assets": [
        {"name": "Negi-Setup.exe", "browser_download_url": "https://github.com/x/negi/releases/download/v0.1.0/Negi-Setup.exe"},
        {"name": "Negi-Setup.exe.sha256", "browser_download_url": "https://github.com/x/negi/releases/download/v0.1.0/h"}]}
    info = actualizador.elegir_mas_nueva([vieja])
    assert info and not actualizador.es_mas_nueva(info["version"], "1.3.0")


# ---- 4. Inundar la cola ----

def test_ataque_inundar_la_cola(api, monkeypatch):
    agregados = []
    monkeypatch.setattr(api._cola, "agregar", lambda *a, **k: agregados.append(1) or str(len(agregados)))
    monkeypatch.setattr(api._cola, "elementos", lambda: [{}] * len(agregados))
    resultados = [api.agregar_a_cola(f"https://x.com/{i}", "max", "") for i in range(5000)]
    assert len(agregados) <= Api.MAX_COLA
    assert resultados[-1] is None
