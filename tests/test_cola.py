import threading
import time

import pytest

from descargador import historial, rutas
from descargador.cola import Cola


class DescargaFalsa:
    """Simula motor.Descarga: el comportamiento depende de la URL ('ok', 'falla', 'lento')."""

    def __init__(self, url, modo, carpeta, al_evento, lista=False, calidad=None):
        self.url, self.al_evento, self.calidad = url, al_evento, calidad
        self._cancelar = threading.Event()
        self._hilo = None

    def iniciar(self):
        self._hilo = threading.Thread(target=self._correr, daemon=True)
        self._hilo.start()

    def _correr(self):
        self.al_evento({"tipo": "progreso", "pct": 50.0, "vel": "1MiB/s", "eta": "00:01", "parte": "video"})
        if self.url.startswith("lento"):
            self._cancelar.wait(10)
            self.al_evento({"tipo": "cancelado"})
        elif self.url.startswith("falla"):
            self.al_evento({"tipo": "error", "texto": "El video es privado."})
        else:
            self.al_evento({"tipo": "listo", "archivo": f"C:/v/{self.url}.mkv", "cantidad": 1, "incompleta": False})

    def cancelar(self):
        self._cancelar.set()

    def esperar(self, timeout):
        if self._hilo:
            self._hilo.join(timeout)


def _cola(eventos):
    return Cola(eventos.append, fabrica=DescargaFalsa)


def _esperar_vacia(c, limite=5):
    fin = time.time() + limite
    while c.ocupada() and time.time() < fin:
        time.sleep(0.02)
    assert not c.ocupada()


def _finales(eventos):
    return [(e["tipo"], e["titulo"]) for e in eventos if e["tipo"] in ("listo", "error", "cancelado")]


def test_cola_orden(datos):
    ev = []
    c = _cola(ev)
    for u in ("ok1", "ok2", "ok3"):
        c.agregar(u, "max", None, "C:/v", titulo=u)
    _esperar_vacia(c)
    assert _finales(ev) == [("listo", "ok1"), ("listo", "ok2"), ("listo", "ok3")]


def test_cola_sigue_tras_error(datos):
    ev = []
    c = _cola(ev)
    c.agregar("falla1", "max", None, "C:/v", titulo="falla1")
    c.agregar("ok2", "max", None, "C:/v", titulo="ok2")
    _esperar_vacia(c)
    assert _finales(ev) == [("error", "falla1"), ("listo", "ok2")]


def test_cola_quitar_en_espera(datos):
    ev = []
    c = _cola(ev)
    c.agregar("lento1", "max", None, "C:/v", titulo="lento1")
    ident = c.agregar("ok2", "max", None, "C:/v", titulo="ok2")
    c.quitar(ident)
    assert [e["titulo"] for e in c.elementos()] == ["lento1"]
    c.quitar(c.elementos()[0]["id"])
    _esperar_vacia(c)
    assert _finales(ev) == [("cancelado", "lento1")]


def test_cola_quitar_el_actual_lo_cancela_y_sigue(datos):
    ev = []
    c = _cola(ev)
    actual = c.agregar("lento1", "max", None, "C:/v", titulo="lento1")
    c.agregar("ok2", "max", None, "C:/v", titulo="ok2")
    time.sleep(0.1)
    c.quitar(actual)
    _esperar_vacia(c)
    assert _finales(ev) == [("cancelado", "lento1"), ("listo", "ok2")]


def test_cola_progreso_lleva_id(datos):
    ev = []
    c = _cola(ev)
    ident = c.agregar("ok1", "max", None, "C:/v", titulo="ok1")
    _esperar_vacia(c)
    assert any(e["tipo"] == "progreso" and e["id"] == ident for e in ev)


def test_cola_avisa_cambios_de_la_lista(datos):
    ev = []
    c = _cola(ev)
    c.agregar("ok1", "max", None, "C:/v", titulo="ok1")
    _esperar_vacia(c)
    listas = [e["elementos"] for e in ev if e["tipo"] == "cola"]
    assert listas[0][0]["titulo"] == "ok1" and listas[-1] == []


def test_cola_listo_va_al_historial(datos):
    ev = []
    c = _cola(ev)
    c.agregar("ok1", "mp4", 720, "C:/v", titulo="Mi video", miniatura="https://img/x.jpg")
    _esperar_vacia(c)
    h = historial.cargar()
    assert h[0]["titulo"] == "Mi video" and h[0]["archivo"] == "C:/v/ok1.mkv"
    assert h[0]["modo"] == "mp4" and h[0]["calidad"] == 720


def test_cola_al_frente(datos):
    ev = []
    c = _cola(ev)
    c.agregar("lento1", "max", None, "C:/v", titulo="lento1")
    c.agregar("ok2", "max", None, "C:/v", titulo="ok2")
    c.agregar("ok3", "max", None, "C:/v", titulo="ok3", al_frente=True)
    assert [e["titulo"] for e in c.elementos()] == ["lento1", "ok3", "ok2"]
    c.cancelar_todo_y_esperar(5)
    assert c.elementos() == [] and not c.ocupada()


hay_herramientas = (rutas.dir_herramientas() / "yt-dlp.exe").is_file()


@pytest.mark.red
@pytest.mark.skipif(not hay_herramientas, reason="faltan herramientas")
def test_cola_dos_videos_reales(datos, tmp_path):
    tmp_path = tmp_path / "videos"
    tmp_path.mkdir()
    ev = []
    c = Cola(ev.append)
    c.agregar("https://www.youtube.com/watch?v=jNQXAC9IVRw", "mp4", 720, str(tmp_path), titulo="zoo mp4")
    c.agregar("https://www.youtube.com/watch?v=jNQXAC9IVRw", "mp3", None, str(tmp_path), titulo="zoo mp3")
    _esperar_vacia(c, limite=240)
    assert _finales(ev) == [("listo", "zoo mp4"), ("listo", "zoo mp3")]
    assert sorted(p.suffix for p in tmp_path.iterdir()) == [".mp3", ".mp4"]
