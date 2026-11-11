import threading

import pytest

from descargador import motor, rutas

URL_CORTO = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # "Me at the zoo", 19 s, 240p


# ---------- unitarias (sin red) ----------

def test_argumentos_max_mkv(tmp_path):
    a = motor.argumentos("max", str(tmp_path), URL_CORTO)
    assert a[a.index("-f") + 1] == "bv*+ba/b"
    assert a[a.index("--merge-output-format") + 1] == "mkv"
    assert "--no-playlist" in a
    assert a[-1] == URL_CORTO
    assert "--ffmpeg-location" in a
    # Carpeta aparte (-P) para que un "%" en su nombre no rompa la plantilla; título recortado a 150 bytes.
    assert a[a.index("-P") + 1] == str(tmp_path)
    assert a[a.index("-o") + 1] == "%(title).150B [%(id)s].%(ext)s"
    assert a[a.index("--socket-timeout") + 1] == "15"


def test_argumentos_calidad_1080_max(tmp_path):
    a = motor.argumentos("max", str(tmp_path), URL_CORTO, calidad=1080)
    assert a[a.index("-f") + 1] == "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b"


def test_argumentos_calidad_720_mp4(tmp_path):
    a = motor.argumentos("mp4", str(tmp_path), URL_CORTO, calidad=720)
    assert a[a.index("-f") + 1] == ("bv*[height<=720][vcodec^=avc1]+ba[acodec^=mp4a]/"
                                    "bv*[height<=720]+ba/b[height<=720]/bv*+ba/b")


def test_argumentos_calidad_de_video_no_afecta_mp3(tmp_path):
    a = motor.argumentos("mp3", str(tmp_path), URL_CORTO, calidad=720)
    assert a[a.index("-f") + 1] == "bestaudio/best"
    assert a[a.index("--audio-quality") + 1] == "0"


@pytest.mark.parametrize("kbps", [320, 192, 128])
def test_argumentos_mp3_con_kbps(tmp_path, kbps):
    a = motor.argumentos("mp3", str(tmp_path), URL_CORTO, calidad=kbps)
    assert a[a.index("-f") + 1] == "bestaudio/best"
    assert a[a.index("--audio-quality") + 1] == f"{kbps}K"


def test_argumentos_calidad_none_igual_que_antes(tmp_path):
    assert motor.argumentos("max", str(tmp_path), URL_CORTO, calidad=None) == \
        motor.argumentos("max", str(tmp_path), URL_CORTO)


def test_resumen_tamano_suma_video_y_audio():
    info = {"title": "x", "formats": [{"height": 1080, "vcodec": "avc1"}],
            "requested_formats": [{"filesize": 900_000_000}, {"filesize_approx": 100_000_000}]}
    assert motor.resumen_info(info)["tamano"] == 1_000_000_000


def test_resumen_tamano_aproximado_o_desconocido():
    assert motor.resumen_info({"title": "x", "filesize_approx": 5_000})["tamano"] == 5_000
    assert motor.resumen_info({"title": "x"})["tamano"] is None
    assert motor.resumen_info({"_type": "playlist", "title": "l", "entries": [{}, {}]})["tamano"] is None


def test_argumentos_mp4_prefiere_h264(tmp_path):
    a = motor.argumentos("mp4", str(tmp_path), URL_CORTO)
    assert a[a.index("-f") + 1] == "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/bv*+ba/b"
    assert a[a.index("--merge-output-format") + 1] == "mp4"


def test_argumentos_mp3_extrae_audio(tmp_path):
    a = motor.argumentos("mp3", str(tmp_path), URL_CORTO)
    assert "-x" in a
    assert a[a.index("--audio-format") + 1] == "mp3"
    assert a[a.index("--audio-quality") + 1] == "0"


def test_argumentos_lista_no_pone_no_playlist(tmp_path):
    a = motor.argumentos("max", str(tmp_path), URL_CORTO, lista=True)
    assert "--no-playlist" not in a
    assert "--yes-playlist" in a


