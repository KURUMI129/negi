# PyInstaller: genera Negi.exe (modo carpeta, sin consola).
# Uso: pyinstaller empaquetado/app.spec --distpath <build>/dist --workpath <build>/work
import os

from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                 VarFileInfo, VarStruct, VSVersionInfo)

RAIZ = os.path.abspath(os.path.join(SPECPATH, ".."))
APP = os.path.join(RAIZ, "app")

version = VSVersionInfo(
    ffi=FixedFileInfo(filevers=(1, 2, 0, 0), prodvers=(1, 2, 0, 0)),
    kids=[
        StringFileInfo([StringTable("040A04B0", [
            StringStruct("FileDescription", "Negi - Descargador de videos"),
            StringStruct("ProductName", "Negi"),
            StringStruct("FileVersion", "1.2.0"),
            StringStruct("ProductVersion", "1.2.0"),
            StringStruct("OriginalFilename", "Negi.exe"),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x040A, 1200])]),
    ],
)

a = Analysis(
    [os.path.join(SPECPATH, "lanzador.py")],
    pathex=[APP],
    datas=[(os.path.join(APP, "descargador", "ui"), os.path.join("descargador", "ui"))],
    hiddenimports=["descargador.api", "descargador.motor"],
    excludes=["tkinter", "yt_dlp", "PIL", "pytest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Negi",
    icon=os.path.join(SPECPATH, "icono.ico"),
    console=False,
    version=version,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Negi", upx=False)
