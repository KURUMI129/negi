from descargador import rutas


def _herramientas_falsas(tmp_path, monkeypatch, contenido=b"original"):
    h = tmp_path / "herramientas"
    h.mkdir()
    (h / "yt-dlp.exe").write_bytes(contenido)
    monkeypatch.setattr(rutas, "dir_herramientas", lambda: h)
    return h


def test_dir_datos_se_crea(datos):
    assert rutas.dir_datos() == datos
    assert datos.is_dir()


def test_ytdlp_activo_copia_si_falta(datos, tmp_path, monkeypatch):
    _herramientas_falsas(tmp_path, monkeypatch)
    activo = rutas.ytdlp_activo()
    assert activo == datos / "bin" / "yt-dlp.exe"
    assert activo.read_bytes() == b"original"


def test_ytdlp_activo_no_sobrescribe_existente(datos, tmp_path, monkeypatch):
    _herramientas_falsas(tmp_path, monkeypatch)
    (datos / "bin").mkdir(parents=True)
    (datos / "bin" / "yt-dlp.exe").write_bytes(b"actualizado")
    assert rutas.ytdlp_activo().read_bytes() == b"actualizado"


def test_ytdlp_activo_concurrente_no_deja_copias_a_medias(datos, tmp_path, monkeypatch):
    import threading
    contenido = b"z" * (40 * 1024 * 1024)
    _herramientas_falsas(tmp_path, monkeypatch, contenido)
    errores, tamanos = [], []

    def usar():
        try:
            tamanos.append(rutas.ytdlp_activo().stat().st_size)
        except Exception as e:  # noqa: BLE001
            errores.append(e)

    hilos = [threading.Thread(target=usar) for _ in range(6)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert errores == []
    assert tamanos == [len(contenido)] * 6


def test_ytdlp_activo_recupera_copia_vacia(datos, tmp_path, monkeypatch):
    # Una actualización interrumpida podría dejar un archivo vacío.
    _herramientas_falsas(tmp_path, monkeypatch)
    (datos / "bin").mkdir(parents=True)
    (datos / "bin" / "yt-dlp.exe").write_bytes(b"")
    assert rutas.ytdlp_activo().read_bytes() == b"original"
