import subprocess

from descargador import ajustes, notificador


class _Llamadas:
    def __init__(self, codigo=0):
        self.args, self.env, self.codigo = [], [], codigo

    def __call__(self, args, **k):
        self.args.append(list(args))
        self.env.append(k.get("env") or {})
        return subprocess.CompletedProcess(args, self.codigo, b"", b"")


def test_registrar_tarea(monkeypatch, tmp_path):
    exe = tmp_path / "Negi.exe"
    exe.write_bytes(b"x")
    ll = _Llamadas()
    monkeypatch.setattr(notificador.subprocess, "run", ll)
    assert notificador.registrar_tarea(exe) is True
    a = ll.args[0]
    assert a[:2] == ["schtasks", "/Create"] and a[a.index("/SC") + 1] == "DAILY"
    assert a[a.index("/TN") + 1] == r"Negi\Revisar actualizaciones"
    assert a[a.index("/TR") + 1] == f'"{exe}" --revisar-actualizacion'


def test_registrar_tarea_rechaza_rutas_raras(monkeypatch, tmp_path):
    ll = _Llamadas()
    monkeypatch.setattr(notificador.subprocess, "run", ll)
    assert notificador.registrar_tarea(tmp_path / "no-existe.exe") is False
    raro = tmp_path / "otro.exe"
    raro.write_bytes(b"x")
    assert notificador.registrar_tarea(raro) is False          # solo Negi.exe
    assert ll.args == []


def test_borrar_tarea(monkeypatch):
    ll = _Llamadas()
    monkeypatch.setattr(notificador.subprocess, "run", ll)
    assert notificador.borrar_tarea() is True
    assert ll.args[0] == ["schtasks", "/Delete", "/TN", r"Negi\Revisar actualizaciones", "/F"]


def test_ataque_titulo_malicioso_no_entra_al_script(monkeypatch):
    ll = _Llamadas()
    monkeypatch.setattr(notificador.subprocess, "run", ll)
    veneno = "\"'; Start-Process calc; '<toast>$(calc)`"
    notificador.mostrar_notificacion(veneno, veneno)
    script = " ".join(ll.args[0])
    assert "calc" not in script                                # nunca concatenado en el comando
    assert ll.env[0]["NEGI_TITULO"] == veneno[:120]            # viaja como dato


def test_revisar_y_avisar_una_vez_por_version(monkeypatch, datos):
    avisos = []
    monkeypatch.setattr(notificador.actualizador, "buscar", lambda v: {"version": "1.5.0", "notas": ""})
    monkeypatch.setattr(notificador, "mostrar_notificacion", lambda t, x: avisos.append(t))
    assert notificador.revisar_y_avisar("1.4.0") == "1.5.0"
    assert notificador.revisar_y_avisar("1.4.0") is None       # ya avisó de esa versión
    assert len(avisos) == 1 and ajustes.cargar()["ultima_avisada"] == "1.5.0"


def test_revisar_sin_internet_no_falla(monkeypatch, datos):
    monkeypatch.setattr(notificador.actualizador, "buscar", lambda v: None)
    monkeypatch.setattr(notificador, "mostrar_notificacion", lambda t, x: (_ for _ in ()).throw(AssertionError))
    assert notificador.revisar_y_avisar("1.4.0") is None


def test_revisar_respeta_casilla_apagada(monkeypatch, datos):
    a = ajustes.cargar()
    a["aviso_cerrada"] = "no"
    ajustes.guardar(a)
    monkeypatch.setattr(notificador.actualizador, "buscar", lambda v: (_ for _ in ()).throw(AssertionError))
    assert notificador.revisar_y_avisar("1.4.0") is None