def test_argumentos_url_que_empieza_con_guion_no_es_opcion(tmp_path):
    a = motor.argumentos("max", str(tmp_path), "--exec calc")
    assert a[-2:] == ["--", "--exec calc"]


def test_leer_linea_progreso():
    e = motor.leer_linea("PROG  45.3%|  8.40MiB/s|00:12|avc1.640028|jNQXAC9IVRw")
    assert e == {"tipo": "progreso", "pct": 45.3, "vel": "8.40MiB/s", "eta": "00:12", "parte": "video",
                 "id": "jNQXAC9IVRw"}


def test_leer_linea_audio():
    e = motor.leer_linea("PROG 100.0%|1.2MiB/s|00:00|none|abc")
    assert e["parte"] == "audio" and e["pct"] == 100.0


def test_leer_linea_porcentaje_desconocido():
    e = motor.leer_linea("PROG N/A|Unknown|Unknown|vp9|abc")
    assert e["pct"] is None


def test_leer_linea_procesando():
    assert motor.leer_linea("POST Merger") == {"tipo": "procesando", "paso": "Merger"}


def test_leer_linea_fin_con_emoji_en_ruta():
    ruta = r"C:\Users\x\Downloads\Canción 🎵 ＂rara＂ [abc].mkv"
    assert motor.leer_linea("FIN " + ruta) == {"tipo": "fin", "archivo": ruta}


def test_leer_linea_error():
    e = motor.leer_linea("ERROR: [youtube] xxxxxxxxxxx: This video is unavailable")
    assert e == {"tipo": "error", "texto": "ERROR: [youtube] xxxxxxxxxxx: This video is unavailable"}


def test_leer_linea_ruido_se_ignora():
    assert motor.leer_linea("[youtube] Extracting URL: x") is None
    assert motor.leer_linea("") is None


def test_basura_tras_cancelar(tmp_path):
    antes = {"viejo.part"}
    nombres = ["viejo.part", "Video [id].f399.mp4", "Video [id].f251.webm.part", "Video [id].mkv.ytdl",
               "Video [id].temp.mkv", "Video [id].webm.part-Frag3", "otro.mkv"]
    assert sorted(motor.basura_tras_cancelar(nombres, antes, set())) == sorted(nombres[1:6])


def test_basura_tras_cancelar_mp3_en_conversion():
    # Al convertir a MP3, yt-dlp deja "Titulo [id].webm" completo y un "Titulo [id].mp3" a medias.
    antes = {"Otra cancion [zzz].mp3"}
    nombres = ["Otra cancion [zzz].mp3", "Cancion [abc].webm", "Cancion [abc].mp3", "descarga del navegador.zip"]
    assert sorted(motor.basura_tras_cancelar(nombres, antes, {"abc"})) == ["Cancion [abc].mp3", "Cancion [abc].webm"]


def _comando_colgado(_args):
    # Igual que yt-dlp.exe (PyInstaller onefile): un proceso lanzador con un hijo que hereda las tuberías.
    import sys
    hijo = "import time; time.sleep(60)"
    padre = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {hijo!r}]); time.sleep(60)"
    return [sys.executable, "-c", padre]


def test_ejecutar_timeout_mata_todo_el_arbol(monkeypatch):
    import subprocess
    import time
    monkeypatch.setattr(motor, "_comando", _comando_colgado)
    inicio = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        motor._ejecutar(["--version"], timeout=2)
    assert time.monotonic() - inicio < 15


