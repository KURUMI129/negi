import hashlib

import pytest

from descargador import actualizador

LANZAMIENTO = {
    "tag_name": "v1.2.0",
    "body": "Novedades: subtítulos.",
    "assets": [
        {"name": "Negi-Setup.exe", "browser_download_url": "https://github.com/x/negi/releases/download/v1.2.0/Negi-Setup.exe"},
        {"name": "Negi-Setup.exe.sha256", "browser_download_url": "https://github.com/x/negi/releases/download/v1.2.0/Negi-Setup.exe.sha256"},
        {"name": "Negi-1.2.0.apk", "browser_download_url": "https://github.com/x/negi/releases/download/v1.2.0/Negi-1.2.0.apk"},
    ],
}


@pytest.mark.parametrize("remota,local,esperado", [
    ("1.2.0", "1.1.0", True), ("1.1.0", "1.1.0", False), ("1.0.9", "1.1.0", False),
    ("1.10.0", "1.9.0", True), ("v2.0", "1.9.9", True), ("basura", "1.0.0", False),
])
def test_es_mas_nueva(remota, local, esperado):
    assert actualizador.es_mas_nueva(remota, local) is esperado


def test_leer_lanzamiento():
    info = actualizador.leer_lanzamiento(LANZAMIENTO)
    assert info == {"version": "1.2.0", "notas": "Novedades: subtítulos.",
                    "instalador": LANZAMIENTO["assets"][0]["browser_download_url"],
                    "sha256": LANZAMIENTO["assets"][1]["browser_download_url"]}


def test_leer_lanzamiento_sin_instalador():
    assert actualizador.leer_lanzamiento({"tag_name": "v9.0.0", "assets": []}) is None


def test_solo_acepta_enlaces_de_github():
    malo = {**LANZAMIENTO, "assets": [{**LANZAMIENTO["assets"][0], "browser_download_url": "https://malo.example/x.exe"},
                                      LANZAMIENTO["assets"][1]]}
    assert actualizador.leer_lanzamiento(malo) is None


def test_no_instala_version_con_ruta_rara(monkeypatch):
    # Una versión como "..\..\Inicio\x" no debe usarse para nombrar archivos ni descargarse.
    llamadas = []
    monkeypatch.setattr(actualizador, "_abrir", lambda *a, **k: llamadas.append(a))
    info = {**actualizador.leer_lanzamiento(LANZAMIENTO), "version": r"..\..\Inicio\x"}
    assert actualizador.descargar_e_instalar(info, lambda p: None) is not None
    assert llamadas == []


def test_verificar_sha256(tmp_path):
    f = tmp_path / "Negi-Setup.exe"
    f.write_bytes(b"instalador")
    bueno = hashlib.sha256(b"instalador").hexdigest()
    assert actualizador.verificar(f, f"{bueno}  Negi-Setup.exe\n") is True
    assert actualizador.verificar(f, "0" * 64) is False
    assert actualizador.verificar(f, "") is False
