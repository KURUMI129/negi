from descargador import historial
from descargador.api import Api


def test_api_no_abre_rutas_ajenas(datos, tmp_path, monkeypatch):
    import os
    abiertos = []
    monkeypatch.setattr(os, "startfile", lambda r: abiertos.append(r), raising=False)
    ajeno = tmp_path / "otra cosa.exe"
    ajeno.write_bytes(b"x")
    api = Api()
    assert api.reproducir(str(ajeno)) is False
    assert abiertos == []


def test_api_reproduce_lo_del_historial(datos, tmp_path, monkeypatch):
    import os
    abiertos = []
    monkeypatch.setattr(os, "startfile", lambda r: abiertos.append(r), raising=False)
    video = tmp_path / "video.mkv"
    video.write_bytes(b"x")
    historial.agregar({"titulo": "v", "archivo": str(video), "miniatura": "", "modo": "max", "calidad": None})
    assert Api().reproducir(str(video)) is True
    assert abiertos == [str(video)]


def test_api_rechaza_calidad_o_modo_invalido(datos):
    api = Api()
    assert api.agregar_a_cola("https://x.com/v", "max", "9999") is None
    assert api.agregar_a_cola("https://x.com/v", "raro", "") is None
    assert api.cola() == []