def test_actualizar_no_se_superpone(monkeypatch, datos, tmp_path):
    import subprocess
    import time
    falso = tmp_path / "yt-dlp.exe"
    falso.write_bytes(b"x" * 100)
    monkeypatch.setattr(rutas, "ytdlp_activo", lambda: falso)

    def lento(_args, timeout):
        time.sleep(1.5)
        return subprocess.CompletedProcess([], 0, b"yt-dlp is up to date", b"")

    monkeypatch.setattr(motor, "_ejecutar", lento)
    resultados = []
    hilos = [threading.Thread(target=lambda: resultados.append(motor.actualizar_ytdlp())) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert sorted(resultados) == ["Ya se está buscando una actualización.", "Ya tienes la versión más reciente."]
    assert falso.read_bytes() == b"x" * 100


def test_actualizar_no_lanza_si_falla_la_copia(monkeypatch, tmp_path):
    def roto():
        raise OSError("disco lleno")
    monkeypatch.setattr(rutas, "ytdlp_activo", roto)
    assert motor.actualizar_ytdlp().startswith("No se pudo")


def test_limpiar_tolera_carpeta_borrada(tmp_path):
    d = motor.Descarga("x", "max", str(tmp_path / "usb_quitada"), lambda e: None)
    d._limpiar()  # no debe lanzar


def test_descarga_esperar_termina_el_hilo(monkeypatch, tmp_path):
    eventos = []
    monkeypatch.setattr(motor, "_comando", lambda args: ["cmd", "/c", "exit 1"])
    d = motor.Descarga("x", "max", str(tmp_path), eventos.append)
    d.iniciar()
    d.esperar(10)
    assert eventos and eventos[-1]["tipo"] == "error"


# ---------- integración (necesitan internet y las herramientas) ----------

hay_herramientas = (rutas.dir_herramientas() / "yt-dlp.exe").is_file() and \
    (rutas.dir_herramientas() / "ffmpeg.exe").is_file()
red = pytest.mark.skipif(not hay_herramientas, reason="faltan herramientas: ejecuta empaquetado/binarios.ps1")


def _descargar(url, modo, carpeta, cancelar_al=None, timeout=180):
    eventos = []
    hecho = threading.Event()

    def al_evento(e):
        eventos.append(e)
        if e["tipo"] in ("listo", "error", "cancelado"):
            hecho.set()
        if cancelar_al and cancelar_al(e):
            d.cancelar()

    d = motor.Descarga(url, modo, str(carpeta), al_evento)
    d.iniciar()
    assert hecho.wait(timeout), f"no terminó; eventos: {eventos[-5:]}"
    return eventos


@pytest.mark.red
@red
def test_vista_previa_me_at_the_zoo(datos):
    v = motor.vista_previa(URL_CORTO)
    assert v["titulo"] == "Me at the zoo"
    assert v["alto_max"] == 240
    assert v["duracion"] == 19
    assert v["es_lista"] is False
    assert v["miniatura"].startswith("https://")


@pytest.mark.red
@red
def test_vista_previa_enlace_roto_mensaje_amigable(datos):
    with pytest.raises(motor.ErrorDescarga) as e:
        motor.vista_previa("https://www.youtube.com/watch?v=xxxxxxxxxxx")
    assert str(e.value).startswith("El video no está disponible")


@pytest.mark.red
@red
@pytest.mark.parametrize("modo,ext", [("max", ".mkv"), ("mp4", ".mp4"), ("mp3", ".mp3")])
def test_descarga_tres_modos(datos, tmp_path, modo, ext):
    tmp_path = tmp_path / "videos 🎬"
    eventos = _descargar(URL_CORTO, modo, tmp_path)
    final = eventos[-1]
    assert final["tipo"] == "listo", eventos[-3:]
    assert final["archivo"].endswith(ext)
    assert (tmp_path / final["archivo"].split("\\")[-1]).stat().st_size > 100_000
    assert any(e["tipo"] == "progreso" for e in eventos)
    assert [p.name for p in tmp_path.iterdir()] == [final["archivo"].split("\\")[-1]]


@pytest.mark.red
@red
def test_cancelar_borra_part(datos, tmp_path):
    # Video largo (más de 1 hora) para que dé tiempo de cancelar a media descarga.
    largo = "https://www.youtube.com/watch?v=LXb3EKWsInQ"
    tmp_path = tmp_path / "videos"
    eventos = _descargar(largo, "max", tmp_path,
                         cancelar_al=lambda e: e["tipo"] == "progreso" and (e["pct"] or 0) > 0.5)
    assert eventos[-1]["tipo"] == "cancelado"
    assert list(tmp_path.iterdir()) == []
