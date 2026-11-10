from descargador.errores import mensaje_amigable


def test_error_video_no_disponible():
    m = mensaje_amigable("ERROR: [youtube] xxxxxxxxxxx: This video is unavailable")
    assert m.startswith("El video no está disponible")


def test_error_enlace_invalido():
    m = mensaje_amigable("ERROR: [generic] 'hola' is not a valid URL")
    assert m.startswith("Ese texto no es un enlace válido")


def test_error_sin_internet():
    m = mensaje_amigable("ERROR: Unable to download webpage: <urlopen error [Errno 11001] getaddrinfo failed>")
    assert m.startswith("No hay conexión a internet")


def test_error_desconocido_sugiere_actualizar():
    m = mensaje_amigable("ERROR: algo rarísimo")
    assert "actualiza" in m.lower()


def test_error_quita_codigos_de_color():
    m = mensaje_amigable("\x1b[0;31mERROR:\x1b[0m algo rarísimo")
    assert "\x1b" not in m
