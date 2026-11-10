from pathlib import Path

from descargador import ajustes

DESCARGAS = ajustes.carpeta_descargas()


def test_carpeta_descargas_es_la_de_windows():
    # Respeta la carpeta Descargas real aunque el usuario la haya movido a otro disco.
    assert Path(DESCARGAS).is_dir()


def test_guardar_desde_varios_hilos_no_pierde_ajustes(datos):
    import threading
    errores = []

    def guardar(i):
        try:
            for _ in range(30):
                ajustes.guardar({"carpeta": DESCARGAS, "modo": "max", "ultima_revision": str(i)})
        except Exception as e:  # noqa: BLE001
            errores.append(e)

    hilos = [threading.Thread(target=guardar, args=(i,)) for i in range(4)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert errores == []


def test_ajustes_por_defecto_sin_archivo(datos):
    a = ajustes.cargar()
    assert a == {"carpeta": DESCARGAS, "modo": "max", "calidad": "", "ultima_revision": ""}


def test_ajustes_por_defecto_si_json_corrupto(datos):
    datos.mkdir(parents=True)
    (datos / "ajustes.json").write_text("{esto no es json", encoding="utf-8")
    assert ajustes.cargar()["modo"] == "max"


def test_ajustes_ida_y_vuelta(datos, tmp_path):
    destino = tmp_path / "Videos 🎬"
    destino.mkdir()
    guardados = {"carpeta": str(destino), "modo": "mp3", "calidad": "720", "ultima_revision": "2026-11-10"}
    ajustes.guardar(guardados)
    assert ajustes.cargar() == guardados


def test_ajustes_calidad_invalida_vuelve_a_maxima(datos):
    ajustes.guardar({"carpeta": DESCARGAS, "modo": "max", "calidad": "9999", "ultima_revision": ""})
    assert ajustes.cargar()["calidad"] == ""


def test_ajustes_carpeta_borrada_vuelve_a_descargas(datos, tmp_path):
    ajustes.guardar({"carpeta": str(tmp_path / "ya_no_existe"), "modo": "mp4", "ultima_revision": ""})
    a = ajustes.cargar()
    assert a["carpeta"] == DESCARGAS
    assert a["modo"] == "mp4"


def test_ajustes_modo_invalido_vuelve_a_max(datos):
    ajustes.guardar({"carpeta": DESCARGAS, "modo": "raro", "ultima_revision": ""})
    assert ajustes.cargar()["modo"] == "max"
