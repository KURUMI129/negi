from descargador import historial


def _entrada(i, archivo):
    return {"titulo": f"Video {i}", "archivo": str(archivo), "miniatura": "", "modo": "max", "calidad": ""}


def test_historial_vacio(datos):
    assert historial.cargar() == []


def test_historial_corrupto(datos):
    datos.mkdir(parents=True)
    (datos / "historial.json").write_text("[{roto", encoding="utf-8")
    assert historial.cargar() == []


def test_historial_agrega_al_principio_con_id_y_fecha(datos, tmp_path):
    a = tmp_path / "a.mkv"
    a.write_bytes(b"x")
    e = historial.agregar(_entrada(1, a))
    assert e["id"] and e["fecha"]
    historial.agregar(_entrada(2, a))
    assert [x["titulo"] for x in historial.cargar()] == ["Video 2", "Video 1"]


def test_historial_limite_100(datos, tmp_path):
    for i in range(105):
        historial.agregar(_entrada(i, tmp_path / "x.mkv"))
    lista = historial.cargar()
    assert len(lista) == historial.MAXIMO == 100
    assert lista[0]["titulo"] == "Video 104"


def test_historial_quitar_no_borra_archivo(datos, tmp_path):
    a = tmp_path / "mi video.mkv"
    a.write_bytes(b"x")
    e = historial.agregar(_entrada(1, a))
    historial.quitar(e["id"])
    assert historial.cargar() == []
    assert a.exists()


def test_historial_marca_archivo_inexistente(datos, tmp_path):
    a = tmp_path / "existe.mkv"
    a.write_bytes(b"x")
    historial.agregar(_entrada(1, tmp_path / "borrado.mkv"))
    historial.agregar(_entrada(2, a))
    assert [x["existe"] for x in historial.cargar()] == [True, False]


def test_historial_contiene_ruta(datos, tmp_path):
    a = tmp_path / "a.mkv"
    historial.agregar(_entrada(1, a))
    assert historial.contiene(str(a))
    assert not historial.contiene(str(tmp_path / "otro.mkv"))
