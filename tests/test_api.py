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


def test_api_calidad_cruzada_se_vuelve_maxima(datos, monkeypatch):
    api = Api()
    recibidas = []
    monkeypatch.setattr(api._cola, "agregar", lambda url, modo, calidad, *a, **k: recibidas.append((modo, calidad)) or "x")
    api.agregar_a_cola("https://x.com/v", "max", "320")   # kbps en un video
    api.agregar_a_cola("https://x.com/v", "mp3", "1080")  # píxeles en un audio
    api.agregar_a_cola("https://x.com/v", "mp3", "192")
    api.agregar_a_cola("https://x.com/v", "mp4", "720")
    assert recibidas == [("max", None), ("mp3", None), ("mp3", 192), ("mp4", 720)]


def test_api_revisar_espacio(datos, monkeypatch):
    import collections
    import shutil
    Uso = collections.namedtuple("Uso", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda p: Uso(10**12, 0, 3 * 10**9))
    api = Api()
    assert api.revisar_espacio(1 * 10**9) == {"suficiente": True, "libre": 3 * 10**9, "necesario": 2 * 10**9}
    assert api.revisar_espacio(2 * 10**9)["suficiente"] is False      # necesita ~4 GB, hay 3
    assert api.revisar_espacio(None)["suficiente"] is True            # tamaño desconocido: no se bloquea
    assert api.revisar_espacio("basura")["suficiente"] is True


def test_api_rechaza_calidad_o_modo_invalido(datos):
    api = Api()
    assert api.agregar_a_cola("https://x.com/v", "max", "9999") is None
    assert api.agregar_a_cola("https://x.com/v", "raro", "") is None
    assert api.cola() == []
