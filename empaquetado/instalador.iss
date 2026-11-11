; Instalador de "Negi" (descargador de videos), Inno Setup 6.
; Lo llama compilar.ps1 con /DBuild=<carpeta de compilación> /DSalida=<carpeta salida>.
; El AppId no cambia: instalar Negi encima del antiguo "Descargador de Videos" lo actualiza.

#define Nombre "Negi"
#define Version "1.3.0"
#define Exe "Negi.exe"

[Setup]
AppId={{D43AEB75-010B-482D-8435-CF3940DDA45A}
AppName={#Nombre}
AppVersion={#Version}
AppVerName={#Nombre} {#Version}
AppPublisher=Hecho en casa
DefaultDirName={localappdata}\Programs\Negi
DefaultGroupName={#Nombre}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#Salida}
OutputBaseFilename=Negi-Setup
SetupIconFile=icono.ico
UninstallDisplayIcon={app}\{#Exe}
UninstallDisplayName={#Nombre}
InfoBeforeFile=LEEME.txt
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
CloseApplications=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "{#Build}\dist\Negi\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#Build}\herramientas\*"; DestDir: "{app}\herramientas"; Flags: ignoreversion
Source: "{#Build}\licencias\*"; DestDir: "{app}\licencias"; Flags: ignoreversion
Source: "arte\LICENCIA-miku.txt"; DestDir: "{app}\licencias"; DestName: "icono-hatsune-miku-LICENCIA.txt"; Flags: ignoreversion
Source: "LEEME.txt"; DestDir: "{app}"; DestName: "LÉEME.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#Nombre}"; Filename: "{app}\{#Exe}"
Name: "{autodesktop}\{#Nombre}"; Filename: "{app}\{#Exe}"; Tasks: escritorio

[Run]
Filename: "{app}\{#Exe}"; Description: "Abrir {#Nombre} ahora"; Flags: nowait postinstall skipifsilent
; Actualización automática desde la app (/SILENT): vuelve a abrir Negi al terminar.
Filename: "{app}\{#Exe}"; Flags: nowait skipifnotsilent

[InstallDelete]
; Restos del nombre anterior ("Descargador de Videos") al actualizar.
Type: files; Name: "{app}\DescargadorDeVideos.exe"
Type: files; Name: "{autoprograms}\Descargador de Videos.lnk"
Type: files; Name: "{autodesktop}\Descargador de Videos.lnk"

[UninstallDelete]
; El yt-dlp actualizado vive fuera de {app}; se borra al desinstalar. Los ajustes y los videos NO se tocan.
Type: filesandordirs; Name: "{localappdata}\DescargadorDeVideos\bin"
