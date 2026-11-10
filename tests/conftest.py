import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))


def pytest_configure(config):
    config.addinivalue_line("markers", "red: necesita internet (descarga real de YouTube)")


@pytest.fixture
def datos(tmp_path, monkeypatch):
    """Carpeta de datos aislada para cada prueba."""
    carpeta = tmp_path / "datos"
    monkeypatch.setenv("DESCARGADOR_DATOS", str(carpeta))
    return carpeta
