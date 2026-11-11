// Descargador de Videos — comportamiento de la interfaz (v1.1: cola, historial, calidad, avisos).
"use strict";

const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;

const estado = { vista: null, url: "", pidiendo: 0, ultimoArchivo: "", copiadoVisto: "" };
const PARTES = { video: "Descargando video", audio: "Descargando audio" };
const PASOS = {
  Merger: "Uniendo imagen y sonido…", ExtractAudio: "Convirtiendo a MP3…",
  FixupM3u8: "Arreglando el archivo…", MoveFiles: "Guardando…",
};
const NOMBRE_MODO = { max: "Máxima calidad", mp4: "MP4", mp3: "MP3" };

// ---------- utilidades ----------
function duracion(s) {
  if (!s && s !== 0) return "";
  s = Math.round(s);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), seg = String(s % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${seg}` : `${m}:${seg}`;
}
function textoCalidad(alto) {
  if (!alto) return "";
  if (alto >= 4320) return "Hasta 8K";
  if (alto >= 2160) return "Hasta 4K";
  if (alto >= 1440) return "Hasta 1440p (2K)";
  return `Hasta ${alto}p`;
}
function tamanoBonito(bytes) {
  if (!bytes) return "";
  const gb = bytes / 1024 ** 3;
  if (gb >= 1) return `${gb.toFixed(gb >= 10 ? 0 : 1)} GB`;
  return `${Math.max(1, Math.round(bytes / 1024 ** 2))} MB`;
}
const textoCalidadElegida =(m, c) => (c ? (m === "mp3" ? `${c} kbps` : `${c}p`) : "");
const pareceEnlace =(t) => /^(https?:\/\/)?([\w-]+\.)+[a-z]{2,}\/\S+/i.test((t || "").trim());
const nombreArchivo = (ruta) => ruta.split(/[\\/]/).pop();
const limpio = (t) => (t && !/unknown|n\/a/i.test(t) ? t : "");

function miniatura(caja, url) {
  caja.replaceChildren();
  if (!/^(https:|data:image\/)/.test(url || "")) return;
  const img = new Image();
  img.alt = "";
  img.referrerPolicy = "no-referrer";
  img.onload = () => caja.replaceChildren(img);
  img.src = url;
}

let temporizadorAviso;
function aviso(texto) {
  const el = $("aviso");
  el.textContent = texto; el.hidden = false;
  clearTimeout(temporizadorAviso);
  temporizadorAviso = setTimeout(() => { el.hidden = true; }, 4500);
}
function mostrarError(texto) {
  $("mensaje-texto").textContent = texto;
  $("mensaje").hidden = !texto;
}
const modo = () => document.querySelector("input[name=modo]:checked").value;
const calidadElegida = () => document.querySelector("input[name=calidad]:checked").value;

// Aviso cuando la ventana no está al frente: parpadeo en la barra de tareas + notificación si hay permiso.
function notificar(titulo, cuerpo) {
  if (document.hasFocus()) return;
  api().llamar_atencion();
  try {
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification(titulo, { body: cuerpo, icon: "logo.png", silent: false });
    }
  } catch { /* sin notificaciones: queda el parpadeo */ }
}
function pedirPermisoNotificaciones() {
  try {
    if ("Notification" in window && Notification.permission === "default") Notification.requestPermission().catch(() => {});
  } catch { /* no disponible */ }
}

// ---------- calidad ----------
function ajustarCalidades() {
  const esAudio = modo() === "mp3";
  const alto = estado.vista && !estado.vista.es_lista ? estado.vista.alto_max : null;
  for (const input of document.querySelectorAll("input[name=calidad]")) {
    const tipo = input.closest(".chip").dataset.tipo;  // video (píxeles) · audio (kbps) · ninguno = Máxima
    const v = Number(input.value);
    const visible = !tipo || (esAudio ? tipo === "audio" : tipo === "video" && (!alto || v <= alto));
    input.closest(".chip").hidden = !visible;
    if (!visible && input.checked) document.querySelector("input[name=calidad][value='']").checked = true;
  }
}

// ---------- vista previa ----------
function limpiarVista() {
  estado.vista = null;
  $("vista").hidden = true;
  $("btn-descargar").disabled = $("btn-agregar").disabled = true;
  $("enlace").removeAttribute("aria-invalid");
  ajustarCalidades();
}

async function pedirVista(url) {
  url = (url || "").trim();
  if (!url || url === estado.url) return;
  estado.url = url;
  mostrarError("");
  $("panel-listo").hidden = true;
  limpiarVista();
  if (!pareceEnlace(url)) {
    $("enlace").setAttribute("aria-invalid", "true");
    mostrarError("Eso no parece un enlace. Copia la dirección completa del video.");
    return;
  }
  const turno = ++estado.pidiendo;
  const vista = $("vista");
  vista.hidden = false; vista.classList.add("cargando");
  $("vista-titulo").textContent = "Buscando el video…";
  $("vista-meta").textContent = "…";
  $("miniatura").replaceChildren();
  let r;
  try { r = await api().vista_previa(url); } catch { r = { ok: false, error: "No se pudo revisar el enlace. Inténtalo de nuevo." }; }
  if (turno !== estado.pidiendo) return; // llegó otra búsqueda después
  vista.classList.remove("cargando");
  if (!r.ok) {
    vista.hidden = true;
    $("enlace").setAttribute("aria-invalid", "true");
    mostrarError(r.error);
    estado.url = ""; // permitir reintentar el mismo enlace
    return;
  }
  estado.vista = r;
  $("vista-titulo").textContent = r.titulo;
  $("vista-titulo").title = r.titulo;
  $("vista-meta").textContent = [r.canal, r.es_lista ? `${r.cantidad} videos` : duracion(r.duracion),
    r.tamano ? `≈ ${tamanoBonito(r.tamano)}` : ""].filter(Boolean).join(" · ");
  $("vista-insignia").textContent = r.es_lista ? "Lista de reproducción" : textoCalidad(r.alto_max);
  $("vista-insignia").hidden = !$("vista-insignia").textContent;
  miniatura($("miniatura"), r.miniatura);
  $("btn-descargar").disabled = $("btn-agregar").disabled = false;
  ajustarCalidades();
}

// ---------- cola ----------
async function encolar(ahora) {
  if (!estado.vista) return;
  pedirPermisoNotificaciones();
  let lista = false;
  if (estado.vista.es_lista) {
    lista = confirm(`Es una lista de reproducción con ${estado.vista.cantidad} videos.\n¿Descargarlos todos?`);
    if (!lista) return;
  }
  mostrarError("");
  // Aviso de espacio: mientras descarga se necesita cerca del doble del tamaño final.
  if (estado.vista.tamano) {
    const e = await api().revisar_espacio(estado.vista.tamano);
    if (!e.suficiente && !confirm(
      `Este video pesa cerca de ${tamanoBonito(estado.vista.tamano)} y mientras se descarga necesita ` +
      `unos ${tamanoBonito(e.necesario)} libres.\nEn la carpeta elegida solo quedan ${tamanoBonito(e.libre)}.\n\n` +
      "Puedes liberar espacio, elegir una calidad menor u otra carpeta.\n¿Intentar de todas formas?")) return;
  }
  const args = [estado.url, modo(), calidadElegida(), lista,
                estado.vista.titulo, estado.vista.miniatura || ""];
  const id = await (ahora ? api().descargar(...args) : api().agregar_a_cola(...args));
  if (!id) { mostrarError("No se pudo agregar. Revisa el enlace."); return; }
  if (!ahora) aviso(`Agregado a la cola: ${estado.vista.titulo}`);
  // Listo para pegar el siguiente enlace.
  $("enlace").value = ""; estado.url = ""; limpiarVista(); $("panel-listo").hidden = true;
  $("enlace").focus();
}

function crearElemento(e) {
  const li = document.createElement("li");
  li.className = "elemento";
  li.dataset.id = e.id;
  const mini = document.createElement("div");
  mini.className = "elemento-mini";
  miniatura(mini, e.miniatura);
  const texto = document.createElement("div");
  texto.className = "elemento-texto";
  const titulo = document.createElement("p");
  titulo.className = "elemento-titulo";
  titulo.textContent = e.titulo;
  titulo.title = e.titulo;
  const est = document.createElement("p");
  est.className = "elemento-estado num";
  const barra = document.createElement("div");
  barra.className = "barra-progreso";
  barra.setAttribute("role", "progressbar");
  barra.setAttribute("aria-valuemin", "0");
  barra.setAttribute("aria-valuemax", "100");
  barra.innerHTML = '<div class="barra-relleno"></div>';
  texto.append(titulo, est, barra);
  const boton = document.createElement("button");
  boton.className = "btn btn-texto";
  boton.addEventListener("click", () => {
    boton.disabled = true;
    api().quitar_de_cola(e.id);
  });
  li.append(mini, texto, boton);
  return li;
}

function actualizarElemento(li, e) {
  const est = li.querySelector(".elemento-estado");
  const barra = li.querySelector(".barra-progreso");
  const boton = li.querySelector("button");
  const detalle = [NOMBRE_MODO[e.modo], textoCalidadElegida(e.modo, e.calidad)].filter(Boolean).join(" · ");
  if (e.estado === "espera") {
    est.textContent = `En espera · ${detalle}`;
    barra.hidden = true;
    boton.textContent = "Quitar";
    boton.classList.remove("btn-peligro");
  } else {
    barra.hidden = false;
    if (!li.dataset.progreso) { est.textContent = e.estado === "cancelando" ? "Cancelando…" : "Preparando…"; barra.classList.add("indeterminada"); }
    boton.textContent = "Cancelar";
    boton.classList.add("btn-peligro");
    boton.disabled = e.estado === "cancelando";
  }
  boton.setAttribute("aria-label", `${boton.textContent}: ${e.titulo}`);
}

function pintarCola(elementos) {
  const lista = $("cola-lista");
  const vivos = [...lista.children].filter((li) => !li.classList.contains("sale"));
  const antes = new Map(vivos.map((li) => [li.dataset.id, li.getBoundingClientRect().top]));
  const ids = new Set(elementos.map((e) => e.id));
  // Los que salen dejan de ocupar espacio al instante; los demás suben a la vez (choreograph: "together").
  for (const li of vivos) {
    if (ids.has(li.dataset.id)) continue;
    li.style.top = `${li.offsetTop}px`;
    li.classList.add("sale");
    setTimeout(() => li.remove(), 160);
  }
  for (const e of elementos) {
    let li = vivos.find((x) => x.dataset.id === e.id);
    if (!li) { li = crearElemento(e); li.classList.add("entra"); }
    actualizarElemento(li, e);
    lista.appendChild(li);
  }
  for (const li of lista.children) {
    if (li.classList.contains("sale") || !antes.has(li.dataset.id)) continue;
    const d = antes.get(li.dataset.id) - li.getBoundingClientRect().top;
    if (!d) continue;
    li.style.transition = "none";
    li.style.transform = `translateY(${d}px)`;
    requestAnimationFrame(() => {
      li.style.transition = "transform 200ms cubic-bezier(.2,.8,.2,1)";
      li.style.transform = "";
    });
  }
  $("cola-cuenta").textContent = elementos.length > 1 ? `${elementos.length}` : "";
  if (elementos.length) $("panel-cola").hidden = false;
  else setTimeout(() => { if (!$("cola-lista").querySelector(".elemento:not(.sale)")) $("panel-cola").hidden = true; }, 170);
}

function ponerProgreso(e) {
  const li = $("cola-lista").querySelector(`[data-id="${e.id}"]`);
  if (!li) return;
  li.dataset.progreso = "1";
  const barra = li.querySelector(".barra-progreso");
  const est = li.querySelector(".elemento-estado");
  if (e.tipo === "procesando") {
    barra.classList.add("indeterminada");
    est.textContent = PASOS[e.paso] || "Procesando…";
    return;
  }
  const partes = [`${PARTES[e.parte] || "Descargando"}…`];
  if (e.pct == null) barra.classList.add("indeterminada");
  else {
    barra.classList.remove("indeterminada");
    barra.firstChild.style.width = `${Math.min(e.pct, 100)}%`;
    barra.setAttribute("aria-valuenow", Math.round(e.pct));
    partes.push(`${Math.floor(e.pct)} %`);
  }
  if (limpio(e.vel)) partes.push(e.vel.replace("iB", "B"));
  if (limpio(e.eta)) partes.push(`quedan ${e.eta}`);
  est.textContent = partes.join(" · ");
}

window.alEvento = (e) => {
  switch (e.tipo) {
    case "cola": pintarCola(e.elementos); break;
    case "progreso":
    case "procesando": ponerProgreso(e); break;
    case "listo":
      estado.ultimoArchivo = e.archivo;
      notificar("✓ Descarga lista", e.titulo);
      if (!e.quedan) {
        $("listo-archivo").textContent = e.cantidad > 1
          ? `${e.cantidad} videos guardados` + (e.incompleta ? " (algunos no se pudieron descargar)" : "")
          : nombreArchivo(e.archivo);
        $("panel-listo").hidden = false;
      } else {
        aviso(`✓ Listo: ${e.titulo}`);
      }
      if (!$("seccion-historial").hidden) cargarHistorial();
      break;
    case "cancelado": aviso(`Cancelado: ${e.titulo}`); break;
    case "error":
      mostrarError(`«${e.titulo}»: ${e.texto}`);
      notificar("No se pudo descargar", e.titulo);
      break;
    case "aviso": aviso(e.texto); break;
    case "version_nueva":
      $("texto-version").textContent = `Negi ${e.version} ya está disponible`;
      $("texto-version").title = e.notas || "";
      $("tira-version").hidden = false;
      break;
    case "actualizando":
      if (e.error) {
        $("btn-actualizar-app").disabled = false;
        $("texto-version").textContent = "No se pudo actualizar";
        mostrarError(e.error);
      } else {
        $("texto-version").textContent = `Descargando actualización… ${Math.floor(e.pct)} %`;
      }
      break;
  }
};

$("btn-actualizar-app").addEventListener("click", async () => {
  $("btn-actualizar-app").disabled = true;
  $("texto-version").textContent = "Preparando la actualización…";
  const error = await api().actualizar_app();
  if (error) { $("btn-actualizar-app").disabled = false; $("tira-version").hidden = true; aviso(error); }
});

// ---------- historial ----------
function fechaBonita(iso) {
  try {
    return new Date(iso).toLocaleString("es", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
}

async function cargarHistorial() {
  const lista = await api().historial();
  const ul = $("historial-lista");
  ul.replaceChildren();
  $("historial-vacio").hidden = lista.length > 0;
  for (const h of lista) {
    const li = document.createElement("li");
    li.className = "elemento" + (h.existe ? "" : " perdido");
    const mini = document.createElement("div");
    mini.className = "elemento-mini";
    miniatura(mini, h.miniatura);
    const texto = document.createElement("div");
    texto.className = "elemento-texto";
    const titulo = document.createElement("p");
    titulo.className = "elemento-titulo";
    titulo.textContent = h.titulo;
    titulo.title = h.titulo;
    const meta = document.createElement("p");
    meta.className = "elemento-estado";
    meta.textContent = h.existe
      ? [fechaBonita(h.fecha), NOMBRE_MODO[h.modo], textoCalidadElegida(h.modo, h.calidad)].filter(Boolean).join(" · ")
      : "Archivo movido o borrado";
    const botones = document.createElement("div");
    botones.className = "historial-botones";
    const boton = (txt, clase, fn) => {
      const b = document.createElement("button");
      b.className = `btn ${clase}`;
      b.textContent = txt;
      b.setAttribute("aria-label", `${txt}: ${h.titulo}`);
      b.addEventListener("click", fn);
      botones.append(b);
      return b;
    };
    boton("Reproducir", "btn-secundario", async () => {
      if (!(await api().reproducir(h.archivo))) aviso("No se encontró el archivo. ¿Lo moviste o borraste?");
    }).disabled = !h.existe;
    boton("Abrir carpeta", "btn-texto", () => api().abrir_carpeta(h.archivo));
    boton("Quitar", "btn-texto", async () => { await api().quitar_historial(h.id); cargarHistorial(); });
    texto.append(titulo, meta, botones);
    li.append(mini, texto);
    ul.append(li);
  }
}

// ---------- pestañas ----------
function elegirPestana(cual) {
  const historial = cual === "historial";
  $("tab-descargar").setAttribute("aria-selected", String(!historial));
  $("tab-historial").setAttribute("aria-selected", String(historial));
  $("tab-descargar").tabIndex = historial ? -1 : 0;
  $("tab-historial").tabIndex = historial ? 0 : -1;
  $("seccion-descargar").hidden = historial;
  $("seccion-historial").hidden = !historial;
  if (historial) cargarHistorial();
}

// ---------- enlace copiado con la app abierta ----------
async function revisarPortapapeles() {
  const t = await api().portapapeles();
  const actual = $("enlace").value.trim();
  if (pareceEnlace(t) && t !== actual && t !== estado.copiadoVisto) {
    estado.copiadoVisto = t;
    if (!actual) { $("enlace").value = t; pedirVista(t); return; }
    $("tira-copiado").hidden = false;
  }
}

// ---------- ajustes ----------
function abrirAjustes(abrir) {
  $("hoja").hidden = $("velo").hidden = !abrir;
  if (abrir) {
    $("btn-cerrar-ajustes").focus();
    api().version_motor().then((v) => { $("v-motor").textContent = v; });
  } else {
    $("btn-ajustes").focus();
  }
}

// ---------- arranque ----------
async function iniciar() {
  const info = await api().info();
  $("v-app").textContent = info.version;
  $("carpeta").textContent = info.carpeta;
  $("carpeta").title = info.carpeta;
  const radio = document.querySelector(`input[name=modo][value=${info.modo}]`);
  if (radio) radio.checked = true;
  const chip = document.querySelector(`input[name=calidad][value='${info.calidad || ""}']`);
  if (chip) chip.checked = true;
  ajustarCalidades();
  pintarCola(await api().cola());
  await revisarPortapapeles();
  if (!$("enlace").value) $("enlace").focus();
}

$("btn-pegar").addEventListener("click", async () => {
  const t = await api().portapapeles();
  if (!t) { mostrarError("No hay ningún enlace copiado. Copia el enlace del video primero."); return; }
  $("tira-copiado").hidden = true;
  estado.copiadoVisto = t;
  $("enlace").value = t;
  pedirVista(t);
});
$("btn-usar-copiado").addEventListener("click", () => {
  $("tira-copiado").hidden = true;
  $("enlace").value = estado.copiadoVisto;
  pedirVista(estado.copiadoVisto);
});
$("btn-ignorar-copiado").addEventListener("click", () => { $("tira-copiado").hidden = true; });
window.addEventListener("focus", () => { if (window.pywebview) revisarPortapapeles(); });
$("enlace").addEventListener("paste", () => setTimeout(() => pedirVista($("enlace").value), 0));
$("enlace").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter") { ev.preventDefault(); if (estado.vista) encolar(true); else pedirVista($("enlace").value); }
});
let temporizadorEscritura;
$("enlace").addEventListener("input", () => {
  clearTimeout(temporizadorEscritura);
  if (!$("enlace").value.trim()) { estado.url = ""; limpiarVista(); mostrarError(""); return; }
  temporizadorEscritura = setTimeout(() => pedirVista($("enlace").value), 700);
});
for (const r of document.querySelectorAll("input[name=modo]")) r.addEventListener("change", ajustarCalidades);
$("btn-descargar").addEventListener("click", () => encolar(true));
$("btn-agregar").addEventListener("click", () => encolar(false));
$("btn-carpeta").addEventListener("click", async () => {
  const c = await api().elegir_carpeta();
  if (c) { $("carpeta").textContent = c; $("carpeta").title = c; }
});
$("btn-reproducir").addEventListener("click", async () => {
  if (!(await api().reproducir(estado.ultimoArchivo))) aviso("No se encontró el archivo. ¿Lo moviste o borraste?");
});
$("btn-abrir").addEventListener("click", () => api().abrir_carpeta(estado.ultimoArchivo));
$("btn-otro").addEventListener("click", () => {
  $("enlace").value = ""; estado.url = ""; limpiarVista(); $("panel-listo").hidden = true; $("enlace").focus();
});
$("tab-descargar").addEventListener("click", () => elegirPestana("descargar"));
$("tab-historial").addEventListener("click", () => elegirPestana("historial"));
document.querySelector(".pestanas").addEventListener("keydown", (ev) => {
  if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
  const historial = $("seccion-historial").hidden;
  elegirPestana(historial ? "historial" : "descargar");
  $(historial ? "tab-historial" : "tab-descargar").focus();
});
$("btn-ajustes").addEventListener("click", () => abrirAjustes(true));
$("btn-cerrar-ajustes").addEventListener("click", () => abrirAjustes(false));
$("velo").addEventListener("click", () => abrirAjustes(false));
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !$("hoja").hidden) abrirAjustes(false); });
$("btn-licencias").addEventListener("click", () => api().abrir_licencias());
$("btn-actualizar").addEventListener("click", async () => {
  const b = $("btn-actualizar");
  b.disabled = true;
  $("estado-actualizar").textContent = "Buscando…";
  try {
    $("estado-actualizar").textContent = await api().buscar_actualizacion();
    $("v-motor").textContent = await api().version_motor();
  } catch {
    $("estado-actualizar").textContent = "No se pudo buscar actualizaciones. Inténtalo más tarde.";
  } finally {
    b.disabled = false;
  }
});

window.addEventListener("pywebviewready", iniciar);
